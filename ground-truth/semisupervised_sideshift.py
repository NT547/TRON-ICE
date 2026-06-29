"""Temporal semi-supervised SideShift experiment.

This script intentionally treats strict rule labels as seed labels, not as
absolute ground truth. It is meant to reduce circularity in the XGBoost
experiment by:
  - limiting the dataset to SideShift in the configured crawl window,
  - splitting train/test by off-chain calendar days,
  - using strict rule matches only as initial seeds,
  - iteratively adding high-confidence pseudo-labels,
  - evaluating on a temporal holdout with a realistic negative ratio, and
  - exporting high-confidence discoveries missed by the baseline rule.
"""

from __future__ import annotations

import argparse
import bisect
import json
import math
import random
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
)

try:
    import xgboost as xgb
except ImportError as exc:
    raise SystemExit("Install xgboost: pip install xgboost") from exc

GT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = GT_ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.tron_ice.candidates.generator import generate_candidates  # noqa: E402
from src.tron_ice.features.xgboost_features import FEATURE_NAMES, extract_features  # noqa: E402
from src.tron_ice.ground_truth.io import load_history_jsonl, load_tron_classified_json  # noqa: E402
from src.tron_ice.ground_truth.match import history_time_ms  # noqa: E402
from src.tron_ice.ground_truth.paths import offchain_history_path, tron_classified_paths  # noqa: E402
from src.utils.multichain_config import canonical_chain  # noqa: E402


SERVICE = "sideshift"
DEFAULT_COLLECTION_PRIORITY = (
    "ethereum",
    "solana",
    "liquid",
    "bitcoin",
    "bsc",
    "polygon",
    "tron",
)
DEFAULT_OBSERVABLE_CHAINS = ("ethereum", "bsc", "polygon", "tron")


@dataclass(frozen=True)
class DateWindow:
    start: date
    end: date

    @property
    def start_ms(self) -> int:
        return _dt_ms(datetime.combine(self.start, time.min, tzinfo=timezone.utc))

    @property
    def end_ms(self) -> int:
        return _dt_ms(datetime.combine(self.end, time.max, tzinfo=timezone.utc))

    def contains_ms(self, ts_ms: int) -> bool:
        return self.start_ms <= ts_ms <= self.end_ms


def _dt_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _utc_day_from_ms(ts_ms: int) -> date:
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).date()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _token(value: Any) -> str:
    return str(value or "").strip().upper()


def _network(value: Any) -> str:
    return canonical_chain(str(value or "").strip().lower()) or ""


def _txid(tx: dict[str, Any]) -> str:
    return str(
        tx.get("txid")
        or tx.get("tx_hash")
        or tx.get("hash")
        or f"{tx.get('from')}_{tx.get('timestamp')}_{tx.get('to')}"
    )


def _normalize_tx(tx: dict[str, Any]) -> dict[str, Any]:
    amount = _safe_float(tx.get("amount"))
    network = tx.get("chain") or tx.get("network") or "tron"
    network = _network(network)
    txid = _txid(tx)
    return {
        "timestamp": int(tx["timestamp"]),
        "token": _token(tx.get("token")),
        "amount": amount,
        "usd_value": _safe_float(tx.get("usd_value"), amount) or amount,
        "from": tx.get("from"),
        "to": tx.get("to"),
        "tx_hash": txid,
        "txid": txid,
        "network": network,
        "chain": network,
    }


def _pair_key(pair: dict[str, Any]) -> tuple[str, str]:
    return (_txid(pair["deposit"]), _txid(pair["withdrawal"]))


def _rv(a: float, b: float) -> float:
    return abs(a - b) / max(abs(a), abs(b), 1e-12)


def _pair_delta_t_sec(pair: dict[str, Any]) -> float:
    return (int(pair["withdrawal"]["timestamp"]) - int(pair["deposit"]["timestamp"])) / 1000


def _pair_value_rv(pair: dict[str, Any]) -> float:
    return _rv(_safe_float(pair["deposit"].get("usd_value")), _safe_float(pair["withdrawal"].get("usd_value")))


def _history_network(h: dict[str, Any], field: str) -> str:
    raw = h.get("raw") if isinstance(h.get("raw"), dict) else {}
    return _network(raw.get(field))


def _history_is_tron_related(h: dict[str, Any]) -> bool:
    return _history_network(h, "depositNetwork") == "tron" or _history_network(h, "settleNetwork") == "tron"


def _pair_is_tron_related(pair: dict[str, Any]) -> bool:
    dep = pair.get("deposit") or {}
    wit = pair.get("withdrawal") or {}
    dep_chain = _network(dep.get("chain") or dep.get("network"))
    wit_chain = _network(wit.get("chain") or wit.get("network"))
    return dep_chain == "tron" or wit_chain == "tron"


def _parse_csv(value: str) -> tuple[str, ...]:
    return tuple(x.strip().lower() for x in value.split(",") if x.strip())


def _chain_supported(chain: str, observable_chains: set[str]) -> bool:
    return bool(chain) and chain in observable_chains


def _load_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def load_sideshift_window(
    window: DateWindow,
    *,
    year: int,
    observable_chains: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    history = [
        h
        for h in load_history_jsonl(offchain_history_path(SERVICE))
        if (ts := history_time_ms(h)) is not None and window.contains_ms(ts)
    ]

    deposits: list[dict[str, Any]] = []
    withdrawals: list[dict[str, Any]] = []

    multichain_dep = REPO_ROOT / "data" / "classified" / "multichain" / f"deposits_{SERVICE}_{year}.json"
    multichain_wit = REPO_ROOT / "data" / "classified" / "multichain" / f"withdrawals_{SERVICE}_{year}.json"
    for tx in _load_json_list(multichain_dep):
        row = _normalize_tx(tx)
        if window.contains_ms(int(row["timestamp"])) and _chain_supported(row["chain"], observable_chains):
            deposits.append(row)
    for tx in _load_json_list(multichain_wit):
        row = _normalize_tx(tx)
        if window.contains_ms(int(row["timestamp"])) and _chain_supported(row["chain"], observable_chains):
            withdrawals.append(row)

    dep_path, wit_path = tron_classified_paths(SERVICE, year)
    if "tron" in observable_chains and dep_path.exists() and wit_path.exists():
        deposits.extend(
            _normalize_tx(tx)
            for tx in load_tron_classified_json(dep_path, window.start_ms, window.end_ms)
        )
        withdrawals.extend(
            _normalize_tx(tx)
            for tx in load_tron_classified_json(wit_path, window.start_ms, window.end_ms)
        )
    return history, deposits, withdrawals


def split_history_days(
    history: list[dict[str, Any]],
    *,
    test_ratio: float,
    split_date: date | None,
) -> tuple[set[date], set[date], date]:
    days = sorted({_utc_day_from_ms(history_time_ms(h) or 0) for h in history})
    if not days:
        raise SystemExit("No SideShift off-chain records in the selected window.")

    if split_date is None:
        split_idx = max(1, min(len(days) - 1, math.ceil(len(days) * (1.0 - test_ratio))))
        split_date = days[split_idx]

    train_days = {d for d in days if d < split_date}
    test_days = {d for d in days if d >= split_date}
    if not train_days or not test_days:
        raise SystemExit(f"Temporal split produced an empty side at split_date={split_date}")
    return train_days, test_days, split_date


def filter_history_by_days(history: list[dict[str, Any]], days: set[date]) -> list[dict[str, Any]]:
    return [h for h in history if _utc_day_from_ms(history_time_ms(h) or 0) in days]


def filter_pairs_by_deposit_days(pairs: list[dict[str, Any]], days: set[date]) -> list[dict[str, Any]]:
    return [p for p in pairs if _utc_day_from_ms(int(p["deposit"]["timestamp"])) in days]


def strict_seed_positives(
    history: list[dict[str, Any]],
    deposits: list[dict[str, Any]],
    withdrawals: list[dict[str, Any]],
    *,
    max_deposit_lag_sec: int,
    max_settlement_lag_sec: int,
    max_amount_rv: float,
    observable_chains: set[str],
    max_candidates_per_side: int,
) -> list[dict[str, Any]]:
    """Find high-precision off-chain anchored D-W seeds.

    If either SideShift side is not in observable_chains, the record is skipped
    for strict seed labeling. One-sided records are still useful for coverage
    reporting and manual investigation, but not for leakage-free D-W labels.
    """
    deposits_by_chain_token: dict[tuple[str, str], list[dict[str, Any]]] = {}
    withdrawals_by_chain_token: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for tx in deposits:
        deposits_by_chain_token.setdefault((_network(tx.get("chain") or tx.get("network")), _token(tx.get("token"))), []).append(tx)
    for tx in withdrawals:
        withdrawals_by_chain_token.setdefault((_network(tx.get("chain") or tx.get("network")), _token(tx.get("token"))), []).append(tx)
    for rows in deposits_by_chain_token.values():
        rows.sort(key=lambda x: int(x["timestamp"]))
    for rows in withdrawals_by_chain_token.values():
        rows.sort(key=lambda x: int(x["timestamp"]))

    positives: list[dict[str, Any]] = []
    used: set[tuple[str, str]] = set()
    for h in sorted(history, key=lambda row: history_time_ms(row) or 0):
        dep_chain = _history_network(h, "depositNetwork")
        wit_chain = _history_network(h, "settleNetwork")
        if dep_chain not in observable_chains or wit_chain not in observable_chains:
            continue

        h_ts = history_time_ms(h)
        if h_ts is None:
            continue
        dep_token = _token(h.get("input_coin"))
        wit_token = _token(h.get("output_coin"))
        dep_amount = _safe_float(h.get("input_amount"))
        wit_amount = _safe_float(h.get("output_amount"))

        dep_rows = deposits_by_chain_token.get((dep_chain, dep_token), [])
        dep_times = [int(x["timestamp"]) for x in dep_rows]
        lo = bisect.bisect_left(dep_times, h_ts - max_deposit_lag_sec * 1000)
        hi = bisect.bisect_right(dep_times, h_ts + max_deposit_lag_sec * 1000)
        dep_candidates = [
            d for d in dep_rows[lo:hi] if _rv(dep_amount, _safe_float(d.get("amount"))) <= max_amount_rv
        ]
        if not dep_candidates or len(dep_candidates) > max_candidates_per_side:
            continue

        best_pair: dict[str, Any] | None = None
        best_score = float("inf")
        wit_rows = withdrawals_by_chain_token.get((wit_chain, wit_token), [])
        wit_times = [int(x["timestamp"]) for x in wit_rows]
        for dep in dep_candidates:
            dep_ts = int(dep["timestamp"])
            w_lo = bisect.bisect_right(wit_times, dep_ts)
            w_hi = bisect.bisect_right(wit_times, dep_ts + max_settlement_lag_sec * 1000)
            wit_candidates = [
                w
                for w in wit_rows[w_lo:w_hi]
                if _rv(wit_amount, _safe_float(w.get("amount"))) <= max_amount_rv
            ]
            if not wit_candidates or len(wit_candidates) > max_candidates_per_side:
                continue
            for wit in wit_candidates:
                amount_rv = _rv(wit_amount, _safe_float(wit.get("amount")))
                score = (
                    abs(h_ts - dep_ts) / max(max_deposit_lag_sec * 1000, 1)
                    + (int(wit["timestamp"]) - dep_ts) / max(max_settlement_lag_sec * 1000, 1)
                    + amount_rv
                )
                if score < best_score:
                    best_score = score
                    best_pair = {
                        "deposit": dep,
                        "withdrawal": wit,
                        "label": 1,
                        "label_source": "strict_offchain_seed",
                        "shift_timestamp": h.get("shift_timestamp"),
                        "deposit_network": dep_chain,
                        "settle_network": wit_chain,
                    }

        if best_pair is not None and _pair_key(best_pair) not in used:
            used.add(_pair_key(best_pair))
            positives.append(best_pair)

    return positives


def history_coverage(
    history: list[dict[str, Any]],
    observable_chains: set[str],
) -> dict[str, Any]:
    pairs: dict[str, int] = {}
    deposit_networks: dict[str, int] = {}
    settle_networks: dict[str, int] = {}
    observable_records = 0
    one_sided_records = 0
    unsupported_records = 0
    tron_deposit_records = 0
    tron_settle_records = 0
    tron_both_records = 0
    tron_any_records = 0

    for h in history:
        dep = _history_network(h, "depositNetwork") or "unknown"
        wit = _history_network(h, "settleNetwork") or "unknown"
        pairs[f"{dep}->{wit}"] = pairs.get(f"{dep}->{wit}", 0) + 1
        deposit_networks[dep] = deposit_networks.get(dep, 0) + 1
        settle_networks[wit] = settle_networks.get(wit, 0) + 1

        dep_is_tron = dep == "tron"
        wit_is_tron = wit == "tron"
        if dep_is_tron:
            tron_deposit_records += 1
        if wit_is_tron:
            tron_settle_records += 1
        if dep_is_tron and wit_is_tron:
            tron_both_records += 1
        if dep_is_tron or wit_is_tron:
            tron_any_records += 1

        dep_obs = dep in observable_chains
        wit_obs = wit in observable_chains
        if dep_obs and wit_obs:
            observable_records += 1
        elif dep_obs or wit_obs:
            one_sided_records += 1
        else:
            unsupported_records += 1

    def top(d: dict[str, int]) -> list[dict[str, Any]]:
        return [
            {"name": name, "count": count}
            for name, count in sorted(d.items(), key=lambda item: item[1], reverse=True)[:15]
        ]

    return {
        "observable_chains": sorted(observable_chains),
        "fully_observable_records": observable_records,
        "one_sided_observable_records": one_sided_records,
        "unsupported_records": unsupported_records,
        "tron_related_records": {
            "tron_any_side": tron_any_records,
            "tron_deposit_side": tron_deposit_records,
            "tron_settlement_side": tron_settle_records,
            "tron_both_sides": tron_both_records,
            "non_tron_records": len(history) - tron_any_records,
        },
        "deposit_networks": top(deposit_networks),
        "settle_networks": top(settle_networks),
        "top_pairs": top(pairs),
    }


def pair_coverage(rows: list[dict[str, Any]]) -> dict[str, int]:
    """Count TRON involvement in candidate or labeled D-W pairs."""
    out = {
        "rows": len(rows),
        "tron_any_side": 0,
        "tron_deposit_side": 0,
        "tron_withdrawal_side": 0,
        "tron_both_sides": 0,
        "non_tron_pairs": 0,
        "positive_rows": 0,
        "negative_rows": 0,
        "positive_tron_any_side": 0,
        "negative_tron_any_side": 0,
    }
    for row in rows:
        dep = row.get("deposit") or {}
        wit = row.get("withdrawal") or {}
        dep_chain = _network(dep.get("chain") or dep.get("network"))
        wit_chain = _network(wit.get("chain") or wit.get("network"))
        dep_is_tron = dep_chain == "tron"
        wit_is_tron = wit_chain == "tron"
        tron_any = dep_is_tron or wit_is_tron

        if dep_is_tron:
            out["tron_deposit_side"] += 1
        if wit_is_tron:
            out["tron_withdrawal_side"] += 1
        if dep_is_tron and wit_is_tron:
            out["tron_both_sides"] += 1
        if tron_any:
            out["tron_any_side"] += 1
        else:
            out["non_tron_pairs"] += 1

        if "label" in row:
            if int(row.get("label", 0)) == 1:
                out["positive_rows"] += 1
                if tron_any:
                    out["positive_tron_any_side"] += 1
            else:
                out["negative_rows"] += 1
                if tron_any:
                    out["negative_tron_any_side"] += 1
    return out


def sample_negative_rows(
    candidates: list[dict[str, Any]],
    positive_keys: set[tuple[str, str]],
    *,
    target: int,
    seed: int,
    source: str,
) -> list[dict[str, Any]]:
    pool = [p for p in candidates if _pair_key(p) not in positive_keys]
    rng = random.Random(seed)
    rng.shuffle(pool)
    rows = []
    for pair in pool[:target]:
        rows.append(
            {
                "deposit": pair["deposit"],
                "withdrawal": pair["withdrawal"],
                "label": 0,
                "label_source": source,
            }
        )
    return rows


def fit_model(rows: list[dict[str, Any]], *, seed: int) -> Any:
    y = np.array([int(r["label"]) for r in rows], dtype=np.int32)
    if len(np.unique(y)) < 2:
        raise SystemExit("Need both positive and negative labels to train.")
    X = extract_features([{"deposit": r["deposit"], "withdrawal": r["withdrawal"]} for r in rows])
    pos = max(int(y.sum()), 1)
    neg = max(len(y) - pos, 1)
    model = xgb.XGBClassifier(
        max_depth=4,
        learning_rate=0.05,
        n_estimators=250,
        objective="binary:logistic",
        scale_pos_weight=neg / pos,
        eval_metric="logloss",
        random_state=seed,
    )
    model.fit(X, y)
    return model


def predict_scores(model: Any, pairs: list[dict[str, Any]]) -> np.ndarray:
    if not pairs:
        return np.array([], dtype=np.float32)
    return model.predict_proba(extract_features(pairs))[:, 1]


def self_train(
    seed_rows: list[dict[str, Any]],
    unlabeled_pairs: list[dict[str, Any]],
    *,
    iterations: int,
    positive_threshold: float,
    negative_threshold: float,
    seed: int,
) -> tuple[Any, list[dict[str, Any]], list[dict[str, Any]]]:
    labeled = list(seed_rows)
    labeled_keys = {_pair_key(r) for r in labeled}
    additions: list[dict[str, Any]] = []
    model = fit_model(labeled, seed=seed)

    for iteration in range(1, iterations + 1):
        remaining = [p for p in unlabeled_pairs if _pair_key(p) not in labeled_keys]
        if not remaining:
            break
        scores = predict_scores(model, remaining)
        new_rows: list[dict[str, Any]] = []
        for pair, score in zip(remaining, scores):
            if score >= positive_threshold:
                label = 1
            elif score <= negative_threshold:
                label = 0
            else:
                continue
            row = {
                "deposit": pair["deposit"],
                "withdrawal": pair["withdrawal"],
                "label": label,
                "label_source": f"self_training_iter_{iteration}",
                "pseudo_probability": float(score),
            }
            new_rows.append(row)
            labeled_keys.add(_pair_key(row))
        if not new_rows:
            break
        labeled.extend(new_rows)
        additions.extend(new_rows)
        model = fit_model(labeled, seed=seed)

    return model, labeled, additions


def metrics_at_threshold(y_true: np.ndarray, scores: np.ndarray, threshold: float) -> dict[str, float]:
    pred = (scores >= threshold).astype(np.int32)
    tp = int(((y_true == 1) & (pred == 1)).sum())
    fp = int(((y_true == 0) & (pred == 1)).sum())
    tn = int(((y_true == 0) & (pred == 0)).sum())
    fn = int(((y_true == 1) & (pred == 0)).sum())
    return {
        "accuracy": float(accuracy_score(y_true, pred)),
        "precision": float(precision_score(y_true, pred, zero_division=0)),
        "recall": float(recall_score(y_true, pred, zero_division=0)),
        "f1": float(f1_score(y_true, pred, zero_division=0)),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "predicted_positive": int(pred.sum()),
        "predicted_negative": int(len(pred) - pred.sum()),
    }


def baseline_rule_scores(
    pairs: list[dict[str, Any]],
    *,
    max_time_diff_sec: int,
    max_value_rv: float,
) -> np.ndarray:
    scores: list[float] = []
    for pair in pairs:
        dt_sec = _pair_delta_t_sec(pair)
        value_rv = _pair_value_rv(pair)
        scores.append(1.0 if 0 < dt_sec <= max_time_diff_sec and value_rv <= max_value_rv else 0.0)
    return np.array(scores, dtype=np.float32)


def evaluate_temporal_holdout(
    model: Any,
    positives: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    *,
    negative_ratio: int,
    baseline_time_diff_sec: int,
    baseline_value_rv: float,
    seed: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    positive_keys = {_pair_key(p) for p in positives}
    negatives = sample_negative_rows(
        candidates,
        positive_keys,
        target=max(len(positives) * negative_ratio, negative_ratio if positives else 0),
        seed=seed,
        source="temporal_holdout_negative",
    )
    rows = positives + negatives
    if not positives or not negatives:
        return {
            "warning": "Not enough strict temporal holdout labels for PR-AUC.",
            "positives": len(positives),
            "negatives": len(negatives),
        }, rows

    pairs = [{"deposit": r["deposit"], "withdrawal": r["withdrawal"]} for r in rows]
    y_true = np.array([int(r["label"]) for r in rows], dtype=np.int32)
    xgb_scores = predict_scores(model, pairs)
    base_scores = baseline_rule_scores(
        pairs,
        max_time_diff_sec=baseline_time_diff_sec,
        max_value_rv=baseline_value_rv,
    )
    metrics = {
        "positives": len(positives),
        "negatives": len(negatives),
        "negative_ratio": negative_ratio,
        "pair_coverage": pair_coverage(rows),
        "xgboost": {
            "pr_auc": float(average_precision_score(y_true, xgb_scores)),
            "threshold_0_50": metrics_at_threshold(y_true, xgb_scores, 0.50),
            "threshold_0_99": metrics_at_threshold(y_true, xgb_scores, 0.99),
        },
        "baseline_rule": {
            "pr_auc": float(average_precision_score(y_true, base_scores)),
            "threshold_0_50": metrics_at_threshold(y_true, base_scores, 0.50),
            "max_time_diff_sec": baseline_time_diff_sec,
            "max_value_rv": baseline_value_rv,
        },
    }
    for row, xgb_score, base_score in zip(rows, xgb_scores, base_scores):
        row["model_probability"] = float(xgb_score)
        row["baseline_probability"] = float(base_score)
    return metrics, rows


def export_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def export_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="SideShift temporal semi-supervised XGBoost experiment")
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--start-date", default="2026-05-22")
    parser.add_argument("--end-date", default="2026-06-28")
    parser.add_argument(
        "--split-date",
        type=_parse_date,
        default=_parse_date("2026-06-11"),
        help=(
            "UTC first test day. Train uses days before this date; "
            "test uses this date and later."
        ),
    )
    parser.add_argument("--test-ratio", type=float, default=0.25)
    parser.add_argument(
        "--collection-priority",
        default=",".join(DEFAULT_COLLECTION_PRIORITY),
        help="Research collection order used for metrics/reporting.",
    )
    parser.add_argument(
        "--observable-chains",
        default=",".join(DEFAULT_OBSERVABLE_CHAINS),
        help=(
            "Chains with comparable on-chain classified data. "
            "bitcoin/liquid are intentionally omitted by default."
        ),
    )
    parser.add_argument("--candidate-max-time-diff", type=int, default=7200)
    parser.add_argument("--candidate-max-rv", type=float, default=0.50)
    parser.add_argument("--seed-positive-window-sec", type=int, default=120)
    parser.add_argument("--seed-settlement-window-sec", type=int, default=7200)
    parser.add_argument("--seed-max-rv", type=float, default=0.005)
    parser.add_argument(
        "--seed-max-candidates-per-side",
        type=int,
        default=1,
        help="Ambiguity guard for strict seed labels.",
    )
    parser.add_argument("--train-negative-ratio", type=int, default=20)
    parser.add_argument("--eval-negative-ratio", type=int, default=20)
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--positive-threshold", type=float, default=0.99)
    parser.add_argument("--negative-threshold", type=float, default=0.01)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-prefix", default="sideshift_2026_temporal_semisupervised")
    args = parser.parse_args()

    window = DateWindow(start=_parse_date(args.start_date), end=_parse_date(args.end_date))
    observable_chains = {_network(c) for c in _parse_csv(args.observable_chains)}
    collection_priority = [_network(c) for c in _parse_csv(args.collection_priority)]
    history, deposits, withdrawals = load_sideshift_window(
        window,
        year=args.year,
        observable_chains=observable_chains,
    )
    all_history_count = len(history)
    history = [h for h in history if _history_is_tron_related(h)]
    train_days, test_days, split_date = split_history_days(
        history, test_ratio=args.test_ratio, split_date=args.split_date
    )

    all_candidates = generate_candidates(
        deposits,
        withdrawals,
        max_time_diff=args.candidate_max_time_diff,
        max_rv=args.candidate_max_rv,
        same_token_only=False,
    )
    candidates = [p for p in all_candidates if _pair_is_tron_related(p)]
    train_candidates = filter_pairs_by_deposit_days(candidates, train_days)
    test_candidates = filter_pairs_by_deposit_days(candidates, test_days)

    train_history = filter_history_by_days(history, train_days)
    test_history = filter_history_by_days(history, test_days)
    train_pos = strict_seed_positives(
        train_history,
        deposits,
        withdrawals,
        max_deposit_lag_sec=args.seed_positive_window_sec,
        max_settlement_lag_sec=args.seed_settlement_window_sec,
        max_amount_rv=args.seed_max_rv,
        observable_chains=observable_chains,
        max_candidates_per_side=args.seed_max_candidates_per_side,
    )
    test_pos = strict_seed_positives(
        test_history,
        deposits,
        withdrawals,
        max_deposit_lag_sec=args.seed_positive_window_sec,
        max_settlement_lag_sec=args.seed_settlement_window_sec,
        max_amount_rv=args.seed_max_rv,
        observable_chains=observable_chains,
        max_candidates_per_side=args.seed_max_candidates_per_side,
    )

    train_positive_keys = {_pair_key(p) for p in train_pos}
    train_neg = sample_negative_rows(
        train_candidates,
        train_positive_keys,
        target=max(len(train_pos) * args.train_negative_ratio, args.train_negative_ratio if train_pos else 0),
        seed=args.seed,
        source="train_temporal_negative",
    )
    seed_rows = train_pos + train_neg
    if not train_pos:
        raise SystemExit(
            "No strict train positives were found. Try a later split date, a wider seed window, "
            "or manually label SideShift samples for seed training."
        )

    model, labeled_rows, pseudo_rows = self_train(
        seed_rows,
        train_candidates,
        iterations=args.iterations,
        positive_threshold=args.positive_threshold,
        negative_threshold=args.negative_threshold,
        seed=args.seed,
    )
    holdout_metrics, holdout_rows = evaluate_temporal_holdout(
        model,
        test_pos,
        test_candidates,
        negative_ratio=args.eval_negative_ratio,
        baseline_time_diff_sec=args.seed_positive_window_sec,
        baseline_value_rv=args.seed_max_rv,
        seed=args.seed,
    )

    test_scores = predict_scores(model, test_candidates)
    discoveries: list[dict[str, Any]] = []
    for pair, score in zip(test_candidates, test_scores):
        if score < args.positive_threshold:
            continue
        if _pair_delta_t_sec(pair) <= args.seed_positive_window_sec and _pair_value_rv(pair) <= args.seed_max_rv:
            continue
        discoveries.append(
            {
                "deposit": pair["deposit"],
                "withdrawal": pair["withdrawal"],
                "model_probability": float(score),
                "delta_t_sec": _pair_delta_t_sec(pair),
                "value_rv": _pair_value_rv(pair),
                "missed_by_baseline_rule": True,
            }
        )

    model_path = GT_ROOT / "models" / f"xgboost_{args.output_prefix}.pkl"
    metrics_path = GT_ROOT / "result" / f"{args.output_prefix}_metrics.json"
    labels_path = GT_ROOT / "output" / f"training_pairs_{args.output_prefix}.jsonl"
    holdout_path = GT_ROOT / "output" / f"holdout_pairs_{args.output_prefix}.jsonl"
    discoveries_path = GT_ROOT / "result" / f"{args.output_prefix}_baseline_misses.json"

    joblib.dump(
        {
            "model": model,
            "service": SERVICE,
            "feature_names": FEATURE_NAMES,
            "method": "temporal_semisupervised",
            "date_window": {"start": args.start_date, "end": args.end_date},
            "split_date": str(split_date),
        },
        model_path,
    )
    export_jsonl(labels_path, labeled_rows)
    export_jsonl(holdout_path, holdout_rows)
    export_json(discoveries_path, discoveries)

    metrics = {
        "service": SERVICE,
        "date_window": {"start": args.start_date, "end": args.end_date},
        "split_date": str(split_date),
        "train_days": [str(d) for d in sorted(train_days)],
        "test_days": [str(d) for d in sorted(test_days)],
        "counts": {
            "offchain_history_all_observable": all_history_count,
            "offchain_history": len(history),
            "train_history": len(train_history),
            "test_history": len(test_history),
            "onchain_deposits": len(deposits),
            "onchain_withdrawals": len(withdrawals),
            "candidates_all_observable": len(all_candidates),
            "candidates": len(candidates),
            "train_candidates": len(train_candidates),
            "test_candidates": len(test_candidates),
            "strict_train_positives": len(train_pos),
            "train_negatives": len(train_neg),
            "pseudo_labels_added": len(pseudo_rows),
            "final_labeled_rows": len(labeled_rows),
            "strict_test_positives": len(test_pos),
            "baseline_miss_discoveries": len(discoveries),
        },
        "rules": {
            "history_network_filter": "tron-any",
            "candidate_pair_filter": "tron-any",
            "collection_priority": collection_priority,
            "observable_chains": sorted(observable_chains),
            "seed_positive_window_sec": args.seed_positive_window_sec,
            "seed_settlement_window_sec": args.seed_settlement_window_sec,
            "seed_max_rv": args.seed_max_rv,
            "seed_max_candidates_per_side": args.seed_max_candidates_per_side,
            "positive_threshold": args.positive_threshold,
            "negative_threshold": args.negative_threshold,
            "train_negative_ratio": args.train_negative_ratio,
            "eval_negative_ratio": args.eval_negative_ratio,
        },
        "coverage": history_coverage(history, observable_chains),
        "coverage_by_split": {
            "train_history": history_coverage(train_history, observable_chains),
            "test_history": history_coverage(test_history, observable_chains),
        },
        "pair_coverage": {
            "candidates": pair_coverage(candidates),
            "train_candidates": pair_coverage(train_candidates),
            "test_candidates": pair_coverage(test_candidates),
            "final_labeled_train_rows": pair_coverage(labeled_rows),
            "holdout_rows": pair_coverage(holdout_rows),
            "baseline_miss_discoveries": pair_coverage(discoveries),
        },
        "holdout": holdout_metrics,
        "outputs": {
            "model": str(model_path),
            "labels": str(labels_path),
            "holdout": str(holdout_path),
            "baseline_misses": str(discoveries_path),
        },
        "caveat": (
            "This is a TRON-anchored study: only SideShift records and D-W candidate pairs with "
            "a TRON deposit side, a TRON withdrawal/settlement side, or both are included in "
            "training and holdout metrics. Full D-W seed labels require both sides to be "
            "observable in the configured on-chain data. Bitcoin/Liquid-related requests "
            "are structurally different and should be treated as one-sided evidence unless comparable "
            "classified data exists for that side. Strict labels are high-precision seeds and temporal "
            "holdout anchors, not manual ground truth. baseline_misses should be manually reviewed "
            "before being reported as true positives."
        ),
    }
    export_json(metrics_path, metrics)
    print(json.dumps(metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
