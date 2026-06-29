from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
TRAIN_SCRIPT = REPO_ROOT / "ground-truth" / "train_xgboost.py"


def train_xgboost_model(
    service: str,
    year: int,
    *,
    training_jsonl: Path | None = None,
    model_out: Path | None = None,
) -> None:
    cmd = [sys.executable, str(TRAIN_SCRIPT), "--service", service, "--year", str(year)]
    if training_jsonl is not None:
        cmd.extend(["--training-jsonl", str(training_jsonl)])
    if model_out is not None:
        cmd.extend(["--model-out", str(model_out)])
    subprocess.run(cmd, cwd=str(REPO_ROOT), check=True)

