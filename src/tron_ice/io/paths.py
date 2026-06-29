from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"
ARTIFACTS_DIR = REPO_ROOT / "artifacts"
LEGACY_GROUND_TRUTH_DIR = REPO_ROOT / "ground-truth"


def raw_tron_paths(service: str, year: int) -> tuple[Path, Path]:
    prefix = DATA_DIR / "raw" / f"trongrid_{service}_{year}"
    return prefix.with_name(prefix.name + "_trx.json"), prefix.with_name(prefix.name + "_trc20.json")


def classified_tron_paths(service: str, year: int) -> tuple[Path, Path]:
    return (
        DATA_DIR / "classified" / f"deposits_trongrid_{service}_{year}.json",
        DATA_DIR / "classified" / f"withdrawals_trongrid_{service}_{year}.json",
    )


def priced_tron_paths(service: str, year: int) -> tuple[Path, Path]:
    return (
        DATA_DIR / "priced" / f"deposit_trongrid_{service}_{year}.json",
        DATA_DIR / "priced" / f"withdrawal_trongrid_{service}_{year}.json",
    )


def legacy_ground_truth_outputs(service: str, year: int) -> dict[str, Path]:
    suffix = f"{service}_{year}"
    return {
        "ground_truth_jsonl": LEGACY_GROUND_TRUTH_DIR / "output" / f"ground_truth_{suffix}.jsonl",
        "ground_truth_json": LEGACY_GROUND_TRUTH_DIR / "result" / f"ground_truth_{suffix}.json",
        "training_jsonl": LEGACY_GROUND_TRUTH_DIR / "output" / f"training_pairs_{suffix}.jsonl",
        "model": LEGACY_GROUND_TRUTH_DIR / "models" / f"xgboost_{suffix}.pkl",
        "prediction": LEGACY_GROUND_TRUTH_DIR / "result" / f"xgboost_predict_{suffix}.json",
    }

