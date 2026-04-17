import time
import datetime


def ts_to_datetime(ts):
    """Convert timestamp (ms) → readable datetime"""
    return datetime.datetime.fromtimestamp(ts / 1000)


def sleep_safe(seconds):
    """Sleep để tránh rate limit"""
    time.sleep(seconds)


def safe_get(d, keys, default=None):
    """Truy cập dict an toàn"""
    for k in keys:
        d = d.get(k, {})
    return d if d else default


def normalize_trx(value):
    """TRX (Sun → TRX)"""
    return value / 1_000_000


def normalize_token(value, decimals):
    return int(value) / (10 ** int(decimals))


def is_incoming(tx_to, wallet):
    return tx_to.lower() == wallet.lower()


def is_outgoing(tx_from, wallet):
    return tx_from.lower() == wallet.lower()
