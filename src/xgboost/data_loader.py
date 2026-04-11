# Module: data_loader.py
# Chức năng: Đọc và lọc các giao dịch từ file JSON, chỉ giữ lại các giao dịch hợp lệ (có usd_value và token hợp lệ).

import json
from typing import List, Dict


def load_transactions(file_path: str) -> List[Dict]:
    """
    Đọc các giao dịch từ file JSON và lọc bỏ các giao dịch không hợp lệ:
    - Không có trường usd_value hoặc usd_value = 0
    - Token bị thiếu hoặc không hợp lệ (unknown)
    Trả về: Danh sách các dict giao dịch hợp lệ.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        txs = json.load(f)
    filtered = [
        tx
        for tx in txs
        if tx.get("usd_value") not in (None, 0.0)
        and tx.get("token") not in (None, "", "unknown", "UNKNOWN")
    ]
    return filtered
