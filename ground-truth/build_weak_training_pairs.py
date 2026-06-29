"""Build weakly supervised XGBoost training pairs from classified TRON txs.

This is a pragmatic fallback when strict off-chain ground truth is too sparse.
Labels are heuristic:
  - positive: same-token D->W pair within a tight time/value window
  - negative: same-token D->W pair with clearly bad time or value relation
"""

from __future__ import annotations

import argparse
import bisect
import json
import random
from pathlib import Path
from typing import Any


GT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = GT_ROOT.parent


def _load_json(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Expected list in {path}")
    return [x for x in data if isinstance(x, dict)]


def _txid(tx: dict[str, Any]) -> str:
    return str(tx.get("tx_hash") or tx.get("txid") or f"{tx.get('from')}_{tx.get('timestamp')}_{tx.get('to')}")


def _slim(tx: dict[str, Any]) -> dict[str, Any]:
    amount = float(tx.get("amount") or 0.0)
    return {
        "timestamp": int(tx["timestamp"]),
        "token": str(tx.get("token") or "").upper(),
        "amount": amount,
        "usd_value": float(tx.get("usd_value") or amount),
        "from": tx.get("from"),
        "to": tx.get("to"),
        "tx_hash": _txid(tx),
        "txid": _txid(tx),
        "network": tx.get("network", "tron"),
    }


def _rv(a: float, b: float) -> float:
    return abs(a - b) / max(abs(a), abs(b), 1e-12)


def _index_by_token(rows: list[dict[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[int]]]:
    by_token: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_token.setdefault(row["token"], []).append(row)
    ts_by_token: dict[str, list[int]] = {}
    for token, token_rows in by_token.items():
        token_rows.sort(key=lambda x: x["timestamp"])
        ts_by_token[token] = [int(x["timestamp"]) for x in token_rows]
    return by_token, ts_by_token


def build_pairs(
    deposits: list[dict[str, Any]],
    withdrawals: list[dict[str, Any]],
    *,
    positive_window_sec: int,
    positive_max_rv: float,
    negatives_per_positive: int,
    max_positives: int,
    seed: int,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rng = random.Random(seed)
    deps = [_slim(d) for d in deposits if d.get("timestamp") and d.get("token")]
    wits = [_slim(w) for w in withdrawals if w.get("timestamp") and w.get("token")]
    wit_by_token, wit_ts_by_token = _index_by_token(wits)

    positives: list[dict[str, Any]] = []
    used_pairs: set[tuple[str, str]] = set()

    for dep in sorted(deps, key=lambda x: x["timestamp"]):
        token_wits = wit_by_token.get(dep["token"], [])
        token_ts = wit_ts_by_token.get(dep["token"], [])
        if not token_wits:
            continue
        lo = bisect.bisect_right(token_ts, dep["timestamp"])
        hi = bisect.bisect_right(token_ts, dep["timestamp"] + positive_window_sec * 1000)

        best: dict[str, Any] | None = None
        best_score = float("inf")
        for wit in token_wits[lo:hi]:
            value_rv = _rv(dep["usd_value"], wit["usd_value"])
            if value_rv > positive_max_rv:
                continue
            dt = (wit["timestamp"] - dep["timestamp"]) / 1000
            score = value_rv + (dt / max(positive_window_sec, 1))
            if score < best_score:
                best = wit
                best_score = score

        if best is None:
            continue
        pair_key = (dep["tx_hash"], best["tx_hash"])
        if pair_key in used_pairs:
            continue
        used_pairs.add(pair_key)
        positives.append(
            {
                "deposit": dep,
                "withdrawal": best,
                "label": 1,
                "label_source": "weak_same_token_time_value",
                "match_score": round(max(0.0, 1.0 - best_score), 6),
            }
        )
        if len(positives) >= max_positives:
            break

    negatives: list[dict[str, Any]] = []
    target_negatives = len(positives) * negatives_per_positive
    attempts = 0
    max_attempts = max(target_negatives * 50, 1000)
    while len(negatives) < target_negatives and attempts < max_attempts and deps and wits:
        attempts += 1
        dep = rng.choice(deps)
        same_token_wits = wit_by_token.get(dep["token"], [])
        if not same_token_wits:
            continue
        wit = rng.choice(same_token_wits)
        dt_sec = (wit["timestamp"] - dep["timestamp"]) / 1000
        value_rv = _rv(dep["usd_value"], wit["usd_value"])
        if dt_sec <= 0:
            continue
        if dt_sec > 0 and dt_sec <= positive_window_sec and value_rv <= positive_max_rv:
            continue
        pair_key = (dep["tx_hash"], wit["tx_hash"])
        if pair_key in used_pairs:
            continue
        used_pairs.add(pair_key)
        negatives.append(
            {
                "deposit": dep,
                "withdrawal": wit,
                "label": 0,
                "label_source": "weak_same_token_hard_negative",
                "match_score": 0.0,
            }
        )

    rows = positives + negatives
    rng.shuffle(rows)
    return rows, {"positives": len(positives), "negatives": len(negatives), "rows": len(rows)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build weak XGBoost training JSONL from classified txs")
    parser.add_argument("--service", required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--positive-window-sec", type=int, default=7200)
    parser.add_argument("--positive-max-rv", type=float, default=0.08)
    parser.add_argument("--negatives-per-positive", type=int, default=3)
    parser.add_argument("--max-positives", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    deposits_path = REPO_ROOT / f"data/classified/deposits_trongrid_{args.service}_{args.year}.json"
    withdrawals_path = REPO_ROOT / f"data/classified/withdrawals_trongrid_{args.service}_{args.year}.json"
    output_path = args.output or GT_ROOT / "output" / f"training_pairs_{args.service}_{args.year}_weak.jsonl"

    rows, stats = build_pairs(
        _load_json(deposits_path),
        _load_json(withdrawals_path),
        positive_window_sec=args.positive_window_sec,
        positive_max_rv=args.positive_max_rv,
        negatives_per_positive=args.negatives_per_positive,
        max_positives=args.max_positives,
        seed=args.seed,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print({"output": str(output_path), **stats})


if __name__ == "__main__":
    main()
