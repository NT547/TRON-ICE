import json
import logging
import os
from typing import List, Dict, Any


def load_trx_data(file_path: str) -> List[Dict[str, Any]]:
    """
    Load TRX transactions from JSON file.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"TRX data file not found: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    trx_data = data if isinstance(data, list) else []
    logging.info(f"Loaded {len(trx_data)} TRX transactions from {file_path}")
    return trx_data


def load_trc20_data(file_path: str) -> List[Dict[str, Any]]:
    """
    Load TRC-20 transactions from JSON file.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"TRC-20 data file not found: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    trc20_data = data if isinstance(data, list) else []
    logging.info(f"Loaded {len(trc20_data)} TRC-20 transactions from {file_path}")
    return trc20_data


def load_transactions(
    trx_file: str, trc20_file: str
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Load both TRX and TRC-20 transactions.
    """
    trx_data = load_trx_data(trx_file)
    trc20_data = load_trc20_data(trc20_file)
    return {"trx": trx_data, "trc20": trc20_data}
