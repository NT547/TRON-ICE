"""Export XGBoost training pairs from ground-truth results."""

from __future__ import annotations

import json
import random
from decimal import Decimal
from pathlib import Path
from typing import Any


def _slim_tx(tx: dict[str, Any] | None) -> dict[str, Any] | None:
    if tx is None:
        return None
    amount = tx.get("amount")
    if isinstance(amount, Decimal):
        amount = float(amount)
    return {
        "timestamp": int(tx["timestamp"]),
        "token": tx.get("token"),
        "amount": float(amount) if amount is not None else None,
        "from": tx.get("from"),
        "to": tx.get("to"),
        "tx_hash": tx.get("tx_hash") or tx.get("txid"),
        "network": tx.get("network", "tron"),
    }


def export_training_pairs(
    ground_truth_records: list[dict[str, Any]],
    deposits_pool: list[dict[str, Any]],
    withdrawals_pool: list[dict[str, Any]],
    output_path: Path,
    *,
    min_match_score: float = 0.3,
    negatives_per_positive: int = 3,
    seed: int = 42,
) -> dict[str, int]:
    """
    Write JSONL training rows: {deposit, withdrawal, label, match_score, service, history_id}.

    Positives: full H<->D<->W matches from ground-truth.
    Negatives: random deposit-withdrawal pairs (filtered to avoid near-matches).
    """
    rng = random.Random(seed)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    positives: list[dict[str, Any]] = []
    used_pairs: set[tuple[str | None, str | None]] = set()

    for rec in ground_truth_records:
        if rec.get("label") != 1 and rec.get("match_score", 0) < min_match_score:
            continue
        dep = _slim_tx(rec.get("_deposit_full") or rec.get("deposit"))
        wit = _slim_tx(rec.get("_settlement_full") or rec.get("settlement"))
        if not dep or not wit:
            continue
        dep_h = dep.get("tx_hash") or dep.get("txid")
        wit_h = wit.get("tx_hash") or wit.get("txid")
        used_pairs.add((dep_h, wit_h))
        positives.append(
            {
                "deposit": dep,
                "withdrawal": wit,
                "label": 1,
                "match_score": rec.get("match_score", 1.0),
                "service": rec.get("service"),
                "shift_timestamp": (rec.get("history") or {}).get("shift_timestamp"),
            }
        )

    stats = {"positives": len(positives), "negatives": 0}
    default_service = positives[0].get("service") if positives else None

    with output_path.open("w", encoding="utf-8") as f:
        for row in positives:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

        if negatives_per_positive > 0 and deposits_pool and withdrawals_pool:
            target_neg = max(len(positives) * negatives_per_positive, 0)
            if target_neg == 0 and len(positives) == 0:
                target_neg = min(1000, len(deposits_pool))
            attempts = 0
            max_attempts = max(target_neg * 20, 1)
            while stats["negatives"] < target_neg and attempts < max_attempts:
                attempts += 1
                d = _slim_tx(rng.choice(deposits_pool))
                w = _slim_tx(rng.choice(withdrawals_pool))
                if not d or not w:
                    continue
                if d.get("token") != w.get("token"):
                    continue
                pair = (d.get("tx_hash") or d.get("txid"), w.get("tx_hash") or w.get("txid"))
                if pair in used_pairs:
                    continue
                dt, wt = int(d.get("timestamp", 0)), int(w.get("timestamp", 0))
                if wt <= dt or (wt - dt) > 7200 * 1000:
                    continue
                row = {
                    "deposit": d,
                    "withdrawal": w,
                    "label": 0,
                    "match_score": 0.0,
                    "service": default_service,
                    "shift_timestamp": None,
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                stats["negatives"] += 1

    return stats

