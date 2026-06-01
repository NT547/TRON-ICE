from __future__ import annotations

import json
import logging
import signal
import time
from pathlib import Path
from typing import Any

from client import SideShiftClient
from config import (
    DEFAULT_LOG_FILE,
    DEFAULT_OUTPUT_FILE,
    LOG_DIR,
    POLL_INTERVAL_SEC,
    STATE_FILE,
)
from dedup import DedupStore, key_from_record
from storage import JsonlWriter, shift_to_record, utc_now_iso

logger = logging.getLogger(__name__)


class SideShiftCrawler:
    def __init__(
        self,
        output_file: Path = DEFAULT_OUTPUT_FILE,
        log_file: Path = DEFAULT_LOG_FILE,
        state_file: Path = STATE_FILE,
        poll_interval_sec: float = POLL_INTERVAL_SEC,
    ) -> None:
        self.output_file = output_file
        self.log_file = log_file
        self.state_file = state_file
        self.poll_interval_sec = poll_interval_sec
        self._stop = False
        self.client = SideShiftClient()
        self.dedup = DedupStore()
        self._writer: JsonlWriter | None = None
        self.stats = {
            "polls": 0,
            "fetched": 0,
            "appended": 0,
            "skipped_duplicates": 0,
            "errors": 0,
        }

    def setup_logging(self) -> None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            handlers=[
                logging.FileHandler(self.log_file, encoding="utf-8"),
                logging.StreamHandler(),
            ],
            force=True,
        )

    def _install_signal_handlers(self) -> None:
        def _handle_stop(signum: int, _frame: Any) -> None:
            logger.info("Received signal %s. Stopping after current operation...", signum)
            self._stop = True

        signal.signal(signal.SIGINT, _handle_stop)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, _handle_stop)

    def resume(self) -> int:
        loaded = self.dedup.load_from_jsonl(self.output_file)
        logger.info(
            "Resume: loaded %s dedup keys from %s",
            loaded,
            self.output_file,
        )
        return loaded

    def _save_state(self) -> None:
        payload = {
            "updated_at": utc_now_iso(),
            "output_file": str(self.output_file),
            "dedup_keys": len(self.dedup),
            "stats": self.stats,
        }
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with self.state_file.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def _process_shifts(self, shifts: list[dict[str, Any]]) -> int:
        if self._writer is None:
            raise RuntimeError("Writer not initialized")

        appended = 0
        observed_at = utc_now_iso()

        for shift in shifts:
            if self._stop:
                break

            record = shift_to_record(shift, observed_at=observed_at)
            key = key_from_record(record)

            if self.dedup.contains(key):
                self.stats["skipped_duplicates"] += 1
                continue

            self._writer.append(record)
            self.dedup.add(key)
            appended += 1
            self.stats["appended"] += 1

        return appended

    def poll_once(self) -> int:
        shifts = self.client.fetch_recent_shifts()
        self.stats["polls"] += 1
        self.stats["fetched"] += len(shifts)
        appended = self._process_shifts(shifts)
        self._save_state()
        logger.info(
            "Poll #%s: fetched=%s appended=%s skipped_dup=%s total_keys=%s",
            self.stats["polls"],
            len(shifts),
            appended,
            self.stats["skipped_duplicates"],
            len(self.dedup),
        )
        return appended

    def run(self) -> None:
        self.setup_logging()
        self._install_signal_handlers()
        self.output_file.parent.mkdir(parents=True, exist_ok=True)

        logger.info("Starting SideShift crawler. Output: %s", self.output_file)
        self.resume()

        self._writer = JsonlWriter(self.output_file)
        try:
            while not self._stop:
                try:
                    self.poll_once()
                except Exception:
                    self.stats["errors"] += 1
                    logger.exception("Poll failed; will retry after interval.")

                if self._stop:
                    break

                self._interruptible_sleep(self.poll_interval_sec)
        finally:
            if self._writer is not None:
                self._writer.close()
            self._save_state()
            logger.info("Crawler stopped. Stats: %s", self.stats)

    def _interruptible_sleep(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while not self._stop and time.monotonic() < end:
            time.sleep(min(1.0, end - time.monotonic()))


def run(
    output_file: Path | None = None,
    poll_interval_sec: float = POLL_INTERVAL_SEC,
) -> None:
    crawler = SideShiftCrawler(
        output_file=output_file or DEFAULT_OUTPUT_FILE,
        poll_interval_sec=poll_interval_sec,
    )
    crawler.run()
