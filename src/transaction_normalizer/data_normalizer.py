# Module: data_normalizer.py
import pandas as pd
from src.transaction_normalizer.base58 import hex_to_base58

def normalize_trx_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
    """Chuẩn hóa trực tiếp một chunk DataFrame TRX"""
    if chunk.empty:
        return pd.DataFrame()
    
    norm = pd.DataFrame()
    norm['timestamp'] = chunk['block_timestamp']
    
    # Hàm extract logic cho TRX
    def extract_trx_data(raw):
        if not isinstance(raw, dict): return None, None, 0
        contract = raw.get("contract", [{}])[0] if raw.get("contract") else {}
        val = contract.get("parameter", {}).get("value", {})
        return val.get("owner_address"), val.get("to_address"), val.get("amount", 0)
    
    extracted = chunk['raw_data'].apply(extract_trx_data)
    norm['from'] = extracted.apply(lambda x: hex_to_base58(x[0]) if x and x[0] else None)
    norm['to'] = extracted.apply(lambda x: hex_to_base58(x[1]) if x and x[1] else None)
    norm['amount'] = extracted.apply(lambda x: float(x[2]) / 1e6 if x and x[2] else 0.0)
    norm['token'] = 'TRX'
    
    # Loại bỏ các dòng không hợp lệ
    return norm.dropna(subset=['from', 'to']).copy()

def normalize_trc20_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
    """Chuẩn hóa trực tiếp một chunk DataFrame TRC20"""
    if chunk.empty:
        return pd.DataFrame()
        
    norm = pd.DataFrame()
    norm['timestamp'] = chunk['block_timestamp']
    norm['from'] = chunk['from']
    norm['to'] = chunk['to']
    
    def extract_amount(row):
        val = float(row.get('value', 0))
        t_info = row.get('token_info', {})
        if isinstance(t_info, dict):
            decimals = int(t_info.get("decimals", 0))
            return val / (10 ** decimals) if decimals else val
        return val
        
    norm['amount'] = chunk.apply(extract_amount, axis=1)
    
    def extract_token(t_info):
        if isinstance(t_info, dict):
            return t_info.get("symbol", "UNKNOWN")
        return "UNKNOWN"
        
    norm['token'] = chunk['token_info'].apply(extract_token)
    
    return norm.dropna(subset=['from', 'to']).copy()