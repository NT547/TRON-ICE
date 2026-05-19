import argparse
import json
import logging
import os
import glob
import pandas as pd

from src.data_collection.scraper_trongrid import scaping_trongrid
from src.transaction_classifier.transaction_classifier import run_transaction_classifer
from src.baseline_algorithm.matcher import (
    run_matching_pipeline 

)
from src.baseline_algorithm.price_calculator import price_and_save_transactions
from src.utils.configs import HOT_WALLETS
from src.transaction_normalizer.transaction_normalizer import transaction_normalizer


def main():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

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
            "data_collection",
            "transaction_normalizer",
            "transaction_classifier",
            "baseline_algorithm",
            "xgboost",
        ],
        help="Run full pipeline, baseline algorithm (matching), transaction classifier, data collection, or xgboost pipeline",
    )

    parser.add_argument(
        "--time_window",
        type=int,
        default=180,
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
        help="Custom output file for matched pairs. Defaults to data/matched/matched_pairs_{service}_{year}.csv",
    )

    args = parser.parse_args()

    service = args.service
    year = args.year
    hot_wallet = HOT_WALLETS[service]
    raw_file = f"data/raw/*json"
    trx_file = f"data/processed/trongrid_{service}_{year}_trx*.csv"
    trc20_file = f"data/processed/trongrid_{service}_{year}_trc20*.csv"
    deposits_file_pattern = f"data/classified/deposits_trongrid_{service}_{year}*.csv"
    withdrawals_file_pattern = f"data/classified/withdrawals_trongrid_{service}_{year}*.csv"
    matched_file = (
        args.output_file or f"data/matched/matched_pairs_{service}_{year}.csv"
    )

    os.environ["MATCH_SERVICE"] = service
    os.environ["MATCH_YEAR"] = str(year)

    if args.mode == "full":
        scaping_trongrid(service=service, year=year)
        classified = run_transaction_classifer(trx_file, trc20_file, hot_wallet)
        matches = run_matching_pipeline(
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
        # save_matched_pairs(matches, matched_file)
    elif args.mode == "transaction_normalizer":
        nor = transaction_normalizer(raw_files=raw_file)
        logging.info(
            f"Transaction normalizer completed"
        )
    elif args.mode == "xgboost":
        from src.xgboost.pipeline import run_xgboost_pipeline
        run_xgboost_pipeline(service, year, args)

    elif args.mode == "data_collection":
        scaping_trongrid(service=service, year=year)

    elif args.mode == "transaction_classifier":
        classified = run_transaction_classifer(trx_file, trc20_file, hot_wallet)
        logging.info(
            f"Transaction normalizer completed: {len(classified['deposits'])} deposits, {len(classified['withdrawals'])} withdrawals."
        )

    elif args.mode == "baseline_algorithm":
        os.environ["MATCH_SERVICE"] = service
        os.environ["MATCH_YEAR"] = str(year)

        dep_files = glob.glob(deposits_file_pattern.replace("*", ""))
        wth_files = glob.glob(withdrawals_file_pattern.replace("*", ""))

        if not dep_files or not wth_files:
            raise FileNotFoundError(
                "Baseline algorithm requires precomputed deposit/withdrawal files. "
                "Run --mode transaction_normalizer first to generate them."
            )

        # Thiết lập file log cho pipeline Matcher   
        os.makedirs("results/logs/matcher", exist_ok=True)
        log_file = os.path.join(
            "results/logs/matcher", f"matched_transaction_{service}_{year}.log"
        )
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )
        logging.getLogger().addHandler(file_handler)
        
        # Duyệt qua từng file được phân loại (Xử lý riêng biệt file thường và file _samples)
        for d_file in dep_files:
            w_file = d_file.replace("deposits_", "withdrawals_")
            if not os.path.exists(w_file):
                logging.warning(f"Không tìm thấy file rút tiền tương ứng cho {d_file}")
                continue
                
            # Xác định tên file output matched tương ứng (Tách riêng file mẫu _samples nếu có)
            if "_samples" in d_file.lower():
                base_matched, ext = os.path.splitext(matched_file)
                current_matched_file = f"{base_matched}_samples{ext}"
            else:
                current_matched_file = matched_file
                
            logging.info(f"\n--- ĐANG CHẠY PIPELINE KHỚP CẶP ---\n  Nạp: {d_file}\n  Rút: {w_file}\n  Đầu ra: {current_matched_file}")
            
            # Gọi trực tiếp pipeline mới (Tự động load chunk, định giá USD và lưu file)
            run_matching_pipeline(
                deposits_path=d_file,
                withdrawals_path=w_file,
                output_path=current_matched_file,
                time_window=args.time_window,
                value_threshold=args.value_threshold,
                year=year,
                cache_dir=args.cache_dir,
                api_key=None,
                bucket_minutes=args.bucket_minutes,
            )
            
        logging.getLogger().removeHandler(file_handler)
        file_handler.close()


if __name__ == "__main__":
    main()