import pandas as pd
import copy
import json
from datetime import datetime
from src.utils.configs import HEADER, HOT_WALLETS , CONTRACT_ADDRESS, URL_TRC20, URL_TRX, params
from src.utils.helper import parse_trx, parse_trc20
from src.data_collection.scaper_multithreaded  import  scrape_multithreaded   

file_name="trongrid_changenow_2025"

with open(f'data/raw/{file_name}_trx.json', 'r', encoding='utf-8') as file:
    data = json.load(file)
    data_processed = []
    for tx in data:
        parsed = parse_trc20(tx)
        if parsed:
            data_processed.append(parsed)
pd.DataFrame(data_processed).to_csv(f"data/processed/{file_name}_trx.csv", index=False)
print(f"💾 Saved CSV: data/processed/{file_name}_trx.csv")
