import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(REPO_ROOT / ".env")

OFF_CHAIN_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = OFF_CHAIN_DIR / "output"
LOG_DIR = OUTPUT_DIR / "logs"

DEFAULT_OUTPUT_FILE = OUTPUT_DIR / "changenow_recent_requests.jsonl"
DEFAULT_LOG_FILE = LOG_DIR / "changenow_crawler.log"
STATE_FILE = OUTPUT_DIR / "changenow_crawler_state.json"

CHANGENOW_API_KEY = os.getenv("CHANGENOW_API_KEY", "").strip()

# Partner list (standard flow) — public key; ChangeNOW may require private key (see client errors)
TRANSACTIONS_V1_URL = "https://api.changenow.io/v1/transactions/{api_key}"
# Used by --check only (public key smoke test)
CURRENCIES_V2_URL = "https://api.changenow.io/v2/exchange/currencies"

POLL_INTERVAL_SEC = 30
REQUEST_LIMIT = 100
REQUEST_TIMEOUT_SEC = 30

MAX_RETRIES = 5
RETRY_BASE_DELAY_SEC = 5
RETRY_MAX_DELAY_SEC = 120
RATE_LIMIT_DEFAULT_SLEEP_SEC = 60

# Only persist finished swaps (completed)
DEFAULT_STATUS_FILTER = "finished"
