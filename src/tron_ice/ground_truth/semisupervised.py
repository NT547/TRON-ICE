from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "ground-truth" / "semisupervised_sideshift.py"


def run_sideshift_semisupervised(
    *,
    year: int = 2026,
    start_date: str = "2026-05-22",
    split_date: str = "2026-06-11",
    end_date: str = "2026-06-28",
    observable_chains: str | None = None,
    iterations: int = 5,
    positive_threshold: float = 0.99,
    negative_threshold: float = 0.01,
    eval_negative_ratio: int | None = None,
    output_prefix: str | None = None,
) -> None:
    cmd = [
        sys.executable,
        str(SCRIPT),
        "--year",
        str(year),
        "--start-date",
        start_date,
        "--split-date",
        split_date,
        "--end-date",
        end_date,
        "--iterations",
        str(iterations),
        "--positive-threshold",
        str(positive_threshold),
        "--negative-threshold",
        str(negative_threshold),
    ]
    if eval_negative_ratio is not None:
        cmd.extend(["--eval-negative-ratio", str(eval_negative_ratio)])
    if observable_chains:
        cmd.extend(["--observable-chains", observable_chains])
    if output_prefix:
        cmd.extend(["--output-prefix", output_prefix])
    subprocess.run(cmd, cwd=str(REPO_ROOT), check=True)
