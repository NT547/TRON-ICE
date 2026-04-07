
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

            
def save_json(file_name,data):
    final_file = f"{file_name}.json"
    with open(final_file, "w", encoding="utf-8") as f:  
        json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Data is successfully saved in {file_name}")