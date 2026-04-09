import bisect
import json
import logging
import os
import requests
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from src.utils.configs import COINGECKO_API_KEY

COINGECKO_API = "https://api.coingecko.com/api/v3"
BINANCE_API = "https://api.binance.com/api/v3"
TOKEN_CG_IDS = {"TRX": "tron", "USDT": "tether", "USDC": "usd-coin"}
BINANCE_SYMBOLS = {"TRX": "TRXUSDT"}
STABLE_TOKENS = {"USDT", "USDC"}
HISTORICAL_PRICE_CACHE: Dict[tuple, Dict[int, float]] = {}
PRICE_LOOKUP_CACHE: Dict[tuple, tuple] = {}


def ensure_cache_dir(cache_dir: str) -> None:
    os.makedirs(cache_dir, exist_ok=True)


def load_price_cache_file(cache_file: str) -> Dict[int, float]:
    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        # JSON keys are stored as strings, convert back to int timestamps
        return {int(ts): float(price) for ts, price in data.items()}
    return {}


def save_price_cache_file(cache_file: str, prices: Dict[int, float]) -> None:
    ensure_cache_dir(os.path.dirname(cache_file) or ".")
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(prices, f, indent=2)


def fetch_coingecko_price_history(
    token: str, year: int, api_key: Optional[str] = None
) -> Dict[int, float]:
    if api_key is None:
        api_key = COINGECKO_API_KEY
    coin_id = TOKEN_CG_IDS.get(token, token.lower().replace(".", "-").replace("_", "-"))
    start_date = datetime(year, 1, 1)
    end_date = datetime(year, 12, 31)
    prices: Dict[int, float] = {}
    current = start_date

    def next_month_start(dt: datetime) -> datetime:
        year = dt.year + (dt.month // 12)
        month = dt.month % 12 + 1
        return datetime(year, month, 1)

    while current <= end_date:
        next_month = next_month_start(current)
        to_date = min(next_month - timedelta(seconds=1), end_date)
        from_ts = int(current.timestamp())
        to_ts = int(to_date.timestamp())

        url = f"{COINGECKO_API}/coins/{coin_id}/market_chart/range"
        params = {"vs_currency": "usd", "from": from_ts, "to": to_ts}
        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; TRON-ICE/1.0)",
        }
        if api_key:
            headers["x-cg-demo-api-key"] = api_key

        for attempt in range(3):
            response = requests.get(url, params=params, headers=headers, timeout=30)
            if response.status_code == 429:
                logging.warning(
                    f"Rate limited by CoinGecko for {token} ({coin_id}) {current.date()} - retrying after backoff"
                )
                time.sleep(5 * (attempt + 1))
                continue
            if response.status_code == 401:
                logging.warning(
                    f"Unauthorized access for CoinGecko token {token} ({coin_id}) on range endpoint"
                )
                return {}
            if response.status_code == 404:
                logging.warning(
                    f"CoinGecko token not found for {token} ({coin_id}); falling back to other sources"
                )
                return {}
            if response.status_code != 200:
                logging.warning(
                    f"Unexpected CoinGecko response {response.status_code} for {token} ({coin_id})"
                )
                return {}
            break

        data = response.json()
        for ts, price in data.get("prices", []):
            prices[int(ts / 1000)] = price

        current = next_month
        time.sleep(1)

    return prices


def fetch_binance_price_history(token: str, year: int) -> Dict[int, float]:
    symbol = BINANCE_SYMBOLS.get(token)
    if not symbol:
        return {}

    start_datetime = datetime(year, 1, 1)
    end_datetime = datetime(year, 12, 31)
    prices: Dict[int, float] = {}
    interval = "1h"
    interval_seconds = 3600
    current = start_datetime

    while current <= end_datetime:
        end_window = current + timedelta(hours=1000) - timedelta(seconds=1)
        if end_window > end_datetime:
            end_window = end_datetime

        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": int(current.timestamp() * 1000),
            "endTime": int(end_window.timestamp() * 1000),
            "limit": 1000,
        }
        response = requests.get(f"{BINANCE_API}/klines", params=params, timeout=30)
        if response.status_code != 200:
            logging.warning(
                f"Binance fallback failed for {token}: status {response.status_code}"
            )
            return {}

        data = response.json()
        if not data:
            break

        for kline in data:
            ts = int(kline[0] / 1000)
            close_price = float(kline[4])
            prices[ts] = close_price

        current = datetime.fromtimestamp(int(data[-1][0] / 1000)) + timedelta(
            seconds=interval_seconds
        )
        time.sleep(0.2)

    return prices


def generate_stable_price_history(year: int) -> Dict[int, float]:
    prices: Dict[int, float] = {}
    current = datetime(year, 1, 1)
    end_date = datetime(year, 12, 31)
    while current <= end_date:
        prices[int(current.timestamp())] = 1.0
        current += timedelta(days=1)
    return prices


def get_historical_prices(
    token: str, year: int, cache_dir: str = "cache", api_key: Optional[str] = None
) -> Dict[int, float]:
    if api_key is None:
        api_key = COINGECKO_API_KEY
    key = (token, year)
    if key in HISTORICAL_PRICE_CACHE:
        return HISTORICAL_PRICE_CACHE[key]

    ensure_cache_dir(cache_dir)
    cache_file = os.path.join(cache_dir, f"price_history_{token.lower()}_{year}.json")
    prices = load_price_cache_file(cache_file)
    if prices:
        logging.info(f"Loaded cached price history for {token} {year}")
        HISTORICAL_PRICE_CACHE[key] = prices
        return prices

    logging.info(f"Fetching historical price history for {token} in {year}")
    if token in STABLE_TOKENS:
        prices = generate_stable_price_history(year)
    else:
        prices = fetch_coingecko_price_history(token, year, api_key)
        if not prices:
            logging.info(f"Falling back to Binance price history for {token} {year}")
            prices = fetch_binance_price_history(token, year)
        if not prices and token in STABLE_TOKENS:
            prices = generate_stable_price_history(year)

    if not prices:
        logging.warning(f"No price history found for {token} in {year}")
        return {}

    save_price_cache_file(cache_file, prices)
    HISTORICAL_PRICE_CACHE[key] = prices
    logging.info(f"Saved price history cache for {token} {year}: {len(prices)} points")
    return prices


def get_sorted_price_points(
    token: str,
    year: int,
    cache_dir: str = "cache",
    api_key: Optional[str] = None,
) -> tuple:
    key = (token, year)
    if key in PRICE_LOOKUP_CACHE:
        return PRICE_LOOKUP_CACHE[key]

    prices = get_historical_prices(token, year, cache_dir, api_key)
    if not prices:
        PRICE_LOOKUP_CACHE[key] = ([], {})
        return [], {}

    sorted_timestamps = sorted(prices.keys())
    PRICE_LOOKUP_CACHE[key] = (sorted_timestamps, prices)
    return sorted_timestamps, prices


def get_price_at_timestamp(
    token: str,
    timestamp: int,
    year: int,
    cache_dir: str = "cache",
    bucket_minutes: int = 5,
    api_key: Optional[str] = None,
) -> float:
    """
    Get the price at a specific timestamp, rounded to nearest bucket.
    """
    sorted_timestamps, prices = get_sorted_price_points(token, year, cache_dir, api_key)
    if not sorted_timestamps:
        # Không có giá lịch sử hợp lệ
        return None

    bucket_seconds = bucket_minutes * 60
    rounded_ts = (timestamp // bucket_seconds) * bucket_seconds
    idx = bisect.bisect_left(sorted_timestamps, rounded_ts)

    candidates = []
    if idx < len(sorted_timestamps):
        candidates.append(sorted_timestamps[idx])
    if idx > 0:
        candidates.append(sorted_timestamps[idx - 1])

    if not candidates:
        return None

    closest_ts = min(candidates, key=lambda ts: abs(ts - rounded_ts))
    price = prices.get(closest_ts)
    if price is None or price == 0.0:
        # Không có giá hợp lệ
        return None
    return price


def calculate_usd_value(
    tx: Dict[str, Any],
    year: int,
    cache_dir: str = "cache",
    api_key: Optional[str] = None,
    bucket_minutes: int = 5,
) -> float:
    """
    Calculate USD value for a transaction using historical price cache.
    """
    token = tx["token"]
    amount = tx["amount"]
    logging.debug(
        f"Calculating USD value for tx {tx.get('txid', '<unknown>')}: token={token}, amount={amount}"
    )
    timestamp = tx["timestamp"] // 1000
    actual_year = datetime.fromtimestamp(timestamp).year
    if api_key is None:
        api_key = COINGECKO_API_KEY
    price = get_price_at_timestamp(
        token,
        timestamp,
        actual_year,
        cache_dir,
        bucket_minutes=bucket_minutes,
        api_key=api_key,
    )
    if price is None:
        logging.debug(
            f"No valid price for tx {tx.get('txid', '<unknown>')}: token={token}, timestamp={timestamp}"
        )
        return None
    value = amount * price
    logging.debug(
        f"USD value for tx {tx.get('txid', '<unknown>')}: price={price}, value={value}"
    )
    return value
