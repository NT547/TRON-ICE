
from decimal import Decimal
import time
import json
import pandas as pd
import os
import datetime
import os
from src.utils.configs import print_lock




def ts_to_datetime(ts):
    """Convert timestamp (ms) → readable datetime"""
    return datetime.datetime.fromtimestamp(ts / 1000)

def safe_print(message, filename=None):
    """Utility to print safely across multiple threads without overlapping text."""
    with print_lock:
        print(message)
    log_dir = "results/logs/scaper/"
    os.makedirs(log_dir, exist_ok=True)
    if filename is None:
        filename = f"{filename}.log"
        
    LOG_FILE = os.path.join(log_dir, filename)
        
    # Ghi vào file log (chế độ 'a' = append)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(message + "\n")

def sleep_safe(seconds):
    """Sleep để tránh rate limit"""
    time.sleep(seconds)


def safe_get(d, keys, default=None):
    """Truy cập dict an toàn"""
    for k in keys:
        d = d.get(k, {})
    return d if d else default


def normalize_trx(value):
    """TRX (Sun → TRX)"""
    if value is None:
        return Decimal(0)

    if isinstance(value, str):
        value = int(value, 0)  # hỗ trợ hex

    return Decimal(value) / Decimal(1_000_000)


def normalize_token(value, decimals):
    if value is None:
        return Decimal(0)

    if isinstance(value, str):
        value = int(value, 0)  # auto detect hex/decimal

    decimals = int(decimals or 0)

    return Decimal(value) / (Decimal(10) ** decimals)


def is_incoming(tx_to, wallet):
    return tx_to.lower() == wallet.lower()


def is_outgoing(tx_from, wallet):
    return tx_from.lower() == wallet.lower()

ONLY_USDT = False
# ===== PARSE =====
<<<<<<< HEAD
def parse_trc20(tx):
    try:
        value = int(tx.get("value", 0))
        decimals = int(tx["token_info"].get("decimals", 0))

        return {
            "chain": "tron",
            "type": "TRC20",
            "txid": tx.get("transaction_id"),
            "from": tx.get("from"),
            "to": tx.get("to"),
            "value": value / (10 ** decimals),  # normalize
            "token": tx["token_info"].get("symbol"),
            "timestamp": tx.get("block_timestamp"),
        }

    except Exception:
        return None

def parse_trx(tx):
    try:
        contract = tx["raw_data"]["contract"][0]

        # check đúng loại
        if contract["type"] != "TransferContract":
            return None

        val = contract["parameter"]["value"]

        return {
            "chain": "tron",
            "type": "TRX",
            "txid": tx["txID"],
            "from": val.get("owner_address"),
            "to": val.get("to_address"),
            "value": normalize_trx(val.get("amount", 0)),  # convert sun → TRX
            "token": None,
            "timestamp": tx["block_timestamp"],
        }

    except Exception:
        return None
    
def proccess_raw_data(file_name):
    if os.path.exists(f"data/raw/{file_name}_trx.json"):
        with open(f'data/raw/{file_name}_trx.json', 'r', encoding='utf-8') as file:
            data = json.load(file)
            data_processed = []
            for tx in data:
                data_processed.append(parse_trx(tx))
            pd.DataFrame(data_processed).to_csv(f"data/processed/{file_name}_trx.csv", index=False)
            print(f"💾 Saved CSV: data/processed/{file_name}_trx.csv")

    if os.path.exists(f"data/raw/{file_name}_trc20.json"):
        with open(f'data/raw/{file_name}_trc20.json', 'r', encoding='utf-8') as file:
            data = json.load(file)
            data_processed = []
            for tx in data:
                data_processed.append(parse_trc20(tx))
            pd.DataFrame(data_processed).to_csv(f"data/processed/{file_name}_trc20.csv", index=False)
            print(f"💾 Saved CSV: data/processed/{file_name}_trc20.csv")
=======

            
def save_json(file_name,data):
    final_file = f"{file_name}.json"
    with open(final_file, "w", encoding="utf-8") as f:  
        json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Data is successfully saved in {file_name}")
>>>>>>> 28f005e (merging)
