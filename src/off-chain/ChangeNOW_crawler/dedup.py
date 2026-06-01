from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def dedup_key(
    shift_timestamp: str,
    input_amount: Any,
    input_coin: str,
    output_coin: str,
) -> str:
    return "|".join(
        [
            str(shift_timestamp),
            _normalize_amount(input_amount),
            str(input_coin),
            str(output_coin),
        ]
    )


def key_from_record(record: dict[str, Any]) -> str:
    raw = record.get("raw") or {}
    tx_id = raw.get("id") or raw.get("transactionId")
    if tx_id:
        return f"id:{tx_id}"
    return dedup_key(
        record["shift_timestamp"],
        record["input_amount"],
        record["input_coin"],
        record["output_coin"],
    )


def _normalize_amount(value: Any) -> str:
    if value is None:
        return "null"
    return str(value)


class DedupStore:
    def __init__(self) -> None:
        self._keys: set[str] = set()

    def __len__(self) -> int:
        return len(self._keys)

    def contains(self, key: str) -> bool:
        return key in self._keys

    def add(self, key: str) -> None:
        self._keys.add(key)

    def load_from_jsonl(self, path: Path) -> int:
        if not path.exists():
            return 0
        loaded = 0
        with path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    self.add(key_from_record(record))
                    loaded += 1
                except (json.JSONDecodeError, KeyError) as exc:
                    raise ValueError(f"Invalid record at {path}:{line_no}: {exc}") from exc
        return loaded
