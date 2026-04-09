
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

    print(f"🚀 STARTING MULTITHREADED SCRAPE: {RELATED_ADDRESS}")
    print(f"🧮 Dividing time range into {num_workers} chunks... (Press Ctrl+C to stop safely)")

    # Calculate equal time chunks
    total_time = max_timestamp - min_timestamp
    chunk_duration = total_time // num_workers
    time_chunks = []

    for i in range(num_workers):
        start_ts = min_timestamp + (i * chunk_duration)
        # For the last chunk, ensure it goes exactly to the max_timestamp
        if i == num_workers - 1:
            end_ts = max_timestamp
        else:
            # End just 1ms before the next chunk starts to prevent duplicates
            end_ts = start_ts + chunk_duration - 1
            
        time_chunks.append((i + 1, start_ts, end_ts))

    # Execute with ThreadPool
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        try:
            futures = [
                executor.submit(fetch_time_chunk, chunk_id, start, end, file_name,URL, HEADER, PARAMS) 
                for chunk_id, start, end in time_chunks
            ]
            
            for future in as_completed(futures):
                future.result()

        except KeyboardInterrupt:
            print("\n🛑 [WARNING] Ctrl+C detected! Sending stop signals to all threads...")
            stop_event.set()
            print("⏳ Waiting for ongoing requests to finish before saving...")

    # Aggregation and Save Block
    if global_transfers:
        print("\n🧹 Sorting gathered data chronologically...")
        # Sort by block_timestamp ascending (oldest to newest) since threads finish at random times
        global_transfers.sort(key=lambda x: x.get('block_timestamp', 0))
        
        final_file = f"data/raw/{file_name}.json"
        with open(final_file, "w", encoding="utf-8") as f:
            json.dump(global_transfers, f, indent=2, ensure_ascii=False)
        
        print(f"🎉 PROCESS FINISHED! Safely saved {len(global_transfers)} total transactions to {final_file}\n")
        global_transfers.clear()
    else:
        print("\n⚠️ No data was collected.\n")
        sys.exit(0)
        