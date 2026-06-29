from __future__ import annotations

from pathlib import Path

from src.tron_ice.normalization.classifier import run_transaction_normalizer
from src.tron_ice.config.settings import HOT_WALLETS


def normalize_tron_hot_wallet(service: str, year: int) -> dict:
    hot_wallet = HOT_WALLETS.get(service)
    if not hot_wallet:
        raise ValueError(f"Missing hot wallet for service: {service}")
    trx_file = Path("data/raw") / f"trongrid_{service}_{year}_trx.json"
    trc20_file = Path("data/raw") / f"trongrid_{service}_{year}_trc20.json"
    return run_transaction_normalizer(str(trx_file), str(trc20_file), hot_wallet)
