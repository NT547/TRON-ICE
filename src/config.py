import os
from dotenv import load_dotenv

load_dotenv()

TRONGRID_API = "https://api.trongrid.io/v1"
TRONGRID_API_KEY = os.getenv("TRONGRID_API_KEY")
ETHERSCAN_API_KEYS = {
    "ethereum": os.getenv("ETHERSCAN_API_KEY"),
    "bsc": os.getenv("BSCSCAN_API_KEY"),
    "polygon": os.getenv("POLYGONSCAN_API_KEY"),
}

HOT_WALLETS = {
    "fixedfloat": ["TDoXUNZ6PajKuiUkcYg3EDSV9bnqGqsbcf"],
    "changenow": ["TWS1onJnNTg8tJHomceqxBxTsUB1DHh7PV"],
    "sideshift": ["TBEkD71bkL7fNz2HuCeisRbtvwwT2JWaMr"],
}

TIME_WINDOW = 600
VALUE_THRESHOLD = 0.01
REQUEST_DELAY = 1
TARGET_TOKENS = ["USDT", "USDC", "TRX"]
