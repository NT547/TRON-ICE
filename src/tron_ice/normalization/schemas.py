from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class NormalizedTransaction:
    """Canonical on-chain transaction schema used across pipeline stages."""

    timestamp: int
    chain: str
    token: str
    amount: float
    from_address: str | None
    to_address: str | None
    tx_hash: str | None = None
    usd_value: float | None = None
    raw: dict[str, Any] | None = None

    def to_record(self) -> dict[str, Any]:
        row = asdict(self)
        row["from"] = row.pop("from_address")
        row["to"] = row.pop("to_address")
        return row


@dataclass(frozen=True)
class HistoryRecord:
    """Canonical off-chain swap request H."""

    service: str
    observed_at: str | None
    shift_timestamp: str
    input_coin: str
    input_amount: float | None
    output_coin: str
    output_amount: float | None
    raw: dict[str, Any]


@dataclass(frozen=True)
class CandidatePair:
    deposit: dict[str, Any]
    withdrawal: dict[str, Any]


@dataclass(frozen=True)
class LabeledPair:
    deposit: dict[str, Any]
    withdrawal: dict[str, Any]
    label: int
    label_source: str | None = None
    match_score: float | None = None

