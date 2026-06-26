"""Ground-truth output schemas: H <-> D <-> W with optional trace paths."""

from __future__ import annotations

from typing import Any


def onchain_tx_public(tx: dict[str, Any] | None) -> dict[str, Any] | None:
    if tx is None:
        return None
    return {
        "tx_hash": tx.get("tx_hash") or tx.get("txid"),
        "network": tx.get("network", "tron"),
        "token": tx.get("token"),
        "amount": tx.get("amount"),
        "timestamp": tx.get("timestamp"),
        "from": tx.get("from"),
        "to": tx.get("to"),
    }


def format_ground_truth_record(
    *,
    service: str,
    history: dict[str, Any],
    deposit: dict[str, Any] | None,
    settlement: dict[str, Any] | None,
    deposit_path: list[dict[str, Any]] | None,
    settlement_path: list[dict[str, Any]] | None,
    deposit_trace: dict[str, Any] | None,
    settlement_trace: dict[str, Any] | None,
    match_score: float,
) -> dict[str, Any]:
    """Standard JSON record for result/ and training export."""
    full_match = deposit is not None and settlement is not None
    return {
        "service": service,
        "history": history,
        "deposit": onchain_tx_public(deposit),
        "settlement": onchain_tx_public(settlement),
        "deposit_path": [onchain_tx_public(t) for t in (deposit_path or [])],
        "settlement_path": [onchain_tx_public(t) for t in (settlement_path or [])],
        "deposit_trace": onchain_tx_public(deposit_trace),
        "settlement_trace": onchain_tx_public(settlement_trace),
        "match_score": match_score,
        "label": 1 if full_match and match_score > 0 else 0,
    }
