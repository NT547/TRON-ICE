from pathlib import Path

OFF_CHAIN_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = OFF_CHAIN_DIR / "output"
LOG_DIR = OUTPUT_DIR / "logs"

DEFAULT_OUTPUT_FILE = OUTPUT_DIR / "sideshift_recent_deposits.jsonl"
DEFAULT_LOG_FILE = LOG_DIR / "sideshift_crawler.log"
STATE_FILE = OUTPUT_DIR / "sideshift_crawler_state.json"

RECENT_SHIFTS_URL = "https://sideshift.ai/api/v2/recent-shifts"

POLL_INTERVAL_SEC = 30
REQUEST_LIMIT = 100
REQUEST_TIMEOUT_SEC = 30

MAX_RETRIES = 5
RETRY_BASE_DELAY_SEC = 5
RETRY_MAX_DELAY_SEC = 120
RATE_LIMIT_DEFAULT_SLEEP_SEC = 60
