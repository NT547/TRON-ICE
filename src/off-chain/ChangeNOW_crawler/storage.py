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


def _pick(d: dict[str, Any], *keys: str) -> Any:
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def transaction_to_record(
    tx: dict[str, Any],
    observed_at: str | None = None,
    service: str = "changenow",
) -> dict[str, Any]:
    """
    Map ChangeNOW API transaction -> unified HistoryRecord (same shape as SideShift crawler).
    Supports v1 and v2 field naming variants.
    """
    ts = (
        _pick(tx, "updatedAt", "updated_at", "createdAt", "created_at")
        or utc_now_iso()
    )
    if isinstance(ts, (int, float)):
        ts = datetime.fromtimestamp(ts / 1000 if ts > 1e12 else ts, tz=timezone.utc).isoformat()

    from_cur = _pick(
        tx,
        "fromCurrency",
        "from_currency",
        "from",
        "currencyFrom",
        "currency_from",
    )
    to_cur = _pick(tx, "toCurrency", "to_currency", "to", "currencyTo", "currency_to")

    amount_in = parse_amount(
        _pick(tx, "amountSend", "amount_send", "expectedAmountFrom", "fromAmount", "payinAmount")
    )
    amount_out = parse_amount(
        _pick(tx, "amountReceive", "amount_receive", "expectedAmountTo", "toAmount", "payoutAmount")
    )

    return {
        "service": service,
        "observed_at": observed_at or utc_now_iso(),
        "shift_timestamp": str(ts),
        "input_coin": str(from_cur or "").upper() if from_cur else "",
        "input_amount": amount_in,
        "output_coin": str(to_cur or "").upper() if to_cur else "",
        "output_amount": amount_out,
        "raw": tx,
    }


class JsonlWriter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = path.open("a", encoding="utf-8")

    def append(self, record: dict[str, Any]) -> None:
        self._file.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._file.flush()

    def close(self) -> None:
        self._file.flush()
        self._file.close()
