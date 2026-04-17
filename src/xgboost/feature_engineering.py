# Module: feature_engineering.py
# Chức năng: Trích xuất đặc trưng (feature) từ các cặp ứng viên (candidate pairs) để phục vụ huấn luyện và dự đoán mô hình.

import math
import numpy as np
from typing import List, Dict
from datetime import datetime


def extract_features(
    candidate_pairs: List[Dict], lambda_decay: float = 0.005
) -> np.ndarray:
    """
    Trích xuất vector đặc trưng cho từng cặp ứng viên (deposit, withdrawal):
    - rv: Tỉ lệ lệch giá trị giao dịch (|vd - vw| / max(vd, vw))
    - delta_t: Độ lệch thời gian giữa withdrawal và deposit (giây)
    - sT: Trọng số thời gian (time decay, exp(-lambda_decay * delta_t))
    - token_match: 1 nếu cùng loại token, 0 nếu khác
    - reuse: 1 nếu địa chỉ from của deposit trùng với to của withdrawal (tái sử dụng), 0 nếu không
    - log_value: log(giá trị deposit + 1)
    - hour: Giờ UTC của thời điểm deposit
    - chain_pair: Luôn = 0 (chỉ cho TRON)
    Trả về: np.ndarray shape (n_pairs, 8)
    """
    features = []
    for pair in candidate_pairs:
        d = pair["deposit"]
        w = pair["withdrawal"]
        vd = d["usd_value"]
        vw = w["usd_value"]
        td = d["timestamp"]
        tw = w["timestamp"]
        # 1. Value deviation ratio
        rv = abs(vd - vw) / max(vd, vw)
        # 2. Time difference (seconds)
        delta_t = (tw - td) // 1000
        # 3. Time-decay score
        sT = math.exp(-lambda_decay * delta_t)
        # 4. Token match
        token_match = 1 if d["token"] == w["token"] else 0
        # 5. Address reuse
        reuse = 1 if d.get("from") == w.get("to") else 0
        # 6. Log value
        log_value = math.log(vd + 1)
        # 7. Hour-of-day
        hour = datetime.utcfromtimestamp(td // 1000).hour
        # 8. Chain pair (TRON only, encode = 0)
        chain_pair = 0
        features.append(
            [rv, delta_t, sT, token_match, reuse, log_value, hour, chain_pair]
        )
    return np.array(features)
