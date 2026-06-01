"""Path resolution for ground-truth pipeline (off-chain + on-chain)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GROUND_TRUTH_ROOT = Path(__file__).resolve().parents[1]


def ensure_repo_on_path() -> None:
    root = str(REPO_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def offchain_history_path(service: str) -> Path:
    """Resolve off-chain JSONL without importing hyphenated package name."""
    import importlib.util

    registry_file = REPO_ROOT / "src" / "off-chain" / "registry.py"
    spec = importlib.util.spec_from_file_location("offchain_registry", registry_file)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load registry from {registry_file}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.get_history_path(service)


def tron_classified_paths(service: str, year: int) -> tuple[Path, Path]:
    deposits = REPO_ROOT / f"data/classified/deposits_trongrid_{service}_{year}.json"
    withdrawals = REPO_ROOT / f"data/classified/withdrawals_trongrid_{service}_{year}.json"
    return deposits, withdrawals


def priced_paths(service: str, year: int) -> tuple[Path, Path]:
    deposits = REPO_ROOT / f"data/priced/deposit_trongrid_{service}_{year}.json"
    withdrawals = REPO_ROOT / f"data/priced/withdrawal_trongrid_{service}_{year}.json"
    return deposits, withdrawals


def default_outputs(service: str, year: int | None) -> dict[str, Path]:
    suffix = f"{service}_{year}" if year else service
    return {
        "jsonl": GROUND_TRUTH_ROOT / "output" / f"ground_truth_{suffix}.jsonl",
        "json": GROUND_TRUTH_ROOT / "result" / f"ground_truth_{suffix}.json",
        "log": GROUND_TRUTH_ROOT / "log" / f"ground_truth_{suffix}.log",
        "training": GROUND_TRUTH_ROOT / "output" / f"training_pairs_{suffix}.jsonl",
        "model": GROUND_TRUTH_ROOT / "models" / f"xgboost_{suffix}.pkl",
    }
