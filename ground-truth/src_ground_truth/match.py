from __future__ import annotations

import bisect
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MatchConfig:
    TD_ms: int
    VD_rel: float
    TW_ms: int
    VW_rel: float
    tron_tolerance_mult: float = 2.0


def _safe_float(x: Any) -> float | None:
    if x is None:
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _is_tron(network: str | None) -> bool:
    if not network:
        return False
    return network.lower() in {"tron", "trx", "trc20"}


def _amount_close(a: float | None, b: float | None, rel_tol: float) -> bool:
    if a is None or b is None:
        return False
    if a == 0 and b == 0:
        return True
    denom = max(abs(a), 1e-12)
    return abs(a - b) / denom <= rel_tol


def _score_time(dt_ms: int, window_ms: int) -> float:
    if window_ms <= 0:
        return 0.0
    x = max(0.0, 1.0 - (abs(dt_ms) / window_ms))
    return x


def _score_amount(a: float | None, b: float | None, rel_tol: float) -> float:
    if a is None or b is None:
        return 0.0
    denom = max(abs(a), 1e-12)
    diff = abs(a - b) / denom
    if diff > rel_tol:
        return 0.0
    return max(0.0, 1.0 - (diff / rel_tol))


class GroundTruthMatcher:
    """
    Match SideShift history H -> deposit D -> settlement W.
    H fields expected:
      - shift_timestamp (ISO string)
      - input_coin, input_amount
      - output_coin, output_amount
      - raw.depositNetwork / raw.settleNetwork (optional but used for TRON tolerance)
    """

    def __init__(
        self,
        cfg: MatchConfig,
        deposits: list[dict[str, Any]],
        withdrawals: list[dict[str, Any]],
        tracer: Any | None = None,
    ) -> None:
        self.cfg = cfg
        self.deposits = deposits
        self.withdrawals = withdrawals
        self.tracer = tracer
        self._stats = {
            "matched_h": 0,
            "matched_deposit": 0,
            "matched_settlement": 0,
        }

        self._dep_by_token: dict[str, list[dict[str, Any]]] = {}
        self._dep_ts_by_token: dict[str, list[int]] = {}
        self._with_by_token: dict[str, list[dict[str, Any]]] = {}
        self._with_ts_by_token: dict[str, list[int]] = {}

        for d in deposits:
            t = str(d.get("token") or "").upper()
            self._dep_by_token.setdefault(t, []).append(d)
        for w in withdrawals:
            t = str(w.get("token") or "").upper()
            self._with_by_token.setdefault(t, []).append(w)

        for t in self._dep_by_token:
            self._dep_by_token[t].sort(key=lambda x: int(x.get("timestamp", 0)))
            self._dep_ts_by_token[t] = [int(x["timestamp"]) for x in self._dep_by_token[t]]
        for t in self._with_by_token:
            self._with_by_token[t].sort(key=lambda x: int(x.get("timestamp", 0)))
            self._with_ts_by_token[t] = [int(x["timestamp"]) for x in self._with_by_token[t]]

    def stats(self) -> dict[str, int]:
        return dict(self._stats)

    def match_one(self, h: dict[str, Any]) -> dict[str, Any]:
        dep = self._match_deposit(h)
        sett = self._match_settlement(h, dep) if dep else None

        deposit_path: list[dict[str, Any]] = []
        settlement_path: list[dict[str, Any]] = []
        deposit_trace = None
        settlement_trace = None

        if self.tracer is not None and dep is not None:
            dep_network = _safe_get_network(h, "depositNetwork")
            dep_tol = self.cfg.VD_rel * (
                self.cfg.tron_tolerance_mult if _is_tron(dep_network) else 1.0
            )
            try:
                if hasattr(self.tracer, "trace_deposit_path"):
                    deposit_path = self.tracer.trace_deposit_path(
                        dep,
                        expected_token=str(h.get("input_coin") or ""),
                        expected_amount=_safe_float(h.get("input_amount")),
                        rel_tol=dep_tol,
                    )
                    deposit_trace = deposit_path[0] if deposit_path else None
                else:
                    deposit_trace = self.tracer.trace_deposit_prev_hop(
                        dep,
                        expected_token=str(h.get("input_coin") or ""),
                        expected_amount=_safe_float(h.get("input_amount")),
                        rel_tol=dep_tol,
                    )
            except Exception:
                deposit_path = []
                deposit_trace = None

        if self.tracer is not None and sett is not None:
            sett_network = _safe_get_network(h, "settleNetwork")
            sett_tol = self.cfg.VW_rel * (
                self.cfg.tron_tolerance_mult if _is_tron(sett_network) else 1.0
            )
            try:
                if hasattr(self.tracer, "trace_settlement_path"):
                    settlement_path = self.tracer.trace_settlement_path(
                        sett,
                        expected_token=str(h.get("output_coin") or ""),
                        expected_amount=_safe_float(h.get("output_amount")),
                        rel_tol=sett_tol,
                    )
                    settlement_trace = settlement_path[-1] if settlement_path else None
                else:
                    settlement_trace = self.tracer.trace_settlement_next_hop(
                        sett,
                        expected_token=str(h.get("output_coin") or ""),
                        expected_amount=_safe_float(h.get("output_amount")),
                        rel_tol=sett_tol,
                    )
            except Exception:
                settlement_path = []
                settlement_trace = None

        matched = dep is not None and sett is not None
        if dep is not None:
            self._stats["matched_deposit"] += 1
        if sett is not None:
            self._stats["matched_settlement"] += 1
        if matched:
            self._stats["matched_h"] += 1

        score = self._match_score(h, dep, sett)
        return {
            "history": h,
            "deposit": dep,
            "settlement": sett,
            "deposit_path": deposit_path,
            "settlement_path": settlement_path,
            "deposit_trace": deposit_trace,
            "settlement_trace": settlement_trace,
            "match_score": score,
        }

    def _match_deposit(self, h: dict[str, Any]) -> dict[str, Any] | None:
        h_coin = str(h.get("input_coin") or "").upper()
        h_amt = _safe_float(h.get("input_amount"))
        h_time_ms = history_time_ms(h)
        if h_time_ms is None or not h_coin:
            return None

        network = _safe_get_network(h, "depositNetwork")
        rel_tol = self.cfg.VD_rel * (self.cfg.tron_tolerance_mult if _is_tron(network) else 1.0)

        candidates = self._dep_by_token.get(h_coin, [])
        ts_list = self._dep_ts_by_token.get(h_coin, [])
        if not candidates:
            return None

        lo = bisect.bisect_left(ts_list, h_time_ms - self.cfg.TD_ms)
        hi = bisect.bisect_right(ts_list, h_time_ms + self.cfg.TD_ms)
        best: dict[str, Any] | None = None
        best_score = -1.0

        for d in candidates[lo:hi]:
            dt = int(d.get("timestamp", 0))
            if not _amount_close(h_amt, _safe_float(d.get("amount")), rel_tol):
                continue

            s = 0.55 * _score_time(h_time_ms - dt, self.cfg.TD_ms) + 0.45 * _score_amount(
                h_amt, _safe_float(d.get("amount")), rel_tol
            )
            if s > best_score:
                best_score = s
                best = d

        return best

    def _match_settlement(
        self, h: dict[str, Any], dep: dict[str, Any]
    ) -> dict[str, Any] | None:
        h_coin = str(h.get("output_coin") or "").upper()
        h_amt = _safe_float(h.get("output_amount"))
        if not h_coin:
            return None

        dep_ts = int(dep.get("timestamp", 0))
        network = _safe_get_network(h, "settleNetwork")
        rel_tol = self.cfg.VW_rel * (self.cfg.tron_tolerance_mult if _is_tron(network) else 1.0)

        candidates = self._with_by_token.get(h_coin, [])
        ts_list = self._with_ts_by_token.get(h_coin, [])
        if not candidates:
            return None

        lo = bisect.bisect_left(ts_list, dep_ts)
        hi = bisect.bisect_right(ts_list, dep_ts + self.cfg.TW_ms)
        best: dict[str, Any] | None = None
        best_score = -1.0

        for w in candidates[lo:hi]:
            wt = int(w.get("timestamp", 0))
            if wt < dep_ts:
                continue
            if not _amount_close(h_amt, _safe_float(w.get("amount")), rel_tol):
                continue

            s = 0.55 * _score_time(wt - dep_ts, self.cfg.TW_ms) + 0.45 * _score_amount(
                h_amt, _safe_float(w.get("amount")), rel_tol
            )
            if s > best_score:
                best_score = s
                best = w

        return best

    def _match_score(
        self,
        h: dict[str, Any],
        dep: dict[str, Any] | None,
        sett: dict[str, Any] | None,
    ) -> float:
        if dep is None or sett is None:
            return 0.0

        h_time = history_time_ms(h)
        if h_time is None:
            return 0.0

        h_in = _safe_float(h.get("input_amount"))
        h_out = _safe_float(h.get("output_amount"))

        dep_tol = self.cfg.VD_rel * (
            self.cfg.tron_tolerance_mult
            if _is_tron(_safe_get_network(h, "depositNetwork"))
            else 1.0
        )
        sett_tol = self.cfg.VW_rel * (
            self.cfg.tron_tolerance_mult
            if _is_tron(_safe_get_network(h, "settleNetwork"))
            else 1.0
        )

        dep_part = 0.5 * _score_time(h_time - int(dep["timestamp"]), self.cfg.TD_ms) + 0.5 * _score_amount(
            h_in, _safe_float(dep.get("amount")), dep_tol
        )
        sett_part = 0.5 * _score_time(int(sett["timestamp"]) - int(dep["timestamp"]), self.cfg.TW_ms) + 0.5 * _score_amount(
            h_out, _safe_float(sett.get("amount")), sett_tol
        )
        return round(0.5 * dep_part + 0.5 * sett_part, 6)


def history_time_ms(h: dict[str, Any]) -> int | None:
    """
    SideShift record field `shift_timestamp` is ISO string.
    We convert to ms since epoch. Prefer raw `createdAt` if present.
    """
    ts = h.get("shift_timestamp") or _safe_get(h, ["raw", "createdAt"])
    if not isinstance(ts, str):
        return None

    # Minimal ISO parsing without extra deps.
    # Handles: 2026-05-22T11:04:14.420Z  / with offset
    try:
        from datetime import datetime

        if ts.endswith("Z"):
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(ts)
        return int(dt.timestamp() * 1000)
    except Exception:
        return None


_history_time_ms = history_time_ms


def _safe_get(d: dict[str, Any], keys: list[str]) -> Any:
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def _safe_get_network(h: dict[str, Any], field: str) -> str | None:
    raw = h.get("raw")
    if isinstance(raw, dict):
        v = raw.get(field)
        if isinstance(v, str):
            return v
    return None

