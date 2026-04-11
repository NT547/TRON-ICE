import pandas as pd
import os
import glob
from typing import Iterator, Dict, Any

# Đã bỏ HOT_WALLETS, chỉ giữ lại các tham số cấu hình thuật toán
from src.utils.configs import TIME_WINDOW, VALUE_THRESHOLD

# ==========================================
# CÁC HÀM TIỆN ÍCH (UTILITY FUNCTIONS)
# ==========================================

def read_transactions_stream(file_path: str, chunk_size: int = 100000) -> Iterator[Dict[str, Any]]:
    """
    Sử dụng Generator để đọc file CSV khổng lồ mà không tràn RAM.
    """
    if not os.path.exists(file_path):
        return
        
    dtypes = {"txid": str, "value": float, "timestamp": float}
    
    for chunk in pd.read_csv(file_path, chunksize=chunk_size, dtype=dtypes):
        chunk = chunk.dropna(subset=['txid', 'value', 'timestamp'])
        for record in chunk.to_dict('records'):
            yield record

def calculate_value_diff_ratio(val_deposit: float, val_withdraw: float) -> float:
    """Tính tỷ lệ chênh lệch giá trị giữa nạp và rút."""
    if val_deposit <= 0 or val_withdraw <= 0:
        return float("inf")
    return abs(val_deposit - val_withdraw) / max(val_deposit, val_withdraw)


# ==========================================
# HÀM THUẬT TOÁN LÕI DÙNG SLIDING WINDOW
# ==========================================

def match_baseline_streaming(dep_file: str, wit_file: str, out_file: str, 
                             time_window: int, value_threshold: float) -> int:
    """
    Thuật toán Sliding Window Heuristic cho Big Data.
    """
    dep_stream = read_transactions_stream(dep_file)
    wit_stream = read_transactions_stream(wit_file)
    
    withdraw_buffer = []  
    used_withdrawals = set()
    
    matches = []
    total_matches = 0
    first_write = True  
    
    try:
        next_w = next(wit_stream)
    except StopIteration:
        return 0 

    print("   ⏳ Đang quét dữ liệu bằng Sliding Window...")

    for deposit in dep_stream:
        d_time = deposit["timestamp"]
        
        while next_w is not None and ((next_w["timestamp"] - d_time) / 1000.0) <= time_window:
            withdraw_buffer.append(next_w)
            try:
                next_w = next(wit_stream)
            except StopIteration:
                next_w = None
                
        active_buffer = []
        for w in withdraw_buffer:
            if w["txid"] in used_withdrawals:
                continue
            
            time_diff_sec = (w["timestamp"] - d_time) / 1000.0
            if time_diff_sec < 0:
                used_withdrawals.discard(w["txid"]) 
                continue
                
            active_buffer.append(w)
            
        withdraw_buffer = active_buffer
        
        best_withdrawal = None
        best_score = float("inf")
        
        for w in withdraw_buffer:
            val_diff = calculate_value_diff_ratio(deposit["value"], w["value"])
            if val_diff <= value_threshold and val_diff < best_score:
                best_score = val_diff
                best_withdrawal = w
                
        if best_withdrawal:
            matches.append({
                "deposit_tx": deposit["txid"],
                "withdraw_tx": best_withdrawal["txid"],
                "value_diff_ratio": round(best_score, 4),
                "time_diff_sec": (best_withdrawal["timestamp"] - d_time) / 1000.0,
                "value_dep": deposit["value"],
                "value_wit": best_withdrawal["value"],
            })
            used_withdrawals.add(best_withdrawal["txid"])
            
            if len(matches) >= 10000:
                pd.DataFrame(matches).to_csv(out_file, mode='a', index=False, header=first_write)
                first_write = False
                total_matches += len(matches)
                matches.clear()

    if matches:
        pd.DataFrame(matches).to_csv(out_file, mode='a', index=False, header=first_write)
        total_matches += len(matches)

    return total_matches


# ==========================================
# HÀM ĐIỀU PHỐI (CONTROLLER)
# ==========================================

def process_file_pair(dep_file: str, wit_file: str, service_name: str, output_dir: str = "data/matched"):
    """Thực hiện luồng khớp lệnh cho một cặp file cụ thể."""
    print(f"\n=== PROCESSING: {service_name} ===")

    if not os.path.exists(dep_file) or not os.path.exists(wit_file):
        print(f"⚠️ Thiếu file withdrawal tương ứng cho {service_name}, bỏ qua...")
        return

    os.makedirs(output_dir, exist_ok=True)
    out_file = os.path.join(output_dir, f"{service_name}_matches.csv")
    
    if os.path.exists(out_file):
        os.remove(out_file)

    total_matches = match_baseline_streaming(dep_file, wit_file, out_file, TIME_WINDOW, VALUE_THRESHOLD)

    if total_matches > 0:
        print(f"   ✅ Matches found: {total_matches}")
        print(f"   💾 Saved to: {out_file}")
    else:
        print("   ℹ️ Không tìm thấy cặp khớp nối nào.")

# ==========================================
# ENTRY POINT
# ==========================================

def matching(input_dir: str = "data/classified", output_dir: str = "data/matched"):
    if not os.path.exists(input_dir):
        print(f"❌ Thư mục {input_dir} không tồn tại!")
        return

    # Tự động quét tất cả các file có đuôi _deposits.csv
    deposit_files = glob.glob(os.path.join(input_dir, "*_deposits.csv"))
    
    if not deposit_files:
        print(f"⚠️ Không tìm thấy file *_deposits.csv nào trong {input_dir}")
        return

    for dep_file in deposit_files:
        # Lấy tên gốc của file (Ví dụ: từ "ChangeNOW_deposits.csv" -> "ChangeNOW")
        filename = os.path.basename(dep_file)
        service_name = filename.replace("_deposits.csv", "")
        
        # Tự động suy ra tên file withdrawal tương ứng
        wit_file = os.path.join(input_dir, f"{service_name}_withdrawals.csv")
        
        # Chạy thuật toán cho cặp file này
        process_file_pair(dep_file, wit_file, service_name, output_dir)
