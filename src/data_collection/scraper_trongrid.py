import pandas as pd
import json
import os
import copy
from datetime import datetime
from src.utils.configs import HEADER, HOT_WALLETS , CONTRACT_ADDRESS, URL_TRC20, URL_TRX, params, global_transfers
from src.utils.helper import parse_trx, parse_trc20
from src.data_collection.scaper_multithreaded  import  scrape_multithreaded

def scaping_trongrid(service, file_name=None,year=datetime.now().year, ):

    if file_name is None:
        file_name = f"trongrid_{service}_{year}"
    else:
        file_name = f"{file_name}_{service}_{year}"
        
        
    min_ts = datetime(year, 1, 1).timestamp() * 1000
    max_ts = datetime(year, 12, 31, 23, 59, 59).timestamp() * 1000
    PARAMS = copy.deepcopy(params)
    
    scrape_multithreaded(
        URL=URL_TRX.replace("_RELATED_ADDRESS_", HOT_WALLETS[service]),
        RELATED_ADDRESS = HOT_WALLETS[service], 
        HEADER = HEADER,
        PARAMS= PARAMS, 
        file_name=f"{file_name}_trx", 
        min_timestamp=min_ts, 
        max_timestamp=max_ts,
        num_workers=4
    )
    
    global_transfers.clear()  # Clear before next scrape
    PARAMS['contract_address'] = CONTRACT_ADDRESS
    # Run with 4 threads for example (adjust num_workers based on your API tier capacity)
    scrape_multithreaded(
        URL=URL_TRC20.replace("_RELATED_ADDRESS_", HOT_WALLETS[service]),
        RELATED_ADDRESS = HOT_WALLETS[service], 
        HEADER = HEADER,  
        PARAMS= PARAMS,
        file_name=f"{file_name}_trc20", 
        min_timestamp=min_ts, 
        max_timestamp=max_ts,
        num_workers=4
    )
    

        
    
        
    
    
    
    