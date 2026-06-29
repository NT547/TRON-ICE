from __future__ import annotations

import argparse
import bisect
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

GT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = GT_ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.utils.multichain_config import canonical_chain


def _load_json(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _history_time_ms(h: dict[str, Any]) -> int | None:
    from datetime import datetime

    ts = h.get("shift_timestamp") or (h.get("raw") or {}).get("createdAt")
    if not isinstance(ts, str):
        return None
    try:
        return int(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() * 1000)
    except Exception:
        return None


def _safe_float(x: Any) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _token(value: Any) -> str:
    return str(value or "").upper()


def _amount_close(a: float | None, b: float | None, rel_tol: float, abs_tol: float) -> bool:
    if a is None or b is None:
        return False
    return abs(a - b) <= max(abs_tol, abs(a) * rel_tol)


def _public_tx(tx: dict[str, Any] | None) -> dict[str, Any] | None:
    if tx is None:
        return None
    return {
        "chain": tx.get("chain") or tx.get("network"),
        "timestamp": tx.get("timestamp"),
        "token": tx.get("token"),
        "amount": tx.get("amount"),
        "from": tx.get("from"),
        "to": tx.get("to"),
        "tx_hash": tx.get("tx_hash") or tx.get("txid"),
    }


def _training_tx(tx: dict[str, Any]) -> dict[str, Any]:
    amount = float(tx.get("amount") or 0.0)
    txid = str(tx.get("tx_hash") or tx.get("txid") or f"{tx.get('from')}_{tx.get('timestamp')}_{tx.get('to')}")
    return {
        "timestamp": int(tx["timestamp"]),
        "token": _token(tx.get("token")),
        "amount": amount,
        "usd_value": float(tx.get("usd_value") or amount),
        "from": tx.get("from"),
        "to": tx.get("to"),
        "tx_hash": txid,
        "txid": txid,
        "network": tx.get("chain") or tx.get("network"),
        "chain": tx.get("chain") or tx.get("network"),
    }


def export_training_pairs(
    results: list[dict[str, Any]],
    output_path: Path,
    *,
    negatives_per_positive: int = 3,
    seed: int = 42,
) -> dict[str, int]:
    rng = random.Random(seed)
    rows = []
    positive_deposits = []
    positive_withdrawals = []
    used_pairs = set()

    for rec in results:
        dep = rec.get("_deposit_full")
        wit = rec.get("_settlement_full")
        if rec.get("label") != 1 or not dep or not wit:
            continue
        dep_tx = _training_tx(dep)
        wit_tx = _training_tx(wit)
        pair_key = (dep_tx["txid"], wit_tx["txid"])
        used_pairs.add(pair_key)
        positive_deposits.append(dep_tx)
        positive_withdrawals.append(wit_tx)
        rows.append(
            {
                "deposit": dep_tx,
                "withdrawal": wit_tx,
                "label": 1,
                "label_source": "strict_multichain_history",
                "service": rec.get("service"),
                "shift_timestamp": (rec.get("history") or {}).get("shift_timestamp"),
            }
        )

    target_negatives = len(rows) * max(negatives_per_positive, 0)
    attempts = 0
    max_attempts = max(target_negatives * 50, 1000)
    negatives = 0
    while negatives < target_negatives and attempts < max_attempts:
        attempts += 1
        if not positive_deposits or not positive_withdrawals:
            break
        dep_tx = rng.choice(positive_deposits)
        wit_tx = rng.choice(positive_withdrawals)
        pair_key = (dep_tx["txid"], wit_tx["txid"])
        if pair_key in used_pairs:
            continue
        if int(wit_tx["timestamp"]) <= int(dep_tx["timestamp"]):
            continue
        used_pairs.add(pair_key)
        rows.append(
            {
                "deposit": dep_tx,
                "withdrawal": wit_tx,
                "label": 0,
                "label_source": "strict_multichain_mismatched_pair",
                "service": rows[0].get("service") if rows else None,
                "shift_timestamp": None,
            }
        )
        negatives += 1

    rng.shuffle(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"positives": len(positive_deposits), "negatives": negatives, "rows": len(rows)}


def _normalize_tron_rows(rows: list[dict[str, Any]], chain: str) -> list[dict[str, Any]]:
    out = []
    for tx in rows:
        if not isinstance(tx, dict):
            continue
        tx = dict(tx)
        tx["chain"] = chain
        tx["network"] = chain
        tx["token"] = _token(tx.get("token"))
        tx["tx_hash"] = tx.get("tx_hash") or tx.get("txid") or f"{tx.get('from')}_{tx.get('timestamp')}_{tx.get('to')}"
        out.append(tx)
    return out


@dataclass
class MatchConfig:
    td_sec: int = 1800
    tw_sec: int = 7200
    vd_rel: float = 0.02
    vw_rel: float = 0.03
    abs_tol: float = 1e-9


class MultiChainMatcher:
    def __init__(self, deposits: list[dict[str, Any]], withdrawals: list[dict[str, Any]], cfg: MatchConfig) -> None:
        self.cfg = cfg
        self.deposits = self._index(deposits)
        self.withdrawals = self._index(withdrawals)

    def _index(self, rows: list[dict[str, Any]]) -> dict[tuple[str, str], tuple[list[int], list[dict[str, Any]]]]:
        grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for row in rows:
            chain = canonical_chain(row.get("chain") or row.get("network"))
            token = _token(row.get("token"))
            if not chain or not token or row.get("timestamp") is None:
                continue
            grouped.setdefault((chain, token), []).append(row)
        out = {}
        for key, items in grouped.items():
            items.sort(key=lambda x: int(x["timestamp"]))
            out[key] = ([int(x["timestamp"]) for x in items], items)
        return out

    def _best_deposit(self, h: dict[str, Any]) -> dict[str, Any] | None:
        raw = h.get("raw") if isinstance(h.get("raw"), dict) else {}
        chain = canonical_chain(raw.get("depositNetwork"))
        token = _token(h.get("input_coin"))
        amount = _safe_float(h.get("input_amount"))
        h_ts = _history_time_ms(h)
        if not chain or not token or h_ts is None:
            return None
        indexed = self.deposits.get((chain, token))
        if indexed is None:
            return None
        ts_list, rows = indexed
        lo = bisect.bisect_left(ts_list, h_ts - self.cfg.td_sec * 1000)
        hi = bisect.bisect_right(ts_list, h_ts + self.cfg.td_sec * 1000)
        best = None
        best_score = float("inf")
        for tx in rows[lo:hi]:
            tx_amount = _safe_float(tx.get("amount"))
            if not _amount_close(amount, tx_amount, self.cfg.vd_rel, self.cfg.abs_tol):
                continue
            score = abs(h_ts - int(tx["timestamp"])) / max(self.cfg.td_sec * 1000, 1)
            if amount and tx_amount is not None:
                score += abs(amount - tx_amount) / max(abs(amount), self.cfg.abs_tol)
            if score < best_score:
                best = tx
                best_score = score
        return best

    def _best_withdrawal(self, h: dict[str, Any], deposit: dict[str, Any]) -> dict[str, Any] | None:
        raw = h.get("raw") if isinstance(h.get("raw"), dict) else {}
        chain = canonical_chain(raw.get("settleNetwork"))
        token = _token(h.get("output_coin"))
        amount = _safe_float(h.get("output_amount"))
        dep_ts = int(deposit["timestamp"])
        if not chain or not token:
            return None
        indexed = self.withdrawals.get((chain, token))
        if indexed is None:
            return None
        ts_list, rows = indexed
        lo = bisect.bisect_left(ts_list, dep_ts)
        hi = bisect.bisect_right(ts_list, dep_ts + self.cfg.tw_sec * 1000)
        best = None
        best_score = float("inf")
        for tx in rows[lo:hi]:
            tx_amount = _safe_float(tx.get("amount"))
            if not _amount_close(amount, tx_amount, self.cfg.vw_rel, self.cfg.abs_tol):
                continue
            score = (int(tx["timestamp"]) - dep_ts) / max(self.cfg.tw_sec * 1000, 1)
            if amount and tx_amount is not None:
                score += abs(amount - tx_amount) / max(abs(amount), self.cfg.abs_tol)
            if score < best_score:
                best = tx
                best_score = score
        return best

    def match(self, history: list[dict[str, Any]]) -> list[dict[str, Any]]:
        results = []
        for h in history:
            dep = self._best_deposit(h)
            wit = self._best_withdrawal(h, dep) if dep else None
            results.append(
                {
                    "service": h.get("service"),
                    "history": h,
                    "deposit": _public_tx(dep),
                    "settlement": _public_tx(wit),
                    "label": 1 if dep and wit else 0,
                    "_deposit_full": dep,
                    "_settlement_full": wit,
                }
            )
        return results


def load_multichain_ops(service: str, year: int, include_tron: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    dep: list[dict[str, Any]] = []
    wit: list[dict[str, Any]] = []

    evm_dep = REPO_ROOT / "data" / "classified" / "multichain" / f"deposits_{service}_{year}.json"
    evm_wit = REPO_ROOT / "data" / "classified" / "multichain" / f"withdrawals_{service}_{year}.json"
    dep.extend(_load_json(evm_dep))
    wit.extend(_load_json(evm_wit))

    if include_tron:
        dep.extend(_normalize_tron_rows(_load_json(REPO_ROOT / "data" / "classified" / f"deposits_trongrid_{service}_{year}.json"), "tron"))
        wit.extend(_normalize_tron_rows(_load_json(REPO_ROOT / "data" / "classified" / f"withdrawals_trongrid_{service}_{year}.json"), "tron"))

    return dep, wit


def main() -> None:
    parser = argparse.ArgumentParser(description="Build strict multichain H-D-W ground truth")
    parser.add_argument("--service", required=True, choices=["sideshift", "fixedfloat", "changenow"])
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--history-jsonl", type=Path, default=None)
    parser.add_argument("--td-sec", type=int, default=1800)
    parser.add_argument("--tw-sec", type=int, default=7200)
    parser.add_argument("--vd-rel", type=float, default=0.02)
    parser.add_argument("--vw-rel", type=float, default=0.03)
    parser.add_argument("--no-tron", action="store_true")
    parser.add_argument("--export-training", action="store_true")
    parser.add_argument("--training-jsonl", type=Path, default=None)
    parser.add_argument("--negatives-per-positive", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-json", type=Path, default=None)
    parser.add_argument("--out-jsonl", type=Path, default=None)
    args = parser.parse_args()

    history_path = args.history_jsonl or REPO_ROOT / "src" / "off-chain" / "output" / f"{args.service}_recent_deposits.jsonl"
    if args.service == "fixedfloat" and args.history_jsonl is None:
        history_path = REPO_ROOT / "src" / "off-chain" / "output" / "fixedfloat_recent_requests.jsonl"
    if args.service == "changenow" and args.history_jsonl is None:
        history_path = REPO_ROOT / "src" / "off-chain" / "output" / "changenow_recent_requests.jsonl"

    history = _load_jsonl(history_path)
    history = [{**h, "service": h.get("service", args.service)} for h in history]
    deposits, withdrawals = load_multichain_ops(args.service, args.year, include_tron=not args.no_tron)

    matcher = MultiChainMatcher(
        deposits,
        withdrawals,
        MatchConfig(td_sec=args.td_sec, tw_sec=args.tw_sec, vd_rel=args.vd_rel, vw_rel=args.vw_rel),
    )
    results = matcher.match(history)

    out_json = args.out_json or GT_ROOT / "result" / f"ground_truth_{args.service}_{args.year}_multichain.json"
    out_jsonl = args.out_jsonl or GT_ROOT / "output" / f"ground_truth_{args.service}_{args.year}_multichain.jsonl"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    with out_jsonl.open("w", encoding="utf-8") as f:
        for row in results:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    matched_deposit = sum(1 for r in results if r["deposit"])
    matched_full = sum(1 for r in results if r["label"] == 1)
    summary = {
        "history": len(history),
        "deposits": len(deposits),
        "withdrawals": len(withdrawals),
        "matched_deposit": matched_deposit,
        "matched_full": matched_full,
        "out_json": str(out_json),
        "out_jsonl": str(out_jsonl),
    }
    if args.export_training:
        training_path = args.training_jsonl or GT_ROOT / "output" / f"training_pairs_{args.service}_{args.year}_strict_multichain.jsonl"
        summary["training_stats"] = export_training_pairs(
            results,
            training_path,
            negatives_per_positive=args.negatives_per_positive,
            seed=args.seed,
        )
        summary["training_jsonl"] = str(training_path)
    print(summary)


if __name__ == "__main__":
    main()
