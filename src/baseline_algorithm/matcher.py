# Module: matcher.py
# Chức năng: Ghép cặp giao dịch nạp (deposit) và rút (withdrawal) tuân thủ nghiêm ngặt quy tắc ICE
#            Tích hợp cơ chế kiểm tra Tái sử dụng địa chỉ (Address Reuse) toàn cục.

import bisect
import json
import logging
import os
import pandas as pd
from typing import List, Dict, Any, Optional, Generator
from collections import defaultdict

# Import các hàm tính toán giá và helper xử lý CSV
from src.baseline_algorithm.price_calculator import (
    calculate_usd_value,
    get_historical_prices,
)
from src.utils.helper import load_csv, save_csv_in_chunks


def compute_usd_values(
    transactions: List[Dict[str, Any]],
    year: int,
    cache_dir: str,
    api_key: Optional[str],
    bucket_minutes: int,
) -> None:
    """
    Tính usd_value cho từng giao dịch nếu chưa có, sử dụng cache giá lịch sử.
    Đồng thời chuẩn hóa trường số lượng (hỗ trợ cả 'amount' và 'value').
    """
    for tx in transactions:
        if tx.get("token") != "TRX":
            continue
        
        if "amount" not in tx and "value" in tx:
            tx["amount"] = float(tx["value"])

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
    """
    withdrawals_by_token: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    withdrawal_timestamps: Dict[str, List[int]] = {}

    for w in withdrawals:
        if w.get("token"):
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
    all_deposit_senders: set,  # BỔ SUNG: Tập hợp toàn bộ địa chỉ nạp để check Address Reuse
) -> List[Dict[str, Any]]:
    """
    Tìm kiếm và xếp hạng các giao dịch rút tiền khớp với giao dịch nạp tiền
    Áp dụng quy tắc phân tầng địa chỉ tái sử dụng nâng cao.
    """
    d_time = deposit["timestamp"]
    d_usd = deposit.get("usd_value")
    d_token = deposit.get("token")
    if not d_usd or d_usd == 0:
        return []

    time_window_ms = time_window * 1000

    # 1. KIỂM TRA TIÊN QUYẾT & LỌC T (Thời gian)
    left_idx = bisect.bisect_right(withdrawal_timestamps, d_time)
    right_idx = bisect.bisect_right(withdrawal_timestamps, d_time + time_window_ms)

    candidates = []
    dep_sender = str(deposit.get("from") or deposit.get("sender") or "").lower().strip()

    for i in range(left_idx, right_idx):
        w = withdrawals[i]
        w_usd = w.get("usd_value")
        w_token = w.get("token")
        if not w_usd or w_token != d_token:
            continue

        # 2. LỌC V (Giá trị)
        value_diff_ratio = abs(w_usd - d_usd) / d_usd
        if value_diff_ratio > value_threshold or value_diff_ratio < 0.01:
            continue

        w_receiver = str(w.get("to") or w.get("receiver") or "").lower().strip()

        # 3. LOGIC CẢI TIẾN: PHÂN TẦNG ĐỊA CHỈ (Address Reuse)
        
        # Ưu tiên: Địa chỉ rút này từng được sử dụng để nạp bởi 1 hoặc nhiều địa chỉ khác trong hệ thống
        is_address_reused = (w_receiver in all_deposit_senders) and (w_receiver != "")

        # 4. QUY TẮC NHỎ NHẤT (Minimal V and T)
        time_diff = w["timestamp"] - d_time
        t_score = time_diff / time_window_ms
        v_score = value_diff_ratio / value_threshold
        combined_deviation = t_score + v_score

        candidates.append(
            {
                "deposit_txid": deposit.get("txid"),
                "withdrawal_txid": w.get("txid"),
                "deposit_address": deposit.get("from"),
                "withdrawal_address": w.get("to"),
                "is_address_reused": is_address_reused, 
                "deviation_score": combined_deviation,
                "time_diff_sec": time_diff / 1000,
                "value_diff_percent": value_diff_ratio * 100,
            }
        )

    # XẾP HẠNG ỨNG VIÊN THEO 3 TẦNG ƯU TIÊN:
    # Tầng 1: is_address_reused đứng trước (True -> False)
    # Tầng 1: deviation_score nhỏ nhất đứng trước (Tăng dần)
    candidates.sort(
        key=lambda x: (not x["is_address_reused"], x["deviation_score"])
    )

    return candidates


def run_matching_pipeline(
    deposits_path: str,
    withdrawals_path: str,
    output_path: str,
    time_window: int = 180,
    value_threshold: float = 0.05,
    year: int = 2025,
    cache_dir: str = "cache",
    api_key: Optional[str] = None,
    bucket_minutes: int = 5,
    chunk_size: int = 10000,
) -> None:
    """
    Pipeline xử lý đầu cuối (End-to-End) tối ưu dữ liệu lớn bằng CSV Chunking
    """
    # BƯỚC CỐT LÕI MỚI: Thu thập nhanh toàn bộ địa chỉ gửi tiền (Deposit Senders) để làm bản đồ đối chiếu toàn cục
    logging.info("BƯỚC 0: Đang thiết lập bản đồ định danh địa chỉ nạp (Global Deposit Senders)...")
    all_deposit_senders = set()
    pre_deposit_chunks = load_csv(deposits_path, chunk_size=chunk_size)
    for chunk in pre_deposit_chunks:
        for col in ["from", "sender"]:
            if col in chunk.columns:
                # Đưa về dạng lowercase để tránh sai lệch chữ hoa/chữ thường từ các hàm parser
                all_deposit_senders.update(
                    chunk[col].dropna().astype(str).str.lower().str.strip().tolist()
                )
    logging.info(f"Đã ghi nhận tổng cộng {len(all_deposit_senders)} địa chỉ ví nạp duy nhất.")

    logging.info("BƯỚC 1: Bắt đầu tải và định giá danh sách dữ liệu Rút tiền (Withdrawals)...")
    withdrawal_chunks = load_csv(withdrawals_path, chunk_size=chunk_size)
    all_withdrawals: List[Dict[str, Any]] = []

    for chunk in withdrawal_chunks:
        all_withdrawals.extend(chunk.to_dict("records"))

    logging.info(f"Đã tải {len(all_withdrawals)} bản ghi withdrawal. Tiến hành tính toán định giá USD...")
    compute_usd_values(all_withdrawals, year, cache_dir, api_key, bucket_minutes)

    withdrawals_by_token, withdrawal_timestamps = build_withdrawal_index(all_withdrawals)
    used_withdrawal_txids = set()

    def match_chunk_generator() -> Generator[pd.DataFrame, None, None]:
        logging.info("BƯỚC 2: Bắt đầu stream và xử lý danh sách dữ liệu Nạp tiền (Deposits)...")
        deposit_chunks = load_csv(deposits_path, chunk_size=chunk_size)

        for chunk in deposit_chunks:
            batch_deposits = chunk.to_dict("records")
            compute_usd_values(batch_deposits, year, cache_dir, api_key, bucket_minutes)

            chunk_matched_pairs = []
            for deposit in batch_deposits:
                token = deposit.get("token")
                if not token or token not in withdrawals_by_token:
                    continue

                # Truyền bản đồ ví `all_deposit_senders` vào để chấm điểm phân tầng
                ranked_candidates = match_deposit_withdrawal(
                    deposit,
                    withdrawals_by_token[token],
                    withdrawal_timestamps[token],
                    time_window,
                    value_threshold,
                    all_deposit_senders,
                )

                for match in ranked_candidates:
                    w_txid = match["withdrawal_txid"]
                    if w_txid not in used_withdrawal_txids:
                        used_withdrawal_txids.add(w_txid)
                        chunk_matched_pairs.append(match)
                        break

            if chunk_matched_pairs:
                yield pd.DataFrame(chunk_matched_pairs)

    logging.info(f"BƯỚC 3: Tiến hành ghi dữ liệu ghép cặp ra file đầu ra: {output_path}")
    save_csv_in_chunks(match_chunk_generator(), output_path)
    logging.info("🎉 Hoàn tất quá trình khớp cặp giao dịch theo thực thể địa chỉ tái sử dụng thành công!")