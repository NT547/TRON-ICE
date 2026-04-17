# Module: candidate_generator.py
# Chức năng: Sinh ra các cặp ứng viên (candidate pairs) giữa các giao dịch nạp (deposit) và rút (withdrawal) dựa trên các tiêu chí về thời gian và giá trị giao dịch.

from typing import List, Dict
import bisect


def generate_candidates(
    deposits: List[Dict],
    withdrawals: List[Dict],
    max_time_diff: int = 600,
    max_rv: float = 0.15,
) -> List[Dict]:
    """
    Sinh ra các cặp ứng viên (deposit, withdrawal) thỏa mãn các điều kiện:
    - Giao dịch rút phải xảy ra sau giao dịch nạp và trong khoảng thời gian tối đa (max_time_diff, đơn vị giây).
    - Tỉ lệ lệch giá trị giao dịch (rV) không vượt quá max_rv.
    - Chỉ ghép các giao dịch cùng loại token.
    Trả về: Danh sách các dict chứa cặp deposit và withdrawal.
    """
    # Gom các withdrawal theo token để tăng tốc tìm kiếm
    withdrawals_by_token = {}
    for w in withdrawals:
        withdrawals_by_token.setdefault(w["token"], []).append(w)
    # Sắp xếp các withdrawal theo thời gian cho từng token
    for token in withdrawals_by_token:
        withdrawals_by_token[token].sort(key=lambda x: x["timestamp"])
    candidates = []
    for d in deposits:
        token = d["token"]
        if token not in withdrawals_by_token:
            continue
        w_list = withdrawals_by_token[token]
        td = d["timestamp"]
        vd = d["usd_value"]
        # Sử dụng bisect để tìm nhanh các withdrawal trong khoảng thời gian hợp lệ
        w_times = [w["timestamp"] for w in w_list]
        left = bisect.bisect_right(w_times, td)
        right = bisect.bisect_right(w_times, td + max_time_diff * 1000)
        for w in w_list[left:right]:
            tw = w["timestamp"]
            vw = w["usd_value"]
            delta_t = (tw - td) // 1000
            if delta_t <= 0 or delta_t > max_time_diff:
                continue
            rv = abs(vd - vw) / max(vd, vw)
            if rv > max_rv:
                continue
            candidates.append({"deposit": d, "withdrawal": w})
    return candidates
