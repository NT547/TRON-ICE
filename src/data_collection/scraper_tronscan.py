import requests
import json
import os
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
import threading

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

# Thread lock to prevent console output overlap
print_lock = threading.Lock()

def fetch_time_chunk(start_date, end_date, chunk_id):
    """
    Fetches TRC20 transfers for a specific time range in a separate thread.
    Uses time-sliding window logic to bypass pagination limits.
    """
    chunk_transfers = []
    
    # Convert datetime to millisecond timestamps
    start_ts = int(start_date.timestamp() * 1000)
    current_end_ts = int(end_date.timestamp() * 1000)
    
    while current_end_ts >= start_ts:
        params = {
            "limit": 50,
            "start": 0,
            "contract_address": CONTRACT_ADDRESS,
            "relatedAddress": RELATED_ADDRESS,
            "confirm": "true",
            "filterTokenValue": 1,
            "start_timestamp": start_ts,        # Floor limit
            "end_timestamp": current_end_ts     # Sliding ceiling limit
        }

        try:
            response = requests.get(URL, headers=HEADERS, params=params)
            
            if response.status_code == 429:
                with print_lock:
                    print(f"[Thread {chunk_id}] Rate Limit hit! Waiting 5s...")
                time.sleep(5) # Set to 5s for safety during rate limit
                continue
                
            response.raise_for_status()
            data = response.json()
            transfers = data.get("token_transfers", [])
            
            if not transfers:
                break # No more data in this time range
                
            chunk_transfers.extend(transfers)
            
            # Slide time window backward
            last_tx_time = transfers[-1].get("block_ts")
            current_end_ts = last_tx_time - 1
            
            time.sleep(0.2) # Small delay to respect API limits

        except Exception as e:
            with print_lock:
                print(f"[Thread {chunk_id}] Error: {e}")
            break

    # Save checkpoint for each chunk to prevent data loss
    if chunk_transfers:
        filename = f"data/raw/chunk_{chunk_id}_{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(chunk_transfers, f, indent=4, ensure_ascii=False)
            
    with print_lock:
        print(f"✅ [Thread {chunk_id}] Completed! Collected {len(chunk_transfers)} txs.")
        
    return chunk_transfers

def scrape_multithreaded():
    # Ensure directory exists
    os.makedirs("data/raw", exist_ok=True)
    
    # 1. CONFIGURE TIME RANGE
    # Scrape data from the last 365 days
    end_date_global = datetime.now()
    start_date_global = end_date_global - timedelta(days=365)
    
    # Divide into 30-day chunks
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

    print(f"🚀 Initializing {len(time_chunks)} scraping threads...")
    
    all_final_transfers = []
    
    # 2. INITIALIZE THREAD POOL
    # Recommendation: Keep max_workers between 3-5 to avoid IP ban
    with ThreadPoolExecutor(max_workers=5) as executor:
        # Submit tasks to the pool
        futures = [
            executor.submit(fetch_time_chunk, start, end, cid) 
            for start, end, cid in time_chunks
        ]
        
        # Aggregate results as threads finish
        for future in as_completed(futures):
            result = future.result()
            all_final_transfers.extend(result)

    # 3. MERGE ALL DATA
    if all_final_transfers:
        final_file = f"data/raw/MERGED_all_txs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(final_file, "w", encoding="utf-8") as f:
            json.dump(all_final_transfers, f, indent=4, ensure_ascii=False)
        print(f"\n🎉 PROCESS COMPLETE! Merged {len(all_final_transfers)} total transactions into {final_file}")

if __name__ == "__main__":
    scrape_multithreaded()