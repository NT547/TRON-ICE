"""ICE service registry: default off-chain history paths per provider."""

from __future__ import annotations

from pathlib import Path

OFF_CHAIN_OUTPUT = Path(__file__).resolve().parent / "output"

ICE_SERVICES: dict[str, dict[str, str]] = {
    "sideshift": {
        "history_jsonl": str(OFF_CHAIN_OUTPUT / "sideshift_recent_deposits.jsonl"),
        "display_name": "SideShift.ai",
    },
    # Placeholders for future crawlers:
    "fixedfloat": {
        "history_jsonl": str(OFF_CHAIN_OUTPUT / "fixedfloat_recent_requests.jsonl"),
        "display_name": "FixedFloat",
    },
    "changenow": {
        "history_jsonl": str(OFF_CHAIN_OUTPUT / "changenow_recent_requests.jsonl"),
        "display_name": "ChangeNOW",
    },
}


def get_history_path(service: str) -> Path:
    service = service.lower()
    if service not in ICE_SERVICES:
        raise ValueError(
            f"Unknown ICE service '{service}'. Known: {', '.join(ICE_SERVICES)}"
        )
    return Path(ICE_SERVICES[service]["history_jsonl"])
