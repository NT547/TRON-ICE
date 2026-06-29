"""
Train XGBoost matcher from ground-truth training pairs and save .pkl model.

Usage:
  python ground-truth/train_xgboost.py --service sideshift --year 2025
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split

GT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = GT_ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.tron_ice.features.xgboost_features import FEATURE_NAMES, extract_features  # noqa: E402

try:
    import xgboost as xgb
except ImportError as exc:
    raise SystemExit("Install xgboost: pip install xgboost") from exc


def load_training_jsonl(path: Path) -> tuple[list[dict], np.ndarray]:
    pairs: list[dict] = []
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


def ensure_usd_value(tx: dict, year: int, cache_dir: str) -> None:
    if tx.get("usd_value") not in (None, 0.0):
        return
    try:
        from src.tron_ice.normalization.pricing import calculate_usd_value

        tx["usd_value"] = calculate_usd_value(tx, year, cache_dir=cache_dir, api_key=None)
    except Exception:
        tx["usd_value"] = float(tx.get("amount") or 0.0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train XGBoost ICE matcher and save .pkl")
    parser.add_argument("--service", type=str, required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument(
        "--training-jsonl",
        type=Path,
        default=None,
        help="Default: ground-truth/output/training_pairs_{service}_{year}.jsonl",
    )
    parser.add_argument(
        "--model-out",
        type=Path,
        default=None,
        help="Default: ground-truth/models/xgboost_{service}_{year}.pkl",
    )
    parser.add_argument("--cache-dir", type=str, default="cache")
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    suffix = f"{args.service}_{args.year}"
    training_path = args.training_jsonl or GT_ROOT / "output" / f"training_pairs_{suffix}.jsonl"
    model_path = args.model_out or GT_ROOT / "models" / f"xgboost_{suffix}.pkl"
    log_path = GT_ROOT / "log" / f"train_xgboost_{suffix}.log"

    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
        force=True,
    )
    logger = logging.getLogger("train_xgboost")

    if not training_path.exists():
        raise SystemExit(
            f"Training file not found: {training_path}\n"
            "Run ground-truth first with --export-training"
        )

    pairs, y = load_training_jsonl(training_path)
    if len(pairs) < 10:
        raise SystemExit(f"Too few training pairs: {len(pairs)}")

    for p in pairs:
        ensure_usd_value(p["deposit"], args.year, args.cache_dir)
        ensure_usd_value(p["withdrawal"], args.year, args.cache_dir)

    X = extract_features(pairs)
    logger.info("Features shape=%s labels: pos=%s neg=%s", X.shape, int(y.sum()), int((1 - y).sum()))

    if len(np.unique(y)) < 2:
        raise SystemExit(
            "Training data must contain both positive and negative labels. "
            "For strict multichain data, rebuild with "
            "ground-truth/run_multichain_ground_truth.py --export-training "
            "--negatives-per-positive 3."
        )

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=args.test_size, random_state=args.seed, stratify=y if len(np.unique(y)) > 1 else None
    )

    pos = max(int(y_train.sum()), 1)
    neg = max(len(y_train) - pos, 1)
    scale_pos_weight = neg / pos

    model = xgb.XGBClassifier(
        max_depth=5,
        learning_rate=0.1,
        n_estimators=150,
        objective="binary:logistic",
        scale_pos_weight=scale_pos_weight,
        eval_metric="logloss",
    )
    model.fit(X_train, y_train)
    if len(y_test):
        y_pred = model.predict(X_test)
        acc = accuracy_score(y_test, y_pred)
        precision = precision_score(y_test, y_pred, zero_division=0)
        recall = recall_score(y_test, y_pred, zero_division=0)
        f1 = f1_score(y_test, y_pred, zero_division=0)
    else:
        acc = precision = recall = f1 = 0.0
    logger.info(
        "Holdout metrics: accuracy=%.4f precision=%.4f recall=%.4f f1=%.4f",
        acc,
        precision,
        recall,
        f1,
    )

    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "service": args.service,
            "year": args.year,
            "feature_names": FEATURE_NAMES,
        },
        model_path,
    )
    logger.info("Saved model to %s", model_path)


if __name__ == "__main__":
    main()
