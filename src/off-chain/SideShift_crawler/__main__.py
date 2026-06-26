"""Run: python src/off-chain/SideShift_crawler/__main__.py [--output PATH] [--interval SEC]"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent
if str(_PKG_DIR) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR))

from config import DEFAULT_OUTPUT_FILE, POLL_INTERVAL_SEC
from crawler import run


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Continuously crawl SideShift recent completed shifts (deposits metadata)."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_FILE,
        help=f"JSONL output path (default: {DEFAULT_OUTPUT_FILE})",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=POLL_INTERVAL_SEC,
        help=f"Poll interval in seconds (default: {POLL_INTERVAL_SEC})",
    )
    args = parser.parse_args()
    run(output_file=args.output, poll_interval_sec=args.interval)


if __name__ == "__main__":
    main()
