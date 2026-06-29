from __future__ import annotations

import argparse
import logging

from src.tron_ice.collection.tron import collect_trongrid_year
from src.tron_ice.collection.onchain import collect_onchain_window
from src.tron_ice.ground_truth.runner import build_ground_truth
from src.tron_ice.ground_truth.semisupervised import run_sideshift_semisupervised
from src.tron_ice.normalization.onchain import normalize_onchain
from src.tron_ice.normalization.tron import normalize_tron_hot_wallet
from src.tron_ice.prediction.xgboost_predict import predict_xgboost_matches
from src.tron_ice.training.xgboost_train import train_xgboost_model


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TRON ICE clean research pipeline")
    sub = parser.add_subparsers(dest="stage", required=True)

    stage_parsers = {}
    for name in ("collect", "normalize", "ground-truth", "train", "predict"):
        p = sub.add_parser(name)
        stage_parsers[name] = p
        p.add_argument(
            "--service", required=True, choices=["changenow", "fixedfloat", "sideshift"]
        )
        p.add_argument("--year", type=int, required=True)

    stage_parsers["ground-truth"].add_argument("--trace-depth", type=int, default=0)
    stage_parsers["ground-truth"].add_argument("--export-training", action="store_true")
    stage_parsers["ground-truth"].add_argument(
        "--history-network-filter",
        choices=["all", "tron-any", "tron-both"],
        default="all",
    )
    stage_parsers["predict"].add_argument("--threshold", type=float, default=0.5)

    collect_on = sub.add_parser("collect-onchain")
    stage_parsers["collect-onchain"] = collect_on
    collect_on.add_argument("--service", required=True, choices=["sideshift", "fixedfloat", "changenow"])
    collect_on.add_argument("--year", type=int, default=2026)
    collect_on.add_argument(
        "--chains",
        nargs="+",
        default=["ethereum", "solana", "liquid", "bitcoin", "bsc", "polygon", "tron"],
    )
    collect_on.add_argument("--start-date", default="2026-05-22")
    collect_on.add_argument("--end-date", default="2026-06-28")
    collect_on.add_argument("--workers", type=int, default=4)
    collect_on.add_argument(
        "--legacy-api",
        action="store_true",
        help="Use chain-specific explorer V1 endpoints where configured.",
    )
    collect_on.add_argument(
        "--allow-wide-fallback",
        action="store_true",
        help="Allow broad block-range scan when explorer block timestamp lookup fails. Can be slow.",
    )

    normalize_on = sub.add_parser("normalize-onchain")
    stage_parsers["normalize-onchain"] = normalize_on
    normalize_on.add_argument("--service", required=True, choices=["sideshift", "fixedfloat", "changenow"])
    normalize_on.add_argument("--year", type=int, default=2026)
    normalize_on.add_argument(
        "--chains",
        nargs="+",
        default=["ethereum", "solana", "bsc", "polygon", "tron"],
    )

    semi = sub.add_parser("semi-supervised")
    stage_parsers["semi-supervised"] = semi
    semi.add_argument("--service", required=True, choices=["sideshift"])
    semi.add_argument("--year", type=int, default=2026)
    semi.add_argument("--start-date", default="2026-05-22")
    semi.add_argument("--split-date", default="2026-06-11")
    semi.add_argument("--end-date", default="2026-06-28")
    semi.add_argument(
        "--observable-chains",
        default=None,
        help="Comma-separated chains with comparable on-chain classified data.",
    )
    semi.add_argument("--iterations", type=int, default=5)
    semi.add_argument("--positive-threshold", type=float, default=0.99)
    semi.add_argument("--negative-threshold", type=float, default=0.01)
    semi.add_argument("--eval-negative-ratio", type=int, default=None)
    semi.add_argument("--output-prefix", default=None)
    return parser


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    args = build_parser().parse_args()

    if args.stage == "collect":
        collect_trongrid_year(args.service, args.year)
    elif args.stage == "normalize":
        normalize_tron_hot_wallet(args.service, args.year)
    elif args.stage == "ground-truth":
        summary = build_ground_truth(
            args.service,
            args.year,
            trace_depth=args.trace_depth,
            export_training=args.export_training,
            history_network_filter=args.history_network_filter,
        )
        logging.info("Ground-truth summary: %s", summary)
    elif args.stage == "train":
        train_xgboost_model(args.service, args.year)
    elif args.stage == "predict":
        predict_xgboost_matches(args.service, args.year, threshold=args.threshold)
    elif args.stage == "collect-onchain":
        collect_onchain_window(
            args.service,
            args.year,
            chains=args.chains,
            start_date=args.start_date,
            end_date=args.end_date,
            workers=args.workers,
            use_legacy_api=args.legacy_api,
            allow_wide_fallback=args.allow_wide_fallback,
        )
    elif args.stage == "normalize-onchain":
        normalize_onchain(args.service, args.year, chains=args.chains)
    elif args.stage == "semi-supervised":
        run_sideshift_semisupervised(
            year=args.year,
            start_date=args.start_date,
            split_date=args.split_date,
            end_date=args.end_date,
            observable_chains=args.observable_chains,
            iterations=args.iterations,
            positive_threshold=args.positive_threshold,
            negative_threshold=args.negative_threshold,
            eval_negative_ratio=args.eval_negative_ratio,
            output_prefix=args.output_prefix,
        )


if __name__ == "__main__":
    main()
