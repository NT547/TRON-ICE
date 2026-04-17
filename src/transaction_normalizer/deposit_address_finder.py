# Module: deposit_address_finder.py
# Chức năng: Tìm kiếm các địa chỉ nạp (deposit addresses) thực sự của người dùng, loại bỏ contract và nhiễu, phục vụ phân tích dòng tiền vào hệ thống.

import json
import os
from typing import List, Dict, Any, Set
from collections import Counter
from .data_normalizer import normalize_transactions_from_files
from typing import Optional


def is_contract_address(address: Optional[str]) -> bool:
    """
    Heuristic kiểm tra một địa chỉ có phải là contract address trên TRON không.
    - Địa chỉ contract thường bắt đầu bằng 'T9' hoặc '41'.
    - Không hoàn toàn chính xác, chỉ là heuristic đơn giản.
    """
    if not isinstance(address, str):
        return False
    # Simple heuristic: if address starts with 'T9' or '41', likely contract
    # But this is not perfect; in practice, might need more checks
    return address.startswith("T9") or address.startswith("41")


def find_deposit_addresses_from_files(
    trx_file: str, trc20_file: str, hot_wallet: str, min_frequency: int = 5
) -> List[str]:
    """
    Đọc, chuẩn hóa và tìm các địa chỉ nạp từ file TRX và TRC-20.
    Trả về: Danh sách địa chỉ nạp (không phải contract, xuất hiện >= min_frequency).
    """
    normalized = normalize_transactions_from_files(trx_file, trc20_file)
    return find_deposit_addresses(normalized, hot_wallet, min_frequency)


def find_deposit_addresses_from_files(
    trx_file: str, trc20_file: str, hot_wallet: str, min_frequency: int = 5
) -> List[str]:
    """
    Load, normalize, and find deposit addresses.
    """
    normalized = normalize_transactions_from_files(trx_file, trc20_file)
    return find_deposit_addresses(normalized, hot_wallet, min_frequency)


def find_deposit_addresses(
    normalized_data: List[Dict[str, Any]], hot_wallet: str, min_frequency: int = 5
) -> List[str]:
    """
    Phân tích các giao dịch gửi đến hot_wallet để tìm các địa chỉ nạp thực sự:
    - Loại bỏ các địa chỉ contract.
    - Đếm tần suất xuất hiện của từng địa chỉ gửi (from_addr).
    - Chỉ giữ lại các địa chỉ xuất hiện >= min_frequency lần để loại nhiễu.
    Trả về: Danh sách địa chỉ nạp.
    """
    deposit_candidates = []
    tx_to_hot_wallet = 0
    for tx in normalized_data:
        if tx["to"] == hot_wallet:
            tx_to_hot_wallet += 1
            from_addr = tx["from"]
            if not is_contract_address(from_addr):
                deposit_candidates.append(from_addr)

    print(f"Transactions to hot wallet: {tx_to_hot_wallet}")
    print(f"Deposit candidates after filtering contracts: {len(deposit_candidates)}")

    # Đếm tần suất xuất hiện của từng địa chỉ gửi
    freq = Counter(deposit_candidates)
    print(f"Frequency counts: {dict(freq.most_common(10))}")  # Top 10

    # Lọc theo tần suất tối thiểu để loại nhiễu
    deposit_addresses = [addr for addr, count in freq.items() if count >= min_frequency]
    print(
        f"Deposit addresses after frequency filter (>= {min_frequency}): {len(deposit_addresses)}"
    )
    return deposit_addresses


def save_deposit_addresses(deposit_addresses: List[str], output_file: str):
    """
    Lưu danh sách địa chỉ nạp ra file JSON.
    """
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(deposit_addresses, f, indent=2, ensure_ascii=False)
