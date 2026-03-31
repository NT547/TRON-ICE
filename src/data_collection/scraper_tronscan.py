import requests
import json
import os
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
import threading
import sys
# contract_address=TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t
# relatedAddress=TDoXUNZ6PajKuiUkcYg3EDSV9bnqGqsbcf
# Load environment variables
load_dotenv()
TRONSCAN_API_KEY = os.getenv("TRONSCAN_API_KEY")
CONTRACT_ADDRESS = os.getenv("contract_address")
RELATED_ADDRESS = os.getenv("relatedAddress")

URL = "https://apilist.tronscanapi.com/api/token_trc20/transfers"
HEADERS = {
    "Accept": "application/json",
    "TRON-PRO-API-KEY": TRONSCAN_API_KEY
}

# Thread locks and Stop Event
print_lock = threading.Lock()
data_lock = threading.Lock()   # Lock mới để bảo vệ lúc ghi vào list Global
stop_event = threading.Event() # Cờ tín hiệu để dừng các luồng khi có Ctrl+C

# Biến Global lưu toàn bộ dữ liệu theo thời gian thực
global_transfers = []

def fetch_time_chunk(start_date, end_date, chunk_id):
    """
    Fetches TRC20 transfers for a specific time range in a separate thread.
    Uses time-sliding window logic to bypass pagination limits.
    """
    chunk_transfers = []
    
    start_ts = int(start_date.timestamp() * 1000)
    current_end_ts = int(end_date.timestamp() * 1000)
    
    # Bổ sung điều kiện: Chỉ tiếp tục lặp nếu stop_event chưa được bật
    while current_end_ts >= start_ts and not stop_event.is_set():
        params = {
            "limit": 50,
            "start": 0,
            "contract_address": CONTRACT_ADDRESS,
            "relatedAddress": RELATED_ADDRESS,
            "confirm": "true",
            "filterTokenValue": 1,
            "start_timestamp": start_ts,        
            "end_timestamp": current_end_ts     
        }

        try:
            response = requests.get(URL, headers=HEADERS, params=params)
            
            if response.status_code == 429:
                with print_lock:
                    print(f"[Thread {chunk_id}] Rate Limit hit! Waiting 5s...")
                time.sleep(5) 
                continue
                
            response.raise_for_status()
            data = response.json()
            transfers = data.get("token_transfers", [])
            
            if not transfers:
                break 
                
            # Lưu vào list của luồng để tạo checkpoint
            chunk_transfers.extend(transfers)
            
            # Lưu ngay lập tức vào biến Global an toàn
            with data_lock:
                global_transfers.extend(transfers)
            
            last_tx_time = transfers[-1].get("block_ts")
            current_end_ts = last_tx_time - 1
            
            time.sleep(0.2) 

        except Exception as e:
            with print_lock:
                print(f"[Thread {chunk_id}] Error: {e}")
            break

    # Dù luồng chạy xong hay bị dừng ngang bởi Ctrl+C, nó vẫn tự xuất checkpoint những gì đã lấy được
    if chunk_transfers:
        filename = f"data/raw/chunk_{chunk_id}_{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(chunk_transfers, f, indent=4, ensure_ascii=False)
            
    with print_lock:
        if stop_event.is_set():
            print(f"⚠️ [Thread {chunk_id}] Stopped early! Collected {len(chunk_transfers)} txs.")
        else:
            print(f"✅ [Thread {chunk_id}] Completed! Collected {len(chunk_transfers)} txs.")
        
    return chunk_transfers

def scrape_multithreaded():
    os.makedirs("data/raw", exist_ok=True)
    
    end_date_global = datetime.now()
    start_date_global = end_date_global - timedelta(days=365)
    
    chunk_days = 30
    time_chunks = []
    
    current_start = start_date_global
    chunk_id = 1
    
    while current_start < end_date_global:
        current_end = current_start + timedelta(days=chunk_days)
        if current_end > end_date_global:
            current_end = end_date_global
        time_chunks.append((current_start, current_end, chunk_id))
        current_start = current_end
        chunk_id += 1

    print(f"🚀 Initializing {len(time_chunks)} scraping threads... (Press Ctrl+C to stop safely)")
    
    # Bọc ThreadPoolExecutor bằng Try-Except-Finally để bắt sự kiện Ctrl+C
    try:
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(fetch_time_chunk, start, end, cid) 
                for start, end, cid in time_chunks
            ]
            
            # Đợi các luồng chạy. Nếu có lỗi bên trong luồng, sẽ báo ở đây.
            for future in as_completed(futures):
                future.result()

    except KeyboardInterrupt:
        print("\n🛑 [WARNING] Ctrl+C detected! Signalling all threads to stop...")
        stop_event.set() # Bật cờ để các luồng tự thoát khỏi vòng lặp while
        print("⏳ Waiting for current requests to finish before saving data...")

    finally:
        # Khối Finally đảm bảo RẰNG DÙ BÌNH THƯỜNG HAY BỊ NGẮT, DATA VẪN LUÔN ĐƯỢC LƯU
        if global_transfers:
            final_file = f"data/raw/MERGED_all_txs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(final_file, "w", encoding="utf-8") as f:
                json.dump(global_transfers, f, indent=4, ensure_ascii=False)
            print(f"\n🎉 PROCESS ENDED! Safely saved {len(global_transfers)} total transactions into {final_file}")
        else:
            print("\n⚠️ No data was collected before stopping.")
            sys.exit(0)

if __name__ == "__main__":
    scrape_multithreaded()