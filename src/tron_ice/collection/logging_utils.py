from __future__ import annotations

import os

from src.tron_ice.config.settings import print_lock


def safe_print(message: str, filename: str | None = None) -> None:
    with print_lock:
        print(message)

    log_dir = "results/logs/scaper/"
    os.makedirs(log_dir, exist_ok=True)
    if filename is None:
        filename = "scraper.log"

    with open(os.path.join(log_dir, filename), "a", encoding="utf-8") as f:
        f.write(message + "\n")

