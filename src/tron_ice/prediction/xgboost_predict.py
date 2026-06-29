from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
PREDICT_SCRIPT = REPO_ROOT / "ground-truth" / "predict_xgboost.py"


def predict_xgboost_matches(
    service: str,
    year: int,
    *,
    model: Path | None = None,
    output: Path | None = None,
    threshold: float = 0.5,
) -> None:
    cmd = [
        sys.executable,
        str(PREDICT_SCRIPT),
        "--service",
        service,
        "--year",
        str(year),
        "--threshold",
        str(threshold),
    ]
    if model is not None:
        cmd.extend(["--model", str(model)])
    if output is not None:
        cmd.extend(["--output", str(output)])
    subprocess.run(cmd, cwd=str(REPO_ROOT), check=True)

