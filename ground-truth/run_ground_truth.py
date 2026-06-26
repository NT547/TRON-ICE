"""CLI: ICE ground-truth H <-> D <-> W (+ optional TRON n-hop trace)."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

GT_ROOT = Path(__file__).resolve().parent
if str(GT_ROOT) not in sys.path:
    sys.path.insert(0, str(GT_ROOT))

from src_ground_truth.io import ensure_dirs
from src_ground_truth.runner import GroundTruthRunConfig, run_ground_truth


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ICE ground-truth: off-chain user request H <-> on-chain D <-> W (+ TRON trace)."
    )
    parser.add_argument("--service", type=str, required=True, choices=["sideshift", "fixedfloat", "changenow"])
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--history-jsonl", type=Path, default=None)
    parser.add_argument("--tron-deposits-json", type=Path, default=None)
    parser.add_argument("--tron-withdrawals-json", type=Path, default=None)
    parser.add_argument("--deposits-json", type=Path, default=None)
    parser.add_argument("--withdrawals-json", type=Path, default=None)
    parser.add_argument("--TD-sec", type=int, default=1800)
    parser.add_argument("--VD-rel", type=float, default=0.01)
    parser.add_argument("--TW-sec", type=int, default=7200)
    parser.add_argument("--VW-rel", type=float, default=0.02)
    parser.add_argument("--tron-tolerance-mult", type=float, default=2.0)
    parser.add_argument("--trace-depth", type=int, default=0)
    parser.add_argument("--trace-window-min", type=int, default=30)
    parser.add_argument("--no-filter-onchain", action="store_true", help="Load full classified files (slow)")
    parser.add_argument("--out-jsonl", type=Path, default=None)
    parser.add_argument("--out-json", type=Path, default=None)
    parser.add_argument("--log-file", type=Path, default=None)
    parser.add_argument("--export-training", action="store_true")
    parser.add_argument("--min-match-score", type=float, default=0.3)
    parser.add_argument("--negatives-per-positive", type=int, default=3)
    parser.add_argument(
        "--history-network-filter",
        choices=["all", "tron-any", "tron-both"],
        default="all",
        help="Filter off-chain history by raw deposit/settle network before matching",
    )
    args = parser.parse_args()

    from src_ground_truth.paths import default_outputs

    outs = default_outputs(args.service, args.year)
    log_file = args.log_file or outs["log"]

    ensure_dirs(GT_ROOT / "output", GT_ROOT / "log", GT_ROOT / "result", GT_ROOT / "models")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
        force=True,
    )

    cfg = GroundTruthRunConfig(
        service=args.service,
        year=args.year,
        history_jsonl=args.history_jsonl,
        tron_deposits_json=args.tron_deposits_json,
        tron_withdrawals_json=args.tron_withdrawals_json,
        deposits_json=args.deposits_json,
        withdrawals_json=args.withdrawals_json,
        td_sec=args.TD_sec,
        vd_rel=args.VD_rel,
        tw_sec=args.TW_sec,
        vw_rel=args.VW_rel,
        tron_tolerance_mult=args.tron_tolerance_mult,
        trace_depth=args.trace_depth,
        trace_window_min=args.trace_window_min,
        filter_onchain_by_history=not args.no_filter_onchain,
        out_jsonl=args.out_jsonl,
        out_json=args.out_json,
        log_file=log_file,
        export_training=args.export_training,
        min_match_score=args.min_match_score,
        negatives_per_positive=args.negatives_per_positive,
        history_network_filter=args.history_network_filter,
    )
    summary = run_ground_truth(cfg)
    logging.getLogger("ground_truth").info("DONE %s", summary)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUTF8", "1")
    main()
