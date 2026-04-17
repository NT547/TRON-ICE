import argparse
import json
import logging
import os
from src.data_collection.scraper_trongrid import scaping_trongrid
from src.transaction_normalizer.transaction_classifier import (
    run_transaction_normalizer,
    save_classified_transactions,
)
from src.baseline_algorithm.matcher import (
    run_matching as run_new_matching,
    save_matched_pairs,
)
from src.baseline_algorithm.price_calculator import price_and_save_transactions
from src.utils.configs import HOT_WALLETS


def main():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    # python main.py --service fixedfloat --year 2025 #get data for fixedfloat in 2025

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
        choices=range(2020, 2026),
        help="Year to scrape (e.g., 2025)",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="full",
        choices=[
            "full",
            "baseline_algorithm",
            "transaction_normalizer",
            "data_collection",
            "xgboost",
        ],
        help="Run full pipeline, baseline algorithm (matching), transaction normalizer, data collection, or xgboost pipeline",
    )

    parser.add_argument(
        "--time_window",
        type=int,
        default=300,
        help="Time window in seconds for matching (default: 300)",
    )
    parser.add_argument(
        "--value_threshold",
        type=float,
        default=0.05,
        help="Value threshold for matching (default: 0.05)",
    )
    parser.add_argument(
        "--bucket_minutes",
        type=int,
        default=5,
        choices=[1, 2, 3, 4, 5],
        help="Bucket size in minutes for mapping transaction timestamps to prices (default: 5)",
    )
    parser.add_argument(
        "--cache_dir",
        type=str,
        default="cache",
        help="Directory for price cache (default: cache)",
    )
    parser.add_argument(
        "--num_processes",
        type=int,
        default=1,
        help="Number of processes for parallel matching (default: 1)",
    )
    parser.add_argument(
        "--output_file",
        type=str,
        default=None,
        help="Custom output file for matched pairs. Defaults to results/matched/matched_pairs_{service}_{year}.json",
    )

    args = parser.parse_args()

    service = args.service
    year = args.year
    hot_wallet = HOT_WALLETS[service]

    trx_file = f"data/raw/trongrid_{service}_{year}_trx.json"
    trc20_file = f"data/raw/trongrid_{service}_{year}_trc20.json"
    deposits_file = f"data/classified/deposits_trongrid_{service}_{year}.json"
    withdrawals_file = f"data/classified/withdrawals_trongrid_{service}_{year}.json"
    matched_file = (
        args.output_file or f"data/matched/matched_pairs_{service}_{year}.json"
    )

    os.environ["MATCH_SERVICE"] = service
    os.environ["MATCH_YEAR"] = str(year)
    if args.mode == "full":
        scaping_trongrid(service=service, year=year)
        classified = run_transaction_normalizer(trx_file, trc20_file, hot_wallet)
        # Không lưu lại file phân loại ở đây nữa, đã lưu trong run_transaction_normalizer
        matches = run_new_matching(
            classified["deposits"],
            classified["withdrawals"],
            args.time_window,
            args.value_threshold,
            year,
            args.cache_dir,
            args.num_processes,
            None,
            args.bucket_minutes,
        )
    elif args.mode == "xgboost":
        from src.xgboost.pipeline import run_xgboost_pipeline

        run_xgboost_pipeline(service, year, args)
    elif args.mode == "data_collection":
        scaping_trongrid(service=service, year=year)

    elif args.mode == "transaction_normalizer":
        classified = run_transaction_normalizer(trx_file, trc20_file, hot_wallet)
        logging.info(
            f"Transaction normalizer completed: {len(classified['deposits'])} deposits, {len(classified['withdrawals'])} withdrawals."
        )

    elif args.mode == "baseline_algorithm":
        os.environ["MATCH_SERVICE"] = service
        os.environ["MATCH_YEAR"] = str(year)
        if not os.path.exists(deposits_file) or not os.path.exists(withdrawals_file):
            raise FileNotFoundError(
                "Baseline algorithm requires precomputed deposit/withdrawal files. "
                "Run --mode transaction_normalizer first to generate them."
            )

        with open(deposits_file, "r", encoding="utf-8") as f:
            deposits = json.load(f)
        with open(withdrawals_file, "r", encoding="utf-8") as f:
            withdrawals = json.load(f)
        classified = {"deposits": deposits, "withdrawals": withdrawals}
        # Lưu file priced cho deposits và withdrawals
        price_and_save_transactions(
            deposits_file,
            service,
            year,
            cache_dir=args.cache_dir,
            api_key=None,
            bucket_minutes=args.bucket_minutes,
            output_dir="data/priced",
        )
        price_and_save_transactions(
            withdrawals_file,
            service,
            year,
            cache_dir=args.cache_dir,
            api_key=None,
            bucket_minutes=args.bucket_minutes,
            output_dir="data/priced",
        )

        # Thiết lập file log cho pipeline
        os.makedirs("results/logs/matcher", exist_ok=True)
        log_file = os.path.join(
            "results/logs/matcher", f"matched_transaction_{service}_{year}.log"
        )
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )
        logging.getLogger().addHandler(file_handler)
        matches = run_new_matching(
            classified["deposits"],
            classified["withdrawals"],
            args.time_window,
            args.value_threshold,
            year,
            args.cache_dir,
            args.num_processes,
            None,
            args.bucket_minutes,
        )
        save_matched_pairs(matches, matched_file)
        logging.getLogger().removeHandler(file_handler)
        file_handler.close()


if __name__ == "__main__":
    main()
