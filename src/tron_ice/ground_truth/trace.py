from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.tron_ice.ground_truth.match import _amount_close, _safe_float, _score_amount, _score_time
from src.tron_ice.ground_truth.trongrid_client import TronGridClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TraceConfig:
    hop_window_ms: int = 30 * 60 * 1000
    max_depth: int = 3
    max_pages: int = 20


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _normalize_tron_address(addr: str | None) -> str | None:
    if not addr or not isinstance(addr, str):
        return None
    if addr.startswith("T"):
        return addr
    if addr.startswith("41"):
        root = str(_repo_root())
        if root not in sys.path:
            sys.path.insert(0, root)
        try:
            from src.tron_ice.normalization.base58 import hex_to_base58

            return hex_to_base58(addr)
        except Exception:
            return addr
    return addr


class TronMultiHopTracer:
    """
    Trace deposit/settlement paths on TRON beyond hot-wallet-only views.

    deposit_path (backward): UserA -> ... -> depositAddress -> hot-wallet (deposit tx)
    settlement_path (forward): hot-wallet (settlement tx) -> payoutAddress -> ... -> UserB
    """

    def __init__(self, client: TronGridClient, cfg: TraceConfig | None = None) -> None:
        self.client = client
        self.cfg = cfg or TraceConfig()
        self._cache: dict[tuple[str, int, int, str], list[dict[str, Any]]] = {}

    def trace_deposit_prev_hop(
        self,
        deposit_tx: dict[str, Any],
        expected_token: str,
        expected_amount: float | None,
        rel_tol: float,
    ) -> dict[str, Any] | None:
        path = self.trace_deposit_path(deposit_tx, expected_token, expected_amount, rel_tol)
        return path[0] if path else None

    def trace_settlement_next_hop(
        self,
        settlement_tx: dict[str, Any],
        expected_token: str,
        expected_amount: float | None,
        rel_tol: float,
    ) -> dict[str, Any] | None:
        path = self.trace_settlement_path(
            settlement_tx, expected_token, expected_amount, rel_tol
        )
        return path[-1] if path else None

    def trace_deposit_path(
        self,
        deposit_tx: dict[str, Any],
        expected_token: str,
        expected_amount: float | None,
        rel_tol: float,
    ) -> list[dict[str, Any]]:
        """Hops before hot-wallet deposit (closest to user first)."""
        path: list[dict[str, Any]] = []
        anchor_ts = int(deposit_tx.get("timestamp", 0))
        current_addr = _normalize_tron_address(deposit_tx.get("from"))
        if not current_addr or anchor_ts <= 0:
            return path

        amount = expected_amount
        for _ in range(self.cfg.max_depth):
            min_ts = max(anchor_ts - self.cfg.hop_window_ms, 0)
            candidates = self._fetch_transfers(current_addr, min_ts, anchor_ts, expected_token)
            hop = _pick_best(
                candidates,
                target_ts=anchor_ts,
                time_window_ms=self.cfg.hop_window_ms,
                expected_amount=amount,
                rel_tol=rel_tol,
                direction=("to", current_addr),
            )
            if hop is None:
                break
            path.append(hop)
            current_addr = _normalize_tron_address(hop.get("from"))
            anchor_ts = int(hop.get("timestamp", 0))
            amount = _safe_float(hop.get("amount"))
            if not current_addr:
                break
        return path

    def trace_settlement_path(
        self,
        settlement_tx: dict[str, Any],
        expected_token: str,
        expected_amount: float | None,
        rel_tol: float,
    ) -> list[dict[str, Any]]:
        """Hops after hot-wallet settlement (farthest from hot-wallet last)."""
        path: list[dict[str, Any]] = []
        anchor_ts = int(settlement_tx.get("timestamp", 0))
        current_addr = _normalize_tron_address(settlement_tx.get("to"))
        if not current_addr or anchor_ts <= 0:
            return path

        amount = expected_amount
        for _ in range(self.cfg.max_depth):
            max_ts = anchor_ts + self.cfg.hop_window_ms
            candidates = self._fetch_transfers(current_addr, anchor_ts, max_ts, expected_token)
            hop = _pick_best(
                candidates,
                target_ts=anchor_ts,
                time_window_ms=self.cfg.hop_window_ms,
                expected_amount=amount,
                rel_tol=rel_tol,
                direction=("from", current_addr),
            )
            if hop is None:
                break
            path.append(hop)
            current_addr = _normalize_tron_address(hop.get("to"))
            anchor_ts = int(hop.get("timestamp", 0))
            amount = _safe_float(hop.get("amount"))
            if not current_addr:
                break
        return path

    def _fetch_transfers(
        self, address: str, min_ts: int, max_ts: int, expected_token: str
    ) -> list[dict[str, Any]]:
        key = (address, min_ts, max_ts, expected_token.upper())
        if key in self._cache:
            return self._cache[key]

        rows: list[dict[str, Any]] = []
        try:
            rows.extend(_normalize_trx_rows(self.client.fetch_trx_transfers(address, min_ts, max_ts)))
        except Exception:
            logger.exception("TRX fetch failed for %s", address)
        try:
            rows.extend(
                _normalize_trc20_rows(
                    self.client.fetch_trc20_transfers(address, min_ts, max_ts)
                )
            )
        except Exception:
            logger.exception("TRC20 fetch failed for %s", address)

        token_u = expected_token.upper()
        filtered = [r for r in rows if str(r.get("token") or "").upper() == token_u]
        for r in filtered:
            r["from"] = _normalize_tron_address(r.get("from"))
            r["to"] = _normalize_tron_address(r.get("to"))
        self._cache[key] = filtered
        return filtered


# Backward-compatible alias
OneHopTracer = TronMultiHopTracer


def _normalize_trc20_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for tx in rows:
        try:
            amount = _safe_float(tx.get("value"))
            decimals = _safe_float((tx.get("token_info") or {}).get("decimals"))
            if amount is None:
                continue
            if decimals is None:
                decimals = 0.0
            amount_norm = float(amount / (10 ** int(decimals)))
            out.append(
                {
                    "timestamp": int(tx.get("block_timestamp") or 0),
                    "token": (tx.get("token_info") or {}).get("symbol"),
                    "amount": amount_norm,
                    "from": tx.get("from"),
                    "to": tx.get("to"),
                    "tx_hash": tx.get("transaction_id"),
                    "network": "tron",
                    "raw": tx,
                }
            )
        except Exception:
            continue
    return out


def _normalize_trx_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for tx in rows:
        try:
            contract = ((tx.get("raw_data") or {}).get("contract") or [None])[0] or {}
            if contract.get("type") != "TransferContract":
                continue
            val = ((contract.get("parameter") or {}).get("value")) or {}
            amount_sun = _safe_float(val.get("amount"))
            if amount_sun is None:
                continue
            owner = val.get("owner_address")
            to_addr = val.get("to_address")
            out.append(
                {
                    "timestamp": int(tx.get("block_timestamp") or 0),
                    "token": "TRX",
                    "amount": float(amount_sun / 1_000_000),
                    "from": owner,
                    "to": to_addr,
                    "tx_hash": tx.get("txID"),
                    "network": "tron",
                    "raw": tx,
                }
            )
        except Exception:
            continue
    return out


def _pick_best(
    candidates: list[dict[str, Any]],
    target_ts: int,
    time_window_ms: int,
    expected_amount: float | None,
    rel_tol: float,
    direction: tuple[str, str],
) -> dict[str, Any] | None:
    field, addr = direction
    addr_l = str(addr).lower()
    best: dict[str, Any] | None = None
    best_score = -1.0
    for tx in candidates:
        if str(tx.get(field) or "").lower() != addr_l:
            continue
        ts = int(tx.get("timestamp") or 0)
        if ts <= 0 or abs(ts - target_ts) > time_window_ms:
            continue
        amt = _safe_float(tx.get("amount"))
        if expected_amount is not None and not _amount_close(expected_amount, amt, rel_tol):
            continue
        s = 0.6 * _score_time(ts - target_ts, time_window_ms) + 0.4 * _score_amount(
            expected_amount, amt, rel_tol
        )
        if s > best_score:
            best_score = s
            best = tx
    return best
