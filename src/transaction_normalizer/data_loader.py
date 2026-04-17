# Module: data_loader.py
# Chức năng: Đọc dữ liệu giao dịch TRX và TRC-20 từ file JSON, trả về danh sách dict giao dịch.

import json
import logging
import os
from typing import List, Dict, Any


def load_trx_data(file_path: str) -> List[Dict[str, Any]]:
    """
    Đọc dữ liệu giao dịch TRX từ file JSON.
    - Trả về danh sách dict giao dịch TRX.
    - Nếu file không tồn tại sẽ báo lỗi.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"TRX data file not found: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    trx_data = data if isinstance(data, list) else []
    logging.info(f"Loaded {len(trx_data)} TRX transactions from {file_path}")
    return trx_data


def load_trc20_data(file_path: str) -> List[Dict[str, Any]]:
    """
    Đọc dữ liệu giao dịch TRC-20 từ file JSON.
    - Trả về danh sách dict giao dịch TRC-20.
    - Nếu file không tồn tại sẽ báo lỗi.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"TRC-20 data file not found: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    trc20_data = data if isinstance(data, list) else []
    logging.info(f"Loaded {len(trc20_data)} TRC-20 transactions from {file_path}")
    return trc20_data


def load_transactions(
    trx_file: str, trc20_file: str
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Đọc cả hai loại giao dịch TRX và TRC-20 từ file, trả về dict với 2 key: 'trx' và 'trc20'.
    """
    trx_data = load_trx_data(trx_file)
    trc20_data = load_trc20_data(trc20_file)
    return {"trx": trx_data, "trc20": trc20_data}
