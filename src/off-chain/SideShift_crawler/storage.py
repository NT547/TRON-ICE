from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_amount(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def shift_to_record(
    shift: dict[str, Any],
    observed_at: str | None = None,
    service: str = "sideshift",
) -> dict[str, Any]:
    return {
        "service": service,
        "observed_at": observed_at or utc_now_iso(),
        "shift_timestamp": shift["createdAt"],
        "input_coin": shift["depositCoin"],
        "input_amount": parse_amount(shift.get("depositAmount")),
        "output_coin": shift["settleCoin"],
        "output_amount": parse_amount(shift.get("settleAmount")),
        "raw": shift,
    }


class JsonlWriter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = path.open("a", encoding="utf-8")

    def append(self, record: dict[str, Any]) -> None:
        line = json.dumps(record, ensure_ascii=False)
        self._file.write(line + "\n")
        self._file.flush()

    def close(self) -> None:
        self._file.flush()
        self._file.close()
