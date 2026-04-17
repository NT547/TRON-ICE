
import json
import os
from datetime import datetime
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.utils.configs import stop_event
from src.data_collection.fetch_time_chunk import fetch_time_chunk, global_transfers


def scrape_multithreaded(URL, RELATED_ADDRESS, HEADER, PARAMS, file_name="trongrid_multithread", min_timestamp=None, max_timestamp=None, num_workers=5):
    os.makedirs("data/raw", exist_ok=True)
    
    # Set default timestamps if not provided
    if min_timestamp is None:
        min_timestamp = datetime(2023, 1, 1).timestamp() * 1000
    if max_timestamp is None:
        max_timestamp = datetime(2023, 12, 31, 23, 59, 59).timestamp() * 1000

    print(f"🚀 STARTING DYNAMIC QUEUE SCRAPE: {RELATED_ADDRESS}")
    
    # ---------------------------------------------------------
    # BƯỚC NGOẶT: BĂM NHỎ THỜI GIAN THÀNH TỪNG NGÀY (MICRO-SLICING)
    # ---------------------------------------------------------
    time_chunks = []
    current_ts = min_timestamp
    one_day_ms = 24 * 60 * 60 * 1000
    chunk_id = 1
    
    while current_ts < max_timestamp:
        # Đảm bảo cục cuối cùng không vượt qua max_timestamp
        end_ts = min(current_ts + one_day_ms - 1, max_timestamp)
        time_chunks.append((chunk_id, current_ts, end_ts))
        current_ts += one_day_ms
        chunk_id += 1

    print(f"🧮 Băm nhỏ thành {len(time_chunks)} tasks (ngày). Khởi động {num_workers} Workers... (Nhấn Ctrl+C để dừng an toàn)")

    # Execute with ThreadPool
    # ThreadPoolExecutor sẽ tự động đẩy 365 tasks này vào Queue nội bộ của nó.
    # num_workers sẽ tự động kéo task ra làm, xong task này bốc task khác.
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        try:
            futures = [
                executor.submit(fetch_time_chunk, chunk_id, start, end, file_name, URL, HEADER, PARAMS) 
                for chunk_id, start, end in time_chunks
            ]
            
            for future in as_completed(futures):
                # Bắt lỗi nếu có exception ném ra từ bên trong thread
                future.result() 

        except KeyboardInterrupt:
            print("\n🛑 [WARNING] Ctrl+C detected! Sending stop signals to all threads...")
            stop_event.set()
            print("⏳ Waiting for ongoing requests to finish before saving...")

    # Aggregation and Save Block
    if global_transfers:
        print("\n🧹 Sorting gathered data chronologically...")
        # Sort by block_timestamp ascending (oldest to newest) 
        global_transfers.sort(key=lambda x: x.get('block_timestamp', 0))
        
        final_file = f"data/raw/{file_name}.json"
        with open(final_file, "w", encoding="utf-8") as f:
            json.dump(global_transfers, f, indent=2, ensure_ascii=False)
        
        print(f"🎉 PROCESS FINISHED! Safely saved {len(global_transfers)} total transactions to {final_file}\n")
        global_transfers.clear()
    else:
        print("\n⚠️ No data was collected.\n")
        sys.exit(0)
        