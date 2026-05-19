# Module: transaction_classifier.py
# Chức năng: Đọc CSV, phân loại nạp/rút, TÁCH RIÊNG file samples và GHI LOG.

import os
import glob
import pandas as pd
from typing import List, Dict, Any
from src.utils.helper import save_csv_in_chunks

def run_transaction_classifer(
    trx_file: str, trc20_file: str, hot_wallet: str, min_frequency: int = 5
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Pipeline phân loại giao dịch trực tiếp từ CSV.
    Tự động tách riêng dữ liệu thuộc file '_samples' ra một file CSV riêng biệt
    và ghi lại log toàn bộ quá trình.
    """
    trx_csv_pattern = trx_file.replace(".json", ".csv") if ".json" in trx_file else trx_file
    trc20_csv_pattern = trc20_file.replace(".json", ".csv") if ".json" in trc20_file else trc20_file

    # Lấy base_name để đặt tên file log và file output
    base_name_clean = os.path.basename(trx_file).replace(".json", "").replace(".csv", "").replace("*", "").replace("_trx", "")
    
    # --- THIẾT LẬP GHI LOG ---
    log_dir = "results/logs/classifier"
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, f"classifier_{base_name_clean}.log")
    
    # Mở file log ở chế độ ghi
    with open(log_file_path, "w", encoding="utf-8") as log_file:
        
        # Hàm phụ trợ: Vừa in ra màn hình, vừa ghi vào file log
        def log_msg(msg: str):
            print(msg)
            log_file.write(msg + "\n")
            
        log_msg("=== BẮT ĐẦU PIPELINE PHÂN LOẠI GIAO DỊCH (CSV) ===")

        files_to_process = set(glob.glob(trx_csv_pattern) + glob.glob(trc20_csv_pattern))
        
        if not files_to_process:
            log_msg(f"[CẢNH BÁO] Không tìm thấy file dữ liệu nào khớp với {trx_csv_pattern} hoặc {trc20_csv_pattern}")
            return {"deposits": [], "withdrawals": []}

        # Tạo 2 nhóm lưu trữ: 1 cho file thường, 1 cho file samples
        dep_chunks_regular, wth_chunks_regular = [], []
        dep_chunks_samples, wth_chunks_samples = [], []

        for file_path in files_to_process:
            log_msg(f"Đang xử lý file: {file_path}")
            
            # Nhận diện xem file này có phải là file mẫu (samples) không
            is_sample = "_samples" in file_path.lower()
            
            for chunk in pd.read_csv(file_path, chunksize=100000):
                if chunk.empty:
                    continue
                
                # --- BỔ SUNG & ĐIỀU CHỈNH CÁC TRƯỜNG ---
                if 'value' in chunk.columns and 'amount' not in chunk.columns:
                    chunk = chunk.rename(columns={'value': 'amount'})
                
                if 'timestamp' in chunk.columns:
                    chunk['timestamp'] = pd.to_numeric(chunk['timestamp'], errors='coerce').fillna(0).astype(int)
                
                if 'txid' not in chunk.columns:
                    chunk['txid'] = chunk['from'].astype(str) + '_' + chunk['timestamp'].astype(str) + '_' + chunk['to'].astype(str)

                # --- PHÂN LOẠI (CLASSIFY) ---
                deposits = chunk[(chunk['to'] == hot_wallet) & (chunk['from'] != hot_wallet)]
                withdrawals = chunk[(chunk['from'] == hot_wallet) & (chunk['to'] != hot_wallet)]
                
                # Đưa vào đúng nhóm (Samples hoặc Regular)
                if is_sample:
                    if not deposits.empty: dep_chunks_samples.append(deposits.copy())
                    if not withdrawals.empty: wth_chunks_samples.append(withdrawals.copy())
                else:
                    if not deposits.empty: dep_chunks_regular.append(deposits.copy())
                    if not withdrawals.empty: wth_chunks_regular.append(withdrawals.copy())

        os.makedirs("data/classified", exist_ok=True)
        
        # File thường
        deposits_file = os.path.join("data/classified", f"deposits_{base_name_clean}.csv")
        withdrawals_file = os.path.join("data/classified", f"withdrawals_{base_name_clean}.csv")
        
        # File samples
        deposits_samples_file = os.path.join("data/classified", f"deposits_{base_name_clean}_samples.csv")
        withdrawals_samples_file = os.path.join("data/classified", f"withdrawals_{base_name_clean}_samples.csv")

        # --- LƯU RA Ổ ĐĨA ---
        log_msg("Đang lưu dữ liệu ra file CSV...")
        if dep_chunks_regular: save_csv_in_chunks(dep_chunks_regular, deposits_file)
        if wth_chunks_regular: save_csv_in_chunks(wth_chunks_regular, withdrawals_file)
        
        if dep_chunks_samples: save_csv_in_chunks(dep_chunks_samples, deposits_samples_file)
        if wth_chunks_samples: save_csv_in_chunks(wth_chunks_samples, withdrawals_samples_file)

        # --- TRẢ VỀ DỮ LIỆU GỘP CHO MAIN.PY ---
        all_dep = dep_chunks_regular + dep_chunks_samples
        all_wth = wth_chunks_regular + wth_chunks_samples

        df_deposits = pd.concat(all_dep, ignore_index=True) if all_dep else pd.DataFrame()
        df_withdrawals = pd.concat(all_wth, ignore_index=True) if all_wth else pd.DataFrame()

        ret_deposits = df_deposits.where(pd.notnull(df_deposits), None).to_dict('records') if not df_deposits.empty else []
        ret_withdrawals = df_withdrawals.where(pd.notnull(df_withdrawals), None).to_dict('records') if not df_withdrawals.empty else []

        log_msg("=== TỔNG KẾT ===")
        log_msg(f" - [Dữ liệu thường]  Deposits: {sum(len(c) for c in dep_chunks_regular)} | Withdrawals: {sum(len(c) for c in wth_chunks_regular)}")
        log_msg(f" - [Dữ liệu samples] Deposits: {sum(len(c) for c in dep_chunks_samples)} | Withdrawals: {sum(len(c) for c in wth_chunks_samples)}")
        log_msg(f"Log đã được lưu tại: {log_file_path}")
        
        return {"deposits": ret_deposits, "withdrawals": ret_withdrawals}

