# Module: matcher.py
# Chức năng: Thực hiện ghép cặp (matching) giữa các giao dịch nạp (deposit) và rút (withdrawal) dựa trên xác suất dự đoán.
# Sử dụng thuật toán greedy one-to-one matching để đảm bảo mỗi deposit và withdrawal chỉ được ghép một lần.

import json
import numpy as np
from typing import List, Dict


def greedy_matcher(
    deposits: List[Dict],
    withdrawals: List[Dict],
    candidate_pairs: List[Dict],
    probabilities: np.ndarray,
    threshold: float = 0.5,
    output_file: str = None,
):
    """
    Thực hiện ghép cặp greedy one-to-one giữa các giao dịch nạp (deposit) và rút (withdrawal).
    - Mỗi deposit chỉ được ghép với một withdrawal có xác suất dự đoán cao nhất (nếu vượt ngưỡng threshold).
    - Mỗi withdrawal chỉ được ghép một lần (sau khi ghép sẽ bị loại khỏi pool).
    - Kết quả có thể được lưu ra file JSON nếu truyền output_file.
    Trả về: Danh sách các cặp match (dạng dict).
    """
    # Tạo pool các withdrawal còn lại (theo txid) để đảm bảo mỗi withdrawal chỉ được ghép một lần
    withdrawal_pool = {w["txid"]: w for w in withdrawals}

    # Gom các candidate theo deposit txid để dễ truy xuất
    from collections import defaultdict

    candidates_by_deposit = defaultdict(list)
    for idx, pair in enumerate(candidate_pairs):
        d = pair["deposit"]
        w = pair["withdrawal"]
        prob = probabilities[idx]
        if w["txid"] in withdrawal_pool:
            candidates_by_deposit[d["txid"]].append((prob, w))

    # Sắp xếp deposit theo thời gian để ưu tiên ghép trước các giao dịch cũ
    deposits_sorted = sorted(deposits, key=lambda x: x["timestamp"])
    matches = []
    for d in deposits_sorted:
        cands = candidates_by_deposit.get(d["txid"], [])
        if not cands:
            continue
        # Chọn withdrawal có xác suất cao nhất
        best_prob, best_w = max(cands, key=lambda x: x[0])
        if best_prob >= threshold and best_w["txid"] in withdrawal_pool:
            matches.append(
                {
                    "deposit_txid": d["txid"],
                    "withdrawal_txid": best_w["txid"],
                    "probability": float(best_prob),
                    # Độ lệch thời gian giữa deposit và withdrawal (giây)
                    "delta_t": (best_w["timestamp"] - d["timestamp"]) // 1000,
                    # Tỉ lệ lệch giá trị giao dịch
                    "delta_v_ratio": abs(d["usd_value"] - best_w["usd_value"])
                    / max(d["usd_value"], best_w["usd_value"]),
                }
            )
            # Loại withdrawal đã ghép khỏi pool
            del withdrawal_pool[best_w["txid"]]

    # Nếu có truyền output_file thì lưu kết quả ra file JSON
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(matches, f, indent=2, ensure_ascii=False)
    return matches
