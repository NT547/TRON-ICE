"""
Shared off-chain history schema for ICE swap user requests.

Used by crawlers (SideShift, future FixedFloat/ChangeNOW) and ground-truth pipeline.
"""

from __future__ import annotations

from typing import Any, TypedDict


class HistoryRecord(TypedDict, total=False):
    """Off-chain swap request H = (Ht, Hcin, Hvin, Hcout, Hvout)."""

    service: str
    observed_at: str
    shift_timestamp: str
    input_coin: str
    input_amount: float | None
    output_coin: str
    output_amount: float | None
    raw: dict[str, Any]


def history_tuple(h: dict[str, Any]) -> tuple[Any, ...]:
    return (
        h.get("shift_timestamp"),
        h.get("input_coin"),
        h.get("input_amount"),
        h.get("output_coin"),
        h.get("output_amount"),
    )


def enrich_history(h: dict[str, Any], service: str) -> dict[str, Any]:
    out = dict(h)
    out.setdefault("service", service)
    return out
