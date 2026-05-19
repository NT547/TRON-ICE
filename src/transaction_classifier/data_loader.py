# Module: data_loader.py
import os
import ast
import json
import glob
import pandas as pd
from typing import Iterator
from src.utils.helper import load_csv

def parse_json_col(val):
    """Hàm vector hóa ép kiểu JSON từ chuỗi cho Pandas"""
    if pd.isna(val):
        return val
    if isinstance(val, str) and (val.startswith('{') or val.startswith('[')):
        try:
            return ast.literal_eval(val)
        except (ValueError, SyntaxError):
            try:
                return json.loads(val.replace("'", '"'))
            except json.JSONDecodeError:
                return val
    return val

def load_csv_chunks(file_path: str) -> Iterator[pd.DataFrame]:
    """Generator sinh ra các chunk DataFrame đã được ép kiểu JSON"""
    if ".json" in file_path:
        file_path = file_path.replace(".json", ".csv")

    files = glob.glob(file_path)
    if not files:
        return
    
    for f_path in files:
        for chunk in load_csv(f_path):
            # Tự động parse JSON trực tiếp trên cột DataFrame
            for col in ['raw_data', 'token_info']:
                if col in chunk.columns:
                    chunk[col] = chunk[col].apply(parse_json_col)
            yield chunk

def load_trx_chunks(file_path: str) -> Iterator[pd.DataFrame]:
    yield from load_csv_chunks(file_path)

def load_trc20_chunks(file_path: str) -> Iterator[pd.DataFrame]:
    yield from load_csv_chunks(file_path)