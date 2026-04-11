import os
import threading

from dotenv import load_dotenv

load_dotenv()

TRONGRID_API = "https://api.trongrid.io/v1/accounts"

TRONGRID_API_KEY = os.getenv("TRONGRID_API_KEY")

HOT_WALLETS = {
    "fixedfloat": os.getenv("fixedfloat_hot_wallet"),
    "changenow": os.getenv("changenow_hot_wallet"),
    "sideshift": os.getenv("sideshift_hot_wallet"),
}

HEADER = {
    "Content-Type": "application/json",
    "TRON-PRO-API-KEY": TRONGRID_API_KEY 
}

CONTRACT_ADDRESS = os.getenv("contract_address")

params = {
    "limit": 200, 
    "order_by": "block_timestamp,asc", 
    "only_confirmed": "true",
}

data_lock = threading.Lock()
stop_event = threading.Event()
print_lock = threading.Lock()
chunk_transfers = []
global_transfers = []

URL_TRC20 = f"{TRONGRID_API}/_RELATED_ADDRESS_/transactions/trc20"
URL_TRX = f"{TRONGRID_API}/_RELATED_ADDRESS_/transactions"


TIME_WINDOW = 600
VALUE_THRESHOLD = 0.15
VALUE_THRESHOLD = 0.01
REQUEST_DELAY = 1
TARGET_TOKENS = ["USDT", "USDC", "TRX"]