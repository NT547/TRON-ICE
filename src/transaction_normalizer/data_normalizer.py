# Module: data_normalizer.py
# Chức năng: Chuẩn hóa dữ liệu giao dịch TRX và TRC-20 về định dạng thống nhất, phục vụ cho các bước phân tích và phân loại sau này.

import json
import os
from typing import List, Dict, Any
from decimal import Decimal
from .data_loader import load_transactions


def normalize_trx_transaction(tx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Chuẩn hóa một giao dịch TRX về schema thống nhất:
    - Lấy timestamp, địa chỉ from/to (chuyển từ hex sang base58), số lượng, token.
    - Chuyển giá trị từ SUN sang TRX (1e6 SUN = 1 TRX).
    Trả về: dict giao dịch chuẩn hóa hoặc None nếu lỗi.
    """
    try:
        from src.transaction_normalizer.base58 import hex_to_base58

        timestamp = tx.get("block_timestamp")
        # Lấy owner_address/to_address từ raw_data.contract.value
        raw_data = tx.get("raw_data", {})
        contract = raw_data.get("contract", [{}])[0] if raw_data.get("contract") else {}
        value_obj = contract.get("parameter", {}).get("value", {})
        owner_hex = value_obj.get("owner_address")
        to_hex = value_obj.get("to_address")
        from_addr = hex_to_base58(owner_hex) if owner_hex else None
        to_addr = hex_to_base58(to_hex) if to_hex else None
        value = value_obj.get("amount", 0)
        amount = Decimal(value) / Decimal(1e6)  # Convert SUN to TRX
        token = "TRX"
        return {
            "timestamp": timestamp,
            "from": from_addr,
            "to": to_addr,
            "token": token,
            "amount": float(amount),
        }
    except Exception as e:
        print(f"Error normalizing TRX tx: {e}")
        return None


def normalize_trc20_transaction(tx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Chuẩn hóa một giao dịch TRC-20 về schema thống nhất:
    - Lấy timestamp, địa chỉ from/to, số lượng, token, decimals.
    - Chuyển giá trị về số thực theo decimals của token.
    Trả về: dict giao dịch chuẩn hóa hoặc None nếu lỗi.
    """
    try:
        timestamp = tx.get("block_timestamp")
        from_addr = tx.get("from")
        to_addr = tx.get("to")
        value = Decimal(tx.get("value", 0))
        decimals = tx.get("token_info", {}).get(
            "decimals", 6
        )  # Default to 6 for USDT/USDC
        amount = float(value / Decimal(10**decimals))
        token = tx.get("token_info", {}).get("symbol", "UNKNOWN")
        return {
            "timestamp": timestamp,
            "from": from_addr,
            "to": to_addr,
            "token": token,
            "amount": amount,
        }
    except Exception as e:
        print(f"Error normalizing TRC-20 tx: {e}")
        return None


def normalize_transactions_from_files(
    trx_file: str, trc20_file: str
) -> List[Dict[str, Any]]:
    """
    Đọc và chuẩn hóa toàn bộ giao dịch từ file TRX và TRC-20.
    Trả về: Danh sách dict giao dịch chuẩn hóa.
    """
    data = load_transactions(trx_file, trc20_file)
    return normalize_transactions(data["trx"], data["trc20"])


def normalize_transactions(
    trx_data: List[Dict[str, Any]], trc20_data: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Chuẩn hóa toàn bộ giao dịch TRX và TRC-20 về schema thống nhất.
    Trả về: Danh sách dict giao dịch chuẩn hóa.
    """
    normalized = []
    for tx in trx_data:
        norm = normalize_trx_transaction(tx)
        if norm:
            normalized.append(norm)
    for tx in trc20_data:
        norm = normalize_trc20_transaction(tx)
        if norm:
            normalized.append(norm)
    return normalized


def save_normalized_transactions(
    normalized_data: List[Dict[str, Any]], output_file: str
):
    """
    Lưu danh sách giao dịch đã chuẩn hóa ra file JSON.
    """
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(normalized_data, f, indent=2, ensure_ascii=False)
