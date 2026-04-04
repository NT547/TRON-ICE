# Thực hiện thuật toán baseline đơn giản dựa trên file đã phân loại DEPOSIT và WITHDRAWAL (classifide)
# Ghi các giao dịch khớp lệnh vào  file data/matched {service}_matches.csv
import pandas as pd
import os

# Đảm bảo file config.py có các biến này
from config import HOT_WALLETS, TIME_WINDOW, VALUE_THRESHOLD


def load_ops(deposit_file, withdrawal_file):
    """Load dữ liệu từ CSV và chuyển sang list of dicts để xử lý."""
    try:
        d = pd.read_csv(deposit_file)
        w = pd.read_csv(withdrawal_file)
        return d.to_dict("records"), w.to_dict("records")
    except Exception as e:
        print(f"❌ Lỗi khi đọc file: {e}")
        return [], []


def match_baseline(deposits, withdrawals, time_window, value_threshold):
    """
    Thuật toán khớp lệnh dựa trên khoảng cách thời gian và giá trị.
    time_window: Giây
    value_threshold: Tỷ lệ chênh lệch (0.01 = 1%)
    """
    matches = []
    used_w = set()

    for d in deposits:
        best_w = None
        best_score = float("inf")  # Khởi tạo giá trị vô cực để tìm mức thấp nhất

        for w in withdrawals:
            # Bỏ qua nếu withdrawal này đã được khớp với lệnh deposit khác
            if w["txid"] in used_w:
                continue

            # 1. Kiểm tra TIME (Đổi từ ms sang s nếu timestamp là miliseconds)
            dt = abs(d["timestamp"] - w["timestamp"]) / 1000
            if dt > time_window:
                continue

            # 2. Kiểm tra VALUE
            if d["value"] <= 0 or w["value"] <= 0:
                continue

            # Tính tỷ lệ chênh lệch giá trị: |d - w| / max(d, w)
            rv = abs(d["value"] - w["value"]) / max(d["value"], w["value"])

            if rv > value_threshold:
                continue

            # 3. Chọn lệnh khớp nhất (chênh lệch giá trị thấp nhất)
            if rv < best_score:
                best_score = rv
                best_w = w

        # Nếu tìm thấy withdraw phù hợp nhất cho deposit này
        if best_w:
            matches.append(
                {
                    "deposit_tx": d["txid"],
                    "withdraw_tx": best_w["txid"],
                    "value_diff_ratio": best_score,
                    "time_diff_sec": abs(d["timestamp"] - best_w["timestamp"]) / 1000,
                    "value_dep": d["value"],
                    "value_wit": best_w["value"],
                }
            )
            used_w.add(best_w["txid"])

    return matches


def main():
    # Tạo thư mục đầu ra nếu chưa có
    os.makedirs("data/matched", exist_ok=True)

    for service in HOT_WALLETS.keys():
        print(f"\n=== PROCESSING SERVICE: {service} ===")

        dep_file = f"data/classified/{service}_deposits.csv"
        wit_file = f"data/classified/{service}_withdrawals.csv"

        if not os.path.exists(dep_file) or not os.path.exists(wit_file):
            print(f"⚠️  Missing files for {service}, skipping...")
            continue

        deposits, withdrawals = load_ops(dep_file, wit_file)

        print(f"   - Loaded deposits: {len(deposits)}")
        print(f"   - Loaded withdrawals: {len(withdrawals)}")

        # SỬA LỖI: Truyền đủ 4 tham số vào hàm
        matches = match_baseline(deposits, withdrawals, TIME_WINDOW, VALUE_THRESHOLD)

        print(f"   ✅ Matches found: {len(matches)}")

        if matches:
            out_file = f"data/matched/{service}_matches.csv"
            pd.DataFrame(matches).to_csv(out_file, index=False)
            print(f"   💾 Saved to: {out_file}")
        else:
            print("   ℹ️ No matches found to save.")


if __name__ == "__main__":
    main()
