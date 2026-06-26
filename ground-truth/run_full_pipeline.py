"""
End-to-end: ground-truth -> training export -> XGBoost .pkl

  python ground-truth/run_full_pipeline.py --service sideshift --year 2025 --trace-depth 2
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path

GT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = GT_ROOT.parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Full ICE ground-truth + XGBoost pipeline")
    parser.add_argument("--service", required=True, choices=["sideshift", "fixedfloat", "changenow"])
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--trace-depth", type=int, default=0)
    parser.add_argument("--skip-train", action="store_true")
    args = parser.parse_args()

    py = sys.executable
    gt_cmd = [
        py,
        str(GT_ROOT / "run_ground_truth.py"),
        "--service",
        args.service,
        "--year",
        str(args.year),
        "--export-training",
    ]
    if args.trace_depth > 0:
        gt_cmd.extend(["--trace-depth", str(args.trace_depth)])

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.info("Step 1/2: ground-truth matching...")
    subprocess.run(gt_cmd, cwd=str(REPO_ROOT), check=True)

    if not args.skip_train:
        logging.info("Step 2/2: train XGBoost...")
        subprocess.run(
            [
                py,
                str(GT_ROOT / "train_xgboost.py"),
                "--service",
                args.service,
                "--year",
                str(args.year),
            ],
            cwd=str(REPO_ROOT),
            check=True,
        )
    logging.info("Pipeline complete. Model: ground-truth/models/xgboost_%s_%s.pkl", args.service, args.year)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUTF8", "1")
    main()
