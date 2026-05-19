# Module: deposit_address_finder.py
import pandas as pd
from collections import Counter
from typing import List, Optional
from .data_loader import load_trx_chunks, load_trc20_chunks
from .data_normalizer import normalize_trx_chunk, normalize_trc20_chunk

def is_contract_address(address: Optional[str]) -> bool:
    if not isinstance(address, str): return False
    return address.startswith("T9") or address.startswith("41")

def find_deposit_addresses_from_files(
    trx_file: str, trc20_file: str, hot_wallet: str, min_frequency: int = 5
) -> List[str]:
    
    freq = Counter()
    
    def process_frequency(generator, is_trx):
        for raw_chunk in generator:
            if raw_chunk.empty: continue
            norm = normalize_trx_chunk(raw_chunk) if is_trx else normalize_trc20_chunk(raw_chunk)
            if norm.empty: continue
            
            # Chỉ lấy các giao dịch vào ví hot_wallet
            to_hot = norm[norm['to'] == hot_wallet]
            if to_hot.empty: continue
            
            # Lọc bỏ contract logic và đưa vào biến đếm
            candidates = to_hot['from'][~to_hot['from'].apply(is_contract_address)]
            freq.update(candidates)
            
    process_frequency(load_trx_chunks(trx_file), is_trx=True)
    process_frequency(load_trc20_chunks(trc20_file), is_trx=False)
    
    # Chỉ giữ địa chỉ đạt đủ tần suất min_frequency
    deposit_addresses = [addr for addr, count in freq.items() if count >= min_frequency]
    return deposit_addresses