import argparse
import copy
import json
import os
import sys
from datetime import date, datetime, time as dt_time
from pathlib import Path

# Allow: python src/data_collection/scraper_trongrid.py (from repo root)
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.tron_ice.config.settings import HEADER, HOT_WALLETS, CONTRACT_ADDRESS, URL_TRC20, URL_TRX, params, global_transfers
from src.tron_ice.collection.scraper_multithreaded import scrape_multithreaded


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def collect_trongrid_year(
    service: str,
    year: int,
    file_name: str | None = None,
    workers: int = 4,
    start_date: str | None = None,
    end_date: str | None = None,
):
    hot_wallet = HOT_WALLETS.get(service)
    if not hot_wallet:
        raise SystemExit(
            f"Missing hot wallet for service '{service}'. "
            f"Set {service}_hot_wallet in {_REPO_ROOT / '.env'} "
            f"(e.g. sideshift_hot_wallet=T...)."
        )
    if not CONTRACT_ADDRESS:
        raise SystemExit(
            f"Missing contract_address in {_REPO_ROOT / '.env'} (USDT TRC20 contract)."
        )
    if not HEADER.get("TRON-PRO-API-KEY"):
        raise SystemExit(
            f"Missing TRONGRID_API_KEY in {_REPO_ROOT / '.env'}."
        )

    if file_name is None:
        file_name = f"trongrid_{service}_{year}"
    else:
        file_name = f"{file_name}_{service}_{year}"

    if start_date:
        min_dt = datetime.combine(_parse_date(start_date), dt_time.min)
    else:
        min_dt = datetime(year, 1, 1)
    if end_date:
        max_dt = datetime.combine(_parse_date(end_date), dt_time.max)
    else:
        max_dt = datetime(year, 12, 31, 23, 59, 59)
    min_ts = min_dt.timestamp() * 1000
    max_ts = max_dt.timestamp() * 1000
    PARAMS = copy.deepcopy(params)

    scrape_multithreaded(
        URL=URL_TRX.replace("_RELATED_ADDRESS_", hot_wallet),
        RELATED_ADDRESS=hot_wallet,
        HEADER=HEADER,
        PARAMS=PARAMS,
        file_name=f"{file_name}_trx",
        min_timestamp=min_ts,
        max_timestamp=max_ts,
        num_workers=workers,
    )

    global_transfers.clear()  # Clear before next scrape
    PARAMS["contract_address"] = CONTRACT_ADDRESS
    # Run with 4 threads for example (adjust num_workers based on your API tier capacity)
    scrape_multithreaded(
        URL=URL_TRC20.replace("_RELATED_ADDRESS_", hot_wallet),
        RELATED_ADDRESS=hot_wallet,
        HEADER=HEADER,
        PARAMS=PARAMS,
        file_name=f"{file_name}_trc20",
        min_timestamp=min_ts,
        max_timestamp=max_ts,
        num_workers=workers,
    )


def scaping_trongrid(service: str | None = None, year: int | None = None, file_name: str | None = None):
    if service is not None and year is not None:
        return collect_trongrid_year(service=service, year=year, file_name=file_name)

    parser = argparse.ArgumentParser(description="Run Trongrid scraper")
    parser.add_argument(
        "--service",
        type=str,
        required=True,
        choices=["changenow", "fixedfloat", "sideshift"],
        help="Service name (changenow, fixedfloat, sideshift)",
    )
    parser.add_argument(
        "--year",
        type=int,
        required=True,
        choices=range(2020, 2027),
        help="Year to scrape (e.g., 2025)",
    )
    parser.add_argument(
        "--file_name",
        type=str,
        required=False,
        help="Name of the output file (without extension)",
    )
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    args = parser.parse_args()
    return collect_trongrid_year(
        service=args.service,
        year=args.year,
        file_name=args.file_name,
        start_date=args.start_date,
        end_date=args.end_date,
    )


if __name__ == "__main__":
    scaping_trongrid()
