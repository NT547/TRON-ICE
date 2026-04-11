
import requests
import time
import copy
from datetime import datetime
from src.utils.configs import TRONGRID_API, chunk_transfers, global_transfers, data_lock, stop_event
from src.utils.helper import safe_print


def fetch_time_chunk(chunk_id, min_ts, max_ts, file_name, URL, HEADERS, PARAMS):
    """
    Worker function: Scrapes TronGrid for a specific time window.
    """
    # CHÚ Ý LỚN: Biến này phải là biến cục bộ để Thread tự đếm số lượng của riêng nó
    chunk_transfers = [] 

    # Tránh việc tham chiếu chéo (mutate shared variable)
    params = copy.deepcopy(PARAMS)
    params["min_timestamp"] = int(min_ts)
    params["max_timestamp"] = int(max_ts)
    
    start_date_str = datetime.fromtimestamp(min_ts/1000).strftime('%Y-%m-%d')
    end_date_str = datetime.fromtimestamp(max_ts/1000).strftime('%Y-%m-%d')
    
    safe_print(f"🧵 [Task {chunk_id}] Started: {start_date_str} to {end_date_str}", f"{file_name}.log")

    fingerprint = None
    page = 1
    
    try:
        while not stop_event.is_set():
            if fingerprint:
                params["fingerprint"] = fingerprint

            response = requests.get(URL, headers=HEADERS, params=params)
            
            # Handle Rate Limit
            if response.status_code == 429:
                safe_print(f"⚠️ [Task {chunk_id}] Rate Limit hit! Sleeping for 5s...", f"{file_name}.log")
                time.sleep(5) # Đồng bộ với log
                continue
                
            response.raise_for_status()
            data = response.json()
            
            transfers = data.get("data", [])
            if not transfers:
                break
                
            chunk_transfers.extend(transfers)
            
            # Safely append to global list
            with data_lock:
                global_transfers.extend(transfers)
                
            # Extract fingerprint
            meta = data.get("meta", {})
            fingerprint = meta.get("fingerprint")
            
            current_time_reached = datetime.fromtimestamp(transfers[-1]['block_timestamp'] / 1000).strftime('%Y-%m-%d %H:%M:%S')
            safe_print(f"   ↳ [Task {chunk_id}] Page {page} | Got {len(transfers)} txs | Reached: {current_time_reached}", f"{file_name}.log")
            
            if not fingerprint:
                break
                
            page += 1
            time.sleep(0.5) # Protect API Key

    except Exception as e:
        safe_print(f"❌ [Task {chunk_id}] API Error: {e}", f"{file_name}.log")

    # Final status log for this thread chunk
    if stop_event.is_set():
        safe_print(f"🛑 [Task {chunk_id}] Stopped early! Collected {len(chunk_transfers)} txs.", f"{file_name}.log")
    else:
        # Nếu không thu được tx nào, in nhẹ nhàng để đỡ rối log
        if len(chunk_transfers) > 0:
            safe_print(f"✅ [Task {chunk_id}] Finished {start_date_str}! Collected {len(chunk_transfers)} txs.", f"{file_name}.log")