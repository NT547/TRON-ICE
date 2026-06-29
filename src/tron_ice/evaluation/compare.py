from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
EVALUATE_SCRIPT = REPO_ROOT / "ground-truth" / "evaluate_baseline_vs_xgboost.py"


def evaluate_baseline_vs_xgboost(
    service: str,
    year: int,
    *,
    training_jsonl: Path | None = None,
    model: Path | None = None,
) -> None:
    cmd = [sys.executable, str(EVALUATE_SCRIPT), "--service", service, "--year", str(year)]
    if training_jsonl is not None:
        cmd.extend(["--training-jsonl", str(training_jsonl)])
    if model is not None:
        cmd.extend(["--model", str(model)])
    subprocess.run(cmd, cwd=str(REPO_ROOT), check=True)

