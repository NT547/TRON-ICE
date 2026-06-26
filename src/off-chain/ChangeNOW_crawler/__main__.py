"""Run: python src/off-chain/ChangeNOW_crawler/__main__.py [--output PATH] [--interval SEC]"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent
if str(_PKG_DIR) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR))

from client import ChangeNowApiError, ChangeNowClient
from config import DEFAULT_OUTPUT_FILE, POLL_INTERVAL_SEC
from crawler import run


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Continuously crawl ChangeNOW partner transactions (off-chain ICE metadata)."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify API key (currencies + list permissions) and exit",
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
    if args.check:
        report = ChangeNowClient().check_connectivity()
        print("ChangeNOW API check:")
        for k, v in report.items():
            print(f"  {k}: {v}")
        if not report.get("public_key_ok"):
            raise SystemExit(1)
        if not report.get("list_transactions_ok"):
            msg = report.get("list_message") or report.get("list_error") or "unknown"
            print(f"\nList endpoint not available: {msg}")
            print("Off-chain crawler cannot run until ChangeNOW enables transaction listing for your key.")
            raise SystemExit(1)
        print("\nOK — list endpoint accessible.")
        return
    try:
        run(output_file=args.output, poll_interval_sec=args.interval)
    except ChangeNowApiError as exc:
        print(f"ChangeNOW API error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
