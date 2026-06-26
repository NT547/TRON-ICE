"""
Score deposit-withdrawal candidate pairs with a trained XGBoost .pkl model.

Usage:
  python ground-truth/predict_xgboost.py --service sideshift --year 2025
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

import joblib
import numpy as np

GT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = GT_ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(GT_ROOT) not in sys.path:
    sys.path.insert(0, str(GT_ROOT))

from src.xgboost.candidate_generator import generate_candidates
from src.xgboost.feature_engineering import extract_features
from src.xgboost.matcher import greedy_matcher
from src.xgboost.predictor import predict_proba

from src_ground_truth.io import load_tron_classified_json
from src_ground_truth.paths import tron_classified_paths


def _load_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Expected list in {path}")
    return [x for x in data if isinstance(x, dict)]


def _txid(tx: dict[str, Any]) -> str:
    return str(
        tx.get("txid")
        or tx.get("tx_hash")
        or tx.get("hash")
        or f"{tx.get('from')}_{tx.get('timestamp')}_{tx.get('to')}"
    )


def _normalize_prediction_tx(tx: dict[str, Any], default_chain: str | None = None) -> dict[str, Any]:
    amount = float(tx.get("amount") or 0.0)
    chain = tx.get("chain") or tx.get("network") or default_chain
    txid = _txid(tx)
    return {
        "timestamp": int(tx["timestamp"]),
        "token": str(tx.get("token") or "").upper(),
        "amount": amount,
        # Strict multichain training currently uses raw amount when explicit
        # pricing is absent. Keep prediction aligned with that feature scale.
        "usd_value": float(tx.get("usd_value") or amount),
        "from": tx.get("from"),
        "to": tx.get("to"),
        "tx_hash": txid,
        "txid": txid,
        "network": chain,
        "chain": chain,
    }


def _load_prediction_inputs(service: str, year: int, include_tron: bool = True) -> tuple[list, list]:
    deposits: list[dict[str, Any]] = []
    withdrawals: list[dict[str, Any]] = []

    multichain_dep = REPO_ROOT / "data" / "classified" / "multichain" / f"deposits_{service}_{year}.json"
    multichain_wit = REPO_ROOT / "data" / "classified" / "multichain" / f"withdrawals_{service}_{year}.json"
    deposits.extend(_normalize_prediction_tx(tx) for tx in _load_json_list(multichain_dep))
    withdrawals.extend(_normalize_prediction_tx(tx) for tx in _load_json_list(multichain_wit))

    if include_tron:
        dep_p, wit_p = tron_classified_paths(service, year)
        deposits.extend(_normalize_prediction_tx(tx, default_chain="tron") for tx in load_tron_classified_json(dep_p))
        withdrawals.extend(_normalize_prediction_tx(tx, default_chain="tron") for tx in load_tron_classified_json(wit_p))

    return deposits, withdrawals


def _load_priced_or_classified(service: str, year: int) -> tuple[list, list]:
    # Backward-compatible wrapper: prediction now uses the same multichain +
    # TRON classified universe as strict ground-truth generation.
    return _load_prediction_inputs(service, year)
    dep_p, wit_p = tron_classified_paths(service, year)
    return load_tron_classified_json(dep_p), load_tron_classified_json(wit_p)


def ensure_usd(tx: dict, year: int, cache_dir: str) -> None:
    if tx.get("usd_value") not in (None, 0.0):
        return
    try:
        from src.baseline_algorithm.price_calculator import calculate_usd_value

        tx["usd_value"] = calculate_usd_value(tx, year, cache_dir=cache_dir, api_key=None)
    except Exception:
        tx["usd_value"] = float(tx.get("amount") or 0.0)


def ensure_txid(tx: dict) -> None:
    txid = tx.get("txid") or tx.get("tx_hash") or tx.get("hash")
    if txid is None:
        txid = f"{tx.get('from')}_{tx.get('timestamp')}_{tx.get('to')}"
    tx["txid"] = str(txid)
    tx.setdefault("tx_hash", str(txid))


def main() -> None:
    parser = argparse.ArgumentParser(description="Predict ICE pairs with trained XGBoost model")
    parser.add_argument("--service", required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--model", type=Path, default=None)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--max-time-diff", type=int, default=600)
    parser.add_argument("--max-rv", type=float, default=0.15)
    parser.add_argument("--cache-dir", default="cache")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Default: ground-truth/result/xgboost_predict_{service}_{year}.json",
    )
    args = parser.parse_args()

    suffix = f"{args.service}_{args.year}"
    model_path = args.model or GT_ROOT / "models" / f"xgboost_{suffix}.pkl"
    output_path = args.output or GT_ROOT / "result" / f"xgboost_predict_{suffix}.json"

    if not model_path.exists():
        raise SystemExit(f"Model not found: {model_path}. Run train_xgboost.py first.")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger = logging.getLogger("predict_xgboost")

    bundle = joblib.load(model_path)
    model = bundle["model"] if isinstance(bundle, dict) else bundle

    deposits, withdrawals = _load_priced_or_classified(args.service, args.year)
    for tx in deposits:
        ensure_usd(tx, args.year, args.cache_dir)
        ensure_txid(tx)
    for tx in withdrawals:
        ensure_usd(tx, args.year, args.cache_dir)
        ensure_txid(tx)

    candidates = generate_candidates(
        deposits, withdrawals, max_time_diff=args.max_time_diff, max_rv=args.max_rv
    )
    logger.info("Candidates: %s", len(candidates))
    if not candidates:
        raise SystemExit("No candidates generated.")

    X = extract_features(candidates)
    scores = predict_proba(model, X)
    matches = greedy_matcher(
        deposits,
        withdrawals,
        candidates,
        scores,
        threshold=args.threshold,
        output_file=str(output_path),
    )
    logger.info("Saved %s matches to %s", len(matches), output_path)


if __name__ == "__main__":
    main()
