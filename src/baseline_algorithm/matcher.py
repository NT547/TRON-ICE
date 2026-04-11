# Module: matcher.py
# Chức năng: Ghép cặp giao dịch nạp (deposit) và rút (withdrawal) theo thuật toán baseline (dựa vào thời gian, giá trị, token), hỗ trợ tính toán giá trị USD, đa tiến trình, và lưu kết quả.
#
# - Ghép cặp greedy 1-1 giữa deposit và withdrawal dựa trên time window, value threshold, token
# - Tính toán giá trị USD cho giao dịch dựa trên giá lịch sử (price_calculator)
# - Hỗ trợ batch processing, đa tiến trình/đa luồng để tăng tốc
# - Lưu kết quả ghép cặp ra file JSON

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


def price_deposits_and_save(
    deposits: List[Dict[str, Any]],
    service: str,
    year: int,
    cache_dir: str = "cache",
    api_key: Optional[str] = None,
    bucket_minutes: int = 5,
    output_dir: str = "data/priced",
):
    """
    Tính usd_value cho từng deposit và lưu ra file data/priced/deposits_priced_trongrid_{service}_{year}.json
    Args:
        deposits: list giao dịch nạp
        service: tên dịch vụ (vd: fixedfloat)
        year: năm lấy giá
        cache_dir: thư mục cache giá
        api_key: API key CoinGecko (nếu có)
        bucket_minutes: độ rộng bucket thời gian
        output_dir: thư mục lưu file kết quả
    """
    from src.baseline_algorithm.price_calculator import calculate_usd_value

    os.makedirs(output_dir, exist_ok=True)
    for tx in deposits:
        if tx.get("usd_value") is None:
            tx["usd_value"] = calculate_usd_value(
                tx,
                year,
                cache_dir=cache_dir,
                api_key=api_key,
                bucket_minutes=bucket_minutes,
            )
    output_file = os.path.join(
        output_dir, f"deposits_priced_trongrid_{service}_{year}.json"
    )
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(deposits, f, indent=2, ensure_ascii=False)
    logging.info(f"Saved priced deposits to {output_file}")


def prefetch_price_histories(
    transactions: List[Dict[str, Any]],
    year: int,
    cache_dir: str,
    api_key: Optional[str],
) -> None:
    """
    Tải trước lịch sử giá cho tất cả token xuất hiện trong danh sách giao dịch (tăng tốc cho bước pricing).
    Args:
        transactions: list giao dịch (deposit/withdrawal)
        year: năm lấy giá
        cache_dir: thư mục cache
        api_key: API key CoinGecko (nếu có)
    """
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
    """
    Tính usd_value cho từng giao dịch nếu chưa có, sử dụng cache giá lịch sử.
    Args:
        transactions: list giao dịch (deposit/withdrawal)
        year: năm lấy giá
        cache_dir: thư mục cache
        api_key: API key CoinGecko (nếu có)
        bucket_minutes: độ rộng bucket thời gian
    """
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
    """
    Tạo index các withdrawal theo token và danh sách timestamp để tăng tốc tìm kiếm khi ghép cặp.
    Returns:
        withdrawals_by_token: dict token -> list withdrawal
        withdrawal_timestamps: dict token -> list timestamp (đã sort)
    """
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
    """
    Ghép một deposit với các withdrawal hợp lệ trong khoảng thời gian và giá trị cho phép.
    Args:
        deposit: dict giao dịch nạp
        withdrawals: list withdrawal cùng token
        withdrawal_timestamps: list timestamp withdrawal (đã sort)
        time_window: khoảng thời gian cho phép (giây)
        value_threshold: ngưỡng lệch giá trị cho phép (tỉ lệ)
    Returns:
        list các dict match (deposit, withdrawal, time_diff, value_diff_percent)
    """
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
    """
    Xử lý một batch deposit, ghép cặp với withdrawal theo token, trả về tất cả match tìm được.
    Args:
        batch_deposits: list deposit trong batch
        withdrawals_by_token: dict token -> list withdrawal
        withdrawal_timestamps: dict token -> list timestamp
        time_window: khoảng thời gian cho phép (giây)
        value_threshold: ngưỡng lệch giá trị cho phép (tỉ lệ)
    Returns:
        list các dict match
    """
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
    """
    Pipeline ghép cặp baseline:
    - Tính giá trị USD cho tất cả giao dịch nạp/rút
    - Chỉ giữ lại giao dịch hợp lệ (có usd_value, token)
    - Xây dựng index withdrawal theo token
    - Chia batch và ghép cặp song song (đa tiến trình hoặc đa luồng)
    - Trả về danh sách các cặp match (deposit, withdrawal, time_diff, value_diff_percent)
    Args:
        deposits: list giao dịch nạp
        withdrawals: list giao dịch rút
        time_window: khoảng thời gian cho phép (giây)
        value_threshold: ngưỡng lệch giá trị cho phép (tỉ lệ)
        year: năm lấy giá
        cache_dir: thư mục cache giá
        num_processes: số tiến trình/luồng song song
        api_key: API key CoinGecko (nếu có)
        bucket_minutes: độ rộng bucket thời gian
    Returns:
        list các dict match (deposit, withdrawal, time_diff, value_diff_percent)
    """
    logging.info(
        f"Starting matching: {len(deposits)} deposits, {len(withdrawals)} withdrawals, using {num_processes} processes."
    )
    # ...existing code...


def save_matched_pairs(matches: List[Dict[str, Any]], output_file: str):
    """
    Lưu danh sách các cặp match ra file JSON.
    Args:
        matches: list các dict match (deposit, withdrawal, ...)
        output_file: đường dẫn file JSON kết quả
    """
    directory = os.path.dirname(output_file)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(matches, f, indent=2, ensure_ascii=False)
    logging.info(f"Saved {len(matches)} matched pairs to {output_file}.")
