import pandas as pd
import numpy as np
import glob
import os

def labeling_positive(input_dir: str = 'data/matched/', output_dir: str = 'data/ground_truth/positives/'):
    """
    Gán nhãn 1 (Positive) cho các cặp giao dịch đã được khớp từ trước.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    matched_csvs = glob.glob(os.path.join(input_dir, "*.csv"))
    if not matched_csvs:
        print(f"⚠️ Không tìm thấy file CSV nào trong {input_dir}")
        return

    chunk_size = 100000 
    print(f"Bắt đầu xử lý {len(matched_csvs)} file để gán nhãn Positive...")

    for matched_csv in matched_csvs:
        file_name = os.path.basename(matched_csv).replace('_matches', '_positive')
        output_file = os.path.join(output_dir, file_name)
        
        first_chunk = True
        for chunk in pd.read_csv(matched_csv, chunksize=chunk_size):
            # Gán nhãn 1 cho dữ liệu đã khớp
            chunk['label'] = 1
            
            # Lưu ra file (Lần đầu ghi đè tạo header, các lần sau ghi nối tiếp append)
            mode = 'w' if first_chunk else 'a'
            chunk.to_csv(output_file, index=False, mode=mode, header=first_chunk)
            first_chunk = False

        print(f"  -> Đã gán nhãn và lưu: {output_file}")

    print("✅ Gán nhãn Positive hoàn tất!\n")



def labeling_negative(input_dir: str = "data/classified", output_dir: str = 'data/ground_truth/negative/'):
    """
    Tạo dữ liệu Nhãn 0 (Negative) bằng cách ghép ngẫu nhiên lệnh Nạp và Rút.
    Cấu trúc đầu ra ĐỒNG BỘ 100% với thuật toán heuristic match_baseline_streaming.
    """
    os.makedirs(output_dir, exist_ok=True)

    deposit_files = glob.glob(os.path.join(input_dir, "*_deposits.csv"))
    
    if not deposit_files:
        print(f"⚠️ Không tìm thấy file *_deposits.csv nào trong {input_dir}")
        return

    print(f"Bắt đầu xử lý tạo nhãn Negative từ {len(deposit_files)} sàn...")

    for dep_file in deposit_files:
        filename = os.path.basename(dep_file)
        service_name = filename.replace("_deposits.csv", "")
        
        wit_file = os.path.join(input_dir, f"{service_name}_withdrawals.csv")
        
        if not os.path.exists(wit_file):
            print(f"  [Bỏ qua] Không tìm thấy file rút tiền cho sàn {service_name}")
            continue

        # 1. Đọc dữ liệu và xử lý Drop NA giống hệt logic stream của bạn
        df_dep = pd.read_csv(dep_file)
        df_wit = pd.read_csv(wit_file)
        
        df_dep = df_dep.dropna(subset=['txid', 'value', 'timestamp'])
        df_wit = df_wit.dropna(subset=['txid', 'value', 'timestamp'])

        # 2. Xử lý số lượng tối đa có thể lấy mẫu
        NUM_NEGATIVE_SAMPLES = 3000000
        max_samples = min(NUM_NEGATIVE_SAMPLES, len(df_dep), len(df_wit))
        
        if max_samples == 0:
            print(f"  [Bỏ qua] Sàn {service_name} không đủ dữ liệu.")
            continue

        # 3. Lấy mẫu ngẫu nhiên
        rand_dep = df_dep.sample(n=max_samples, random_state=42).reset_index(drop=True)
        rand_wit = df_wit.sample(n=max_samples, random_state=99).reset_index(drop=True)

        # 4. Đổi tên cột sao cho khớp chính xác với Dictionary matches của bạn
        rand_dep = rand_dep.rename(columns={'txid': 'deposit_tx', 'value': 'value_dep', 'timestamp': 'time_in'})
        rand_wit = rand_wit.rename(columns={'txid': 'withdraw_tx', 'value': 'value_wit', 'timestamp': 'time_out'})

        # 5. Ghép ngang hai bảng dữ liệu (Chỉ lấy các cột cần thiết)
        df_neg = pd.concat([
            rand_dep[['deposit_tx', 'value_dep', 'time_in']], 
            rand_wit[['withdraw_tx', 'value_wit', 'time_out']]
        ], axis=1)

        # 6. Tính toán công thức y hệt Baseline
        # time_diff_sec: Chia 1000.0 vì timestamp gốc là milliseconds
        df_neg['time_diff_sec'] = (df_neg['time_out'] - df_neg['time_in']) / 1000.0

        # value_diff_ratio: abs(val_dep - val_wit) / max(val_dep, val_wit)
        max_values = df_neg[['value_dep', 'value_wit']].max(axis=1)
        df_neg['value_diff_ratio'] = np.where(
            max_values > 0,
            abs(df_neg['value_dep'] - df_neg['value_wit']) / max_values,
            np.inf # Nếu cả 2 đều bằng 0 thì gán vô cực giống hàm calculate_value_diff_ratio
        )
        
        # Làm tròn 4 chữ số thập phân giống hàm round() ở Baseline
        df_neg['value_diff_ratio'] = df_neg['value_diff_ratio'].round(4)

        # 7. Gán nhãn 0 (Negative)
        df_neg['label'] = 0

        # 8. Sắp xếp lại thứ tự cột cho ĐẸP và KHỚP với file matches
        final_columns = [
            'deposit_tx', 'withdraw_tx', 'value_diff_ratio', 
            'value_dep', 'value_wit', 'time_diff_sec', 
            'time_in', 'time_out', 'label'
        ]
        df_neg = df_neg[final_columns]

        # Lọc những ca tình cờ "Quá hoàn hảo" (VD: Lệch < 1 tiếng và sai số giá trị < 5%)
        df_neg = df_neg[~((df_neg['time_diff_sec'] >= 0) & 
                          (df_neg['time_diff_sec'] <= 3600) & 
                          (df_neg['value_diff_ratio'] <= 0.05))]

        # 9. Lưu file
        output_file = os.path.join(output_dir, f"{service_name}_negative.csv")
        df_neg.to_csv(output_file, index=False)
        print(f"  -> Đã tạo thành công {len(df_neg)} mẫu Negative chuẩn format cho {service_name}!")

    print("✅ Xử lý gán nhãn Negative hoàn tất!\n")

# Chạy thử nghiệm
