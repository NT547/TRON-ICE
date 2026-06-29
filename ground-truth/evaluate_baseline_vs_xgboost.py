"""Compare baseline rule matching with trained XGBoost on labeled pair data.

Example:
  python ground-truth/evaluate_baseline_vs_xgboost.py \
    --service sideshift \
    --year 2026 \
    --training-jsonl ground-truth/output/training_pairs_sideshift_2026_strict_multichain.jsonl \
    --model ground-truth/models/xgboost_sideshift_2026_crosschain.pkl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split

GT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = GT_ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.tron_ice.features.xgboost_features import extract_features  # noqa: E402


def _load_training_jsonl(path: Path) -> tuple[list[dict[str, Any]], np.ndarray]:
    pairs: list[dict[str, Any]] = []
    labels: list[int] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            dep = row.get("deposit")
            wit = row.get("withdrawal")
            if not dep or not wit:
                continue
            pairs.append({"deposit": dep, "withdrawal": wit})
            labels.append(int(row.get("label", 0)))
    return pairs, np.array(labels, dtype=np.int32)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _ensure_usd(pair: dict[str, Any]) -> None:
    for side in ("deposit", "withdrawal"):
        tx = pair[side]
        if tx.get("usd_value") in (None, 0.0):
            tx["usd_value"] = _safe_float(tx.get("amount"))


def _baseline_predict(
    pairs: list[dict[str, Any]],
    *,
    max_time_diff: int,
    max_rv: float,
    same_token_only: bool,
    same_chain_only: bool,
) -> np.ndarray:
    preds: list[int] = []
    for pair in pairs:
        d = pair["deposit"]
        w = pair["withdrawal"]
        td = int(d["timestamp"])
        tw = int(w["timestamp"])
        delta_t = (tw - td) / 1000.0
        if delta_t <= 0 or delta_t > max_time_diff:
            preds.append(0)
            continue

        if same_token_only and str(d.get("token") or "").upper() != str(w.get("token") or "").upper():
            preds.append(0)
            continue

        d_chain = str(d.get("chain") or d.get("network") or "").lower()
        w_chain = str(w.get("chain") or w.get("network") or "").lower()
        if same_chain_only and d_chain != w_chain:
            preds.append(0)
            continue

        vd = _safe_float(d.get("usd_value"))
        vw = _safe_float(w.get("usd_value"))
        rv = abs(vd - vw) / max(abs(vd), abs(vw), 1e-12)
        preds.append(1 if rv <= max_rv else 0)

    return np.array(preds, dtype=np.int32)


def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
    }


def _print_table(rows: list[tuple[str, dict[str, float]]]) -> None:
    print("| Method | Accuracy | Precision | Recall | F1 |")
    print("|---|---:|---:|---:|---:|")
    for name, m in rows:
        print(
            f"| {name} | {m['accuracy'] * 100:.1f}% | {m['precision'] * 100:.1f}% | "
            f"{m['recall'] * 100:.1f}% | {m['f1'] * 100:.1f}% |"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate baseline rule vs XGBoost on labeled pairs")
    parser.add_argument("--service", required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--training-jsonl", type=Path, default=None)
    parser.add_argument("--model", type=Path, default=None)
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--baseline-max-time-diff", type=int, default=7200)
    parser.add_argument("--baseline-max-rv", type=float, default=0.2)
    parser.add_argument("--baseline-same-token-only", action="store_true")
    parser.add_argument("--baseline-same-chain-only", action="store_true")
    args = parser.parse_args()

    suffix = f"{args.service}_{args.year}"
    training_path = args.training_jsonl or GT_ROOT / "output" / f"training_pairs_{suffix}.jsonl"
    model_path = args.model or GT_ROOT / "models" / f"xgboost_{suffix}.pkl"

    pairs, y = _load_training_jsonl(training_path)
    if len(pairs) < 2:
        raise SystemExit(f"Too few labeled pairs: {len(pairs)}")
    if len(np.unique(y)) < 2:
        raise SystemExit("Evaluation requires both positive and negative labels.")
    if not model_path.exists():
        raise SystemExit(f"Model not found: {model_path}")

    for pair in pairs:
        _ensure_usd(pair)

    indices = np.arange(len(pairs))
    _, test_idx, _, y_test = train_test_split(
        indices,
        y,
        test_size=args.test_size,
        random_state=args.seed,
        stratify=y,
    )
    test_pairs = [pairs[int(i)] for i in test_idx]

    baseline_pred = _baseline_predict(
        test_pairs,
        max_time_diff=args.baseline_max_time_diff,
        max_rv=args.baseline_max_rv,
        same_token_only=args.baseline_same_token_only,
        same_chain_only=args.baseline_same_chain_only,
    )

    bundle = joblib.load(model_path)
    model = bundle["model"] if isinstance(bundle, dict) else bundle
    xgb_pred = model.predict(extract_features(test_pairs))

    print(f"Training file: {training_path}")
    print(f"Model: {model_path}")
    print(
        f"Rows: {len(pairs)} | Positives: {int(y.sum())} | Negatives: {int((1 - y).sum())} | "
        f"Holdout: {len(test_pairs)}"
    )
    print(
        "Baseline rule: "
        f"delta_t<= {args.baseline_max_time_diff}s, rv<= {args.baseline_max_rv}, "
        f"same_token_only={args.baseline_same_token_only}, "
        f"same_chain_only={args.baseline_same_chain_only}"
    )
    _print_table(
        [
            ("Baseline Rule", _metrics(y_test, baseline_pred)),
            ("XGBoost", _metrics(y_test, xgb_pred)),
        ]
    )


if __name__ == "__main__":
    main()
