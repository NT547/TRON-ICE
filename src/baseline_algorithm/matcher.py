import bisect
import json
import logging
import os
from typing import List, Dict, Any, Optional
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from src.baseline_algorithm.price_calculator import (
    calculate_usd_value,
    get_historical_prices,
)


def prefetch_price_histories(
    transactions: List[Dict[str, Any]],
    year: int,
    cache_dir: str,
    api_key: Optional[str],
) -> None:
    unique_tokens = {tx["token"] for tx in transactions if tx.get("token")}
    logging.info(
        f"Prefetching historical price caches for tokens: {', '.join(sorted(unique_tokens))}"
    )
    for token in unique_tokens:
        get_historical_prices(token, year, cache_dir, api_key)


def compute_usd_values(
    transactions: List[Dict[str, Any]],
    year: int,
    cache_dir: str,
    api_key: Optional[str],
    bucket_minutes: int,
) -> None:
    for tx in transactions:
        if tx.get("usd_value") is None:
            tx["usd_value"] = calculate_usd_value(
                tx,
                year,
                cache_dir,
                api_key=api_key,
                bucket_minutes=bucket_minutes,
            )


def build_withdrawal_index(
    withdrawals: List[Dict[str, Any]],
) -> tuple[Dict[str, List[Dict[str, Any]]], Dict[str, List[int]]]:
    withdrawals_by_token: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    withdrawal_timestamps: Dict[str, List[int]] = {}

    for w in withdrawals:
        withdrawals_by_token[w["token"]].append(w)

    for token, token_withdrawals in withdrawals_by_token.items():
        token_withdrawals.sort(key=lambda x: x["timestamp"])
        withdrawal_timestamps[token] = [w["timestamp"] for w in token_withdrawals]

    return withdrawals_by_token, withdrawal_timestamps


def match_deposit_withdrawal(
    deposit: Dict[str, Any],
    withdrawals: List[Dict[str, Any]],
    withdrawal_timestamps: List[int],
    time_window: int,
    value_threshold: float,
) -> List[Dict[str, Any]]:
    matches: List[Dict[str, Any]] = []
    dep_ts = deposit["timestamp"]
    dep_value = deposit.get("usd_value", 0.0)
    if dep_value <= 0:
        logging.debug(
            f"Skipping deposit {deposit.get('txid')} because usd_value={dep_value}"
        )
        return matches

    left = bisect.bisect_left(withdrawal_timestamps, dep_ts - time_window * 1000)
    right = bisect.bisect_right(withdrawal_timestamps, dep_ts + time_window * 1000)
    candidates = withdrawals[left:right]

    for withdrawal in candidates:
        w_value = withdrawal.get("usd_value", 0.0)
        if w_value <= 0:
            continue
        value_diff = abs(w_value - dep_value) / dep_value
        if value_diff <= value_threshold:
            matches.append(
                {
                    "deposit": deposit,
                    "withdrawal": withdrawal,
                    "time_diff": abs(withdrawal["timestamp"] - dep_ts),
                    "value_diff_percent": value_diff * 100,
                }
            )

    return matches


def process_batch(
    batch_deposits: List[Dict[str, Any]],
    withdrawals_by_token: Dict[str, List[Dict[str, Any]]],
    withdrawal_timestamps: Dict[str, List[int]],
    time_window: int,
    value_threshold: float,
) -> List[Dict[str, Any]]:
    all_matches: List[Dict[str, Any]] = []
    logging.info(f"Processing batch with {len(batch_deposits)} deposits")

    for deposit in batch_deposits:
        token = deposit["token"]
        if token not in withdrawals_by_token:
            continue
        matches = match_deposit_withdrawal(
            deposit,
            withdrawals_by_token[token],
            withdrawal_timestamps[token],
            time_window,
            value_threshold,
        )
        if matches:
            logging.debug(
                f"Deposit {deposit.get('txid')} matched {len(matches)} withdrawal(s)"
            )
            all_matches.extend(matches)

    return all_matches


def run_matching(
    deposits: List[Dict[str, Any]],
    withdrawals: List[Dict[str, Any]],
    time_window: int = 300,
    value_threshold: float = 0.05,
    year: int = 2025,
    cache_dir: str = "cache",
    num_processes: int = 1,
    api_key: Optional[str] = None,
    bucket_minutes: int = 5,
) -> List[Dict[str, Any]]:
    logging.info(
        f"Starting matching: {len(deposits)} deposits, {len(withdrawals)} withdrawals, using {num_processes} processes."
    )

    deposits = [d for d in deposits if d.get("token")]
    withdrawals = [w for w in withdrawals if w.get("token")]

    prefetch_price_histories(deposits + withdrawals, year, cache_dir, api_key)
    compute_usd_values(deposits, year, cache_dir, api_key, bucket_minutes)
    compute_usd_values(withdrawals, year, cache_dir, api_key, bucket_minutes)

    # Chỉ giữ transaction có usd_value hợp lệ (không None, không 0.0)
    deposits = [d for d in deposits if d.get("usd_value") not in (None, 0.0)]
    withdrawals = [w for w in withdrawals if w.get("usd_value") not in (None, 0.0)]

    withdrawals_by_token, withdrawal_timestamps = build_withdrawal_index(withdrawals)

    deposits.sort(key=lambda x: x["timestamp"])
    for token in withdrawals_by_token:
        withdrawals_by_token[token].sort(key=lambda x: x["timestamp"])
        withdrawal_timestamps[token].sort()

    batch_size = max(1, len(deposits) // num_processes)
    batches = [
        deposits[i : i + batch_size] for i in range(0, len(deposits), batch_size)
    ]

    all_matches: List[Dict[str, Any]] = []
    if num_processes > 1:
        logging.info("Using multiprocessing executor for matching batches.")
        with ProcessPoolExecutor(max_workers=num_processes) as executor:
            futures = [
                executor.submit(
                    process_batch,
                    batch,
                    withdrawals_by_token,
                    withdrawal_timestamps,
                    time_window,
                    value_threshold,
                )
                for batch in batches
            ]
            for future in futures:
                all_matches.extend(future.result())
    else:
        logging.info("Using thread-based executor for matching batches.")
        with ThreadPoolExecutor(max_workers=num_processes) as executor:
            futures = [
                executor.submit(
                    process_batch,
                    batch,
                    withdrawals_by_token,
                    withdrawal_timestamps,
                    time_window,
                    value_threshold,
                )
                for batch in batches
            ]
            for future in futures:
                all_matches.extend(future.result())

    # Chỉ log ra màn hình, không ghi file log match từng dòng json
    return all_matches


def save_matched_pairs(matches: List[Dict[str, Any]], output_file: str):
    directory = os.path.dirname(output_file)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(matches, f, indent=2, ensure_ascii=False)
    logging.info(f"Saved {len(matches)} matched pairs to {output_file}.")
