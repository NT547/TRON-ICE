from __future__ import annotations

import json
import logging
from decimal import Decimal
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def ensure_dirs(*paths: Path) -> None:
    for p in paths:
        p.mkdir(parents=True, exist_ok=True)


def load_history_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"History file not found: {path}")

    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_no}: {exc}") from exc
    return out


def load_onchain_generic_json(
    path: Path,
    min_timestamp_ms: int | None = None,
    max_timestamp_ms: int | None = None,
) -> list[dict[str, Any]]:
    """Load generic on-chain JSON array; optional time filter."""
    if not path.exists():
        raise FileNotFoundError(f"On-chain file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Expected list in {path}")
    rows = [_normalize_onchain_record(x, source=str(path)) for x in data]
    return _filter_by_time(rows, min_timestamp_ms, max_timestamp_ms)


def _tron_tx_from_raw(tx: dict[str, Any]) -> dict[str, Any]:
    return {
        "timestamp": int(tx["timestamp"]),
        "token": tx.get("token"),
        "amount": float(tx.get("amount", 0.0)),
        "network": "tron",
        "tx_hash": tx.get("tx_hash") or tx.get("txid"),
        "from": tx.get("from"),
        "to": tx.get("to"),
        "raw": tx,
    }


def load_tron_classified_json(
    path: Path,
    min_timestamp_ms: int | None = None,
    max_timestamp_ms: int | None = None,
) -> list[dict[str, Any]]:
    """
    Load transaction_normalizer classified files (deposits_/withdrawals_*.json).
    Uses ijson streaming when filtering by time (large files).
    """
    if not path.exists():
        raise FileNotFoundError(f"TRON classified file not found: {path}")

    if min_timestamp_ms is None and max_timestamp_ms is None:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError(f"Expected list in {path}")
        return [_tron_tx_from_raw(tx) for tx in data if isinstance(tx, dict)]

    return _load_tron_classified_streaming(path, min_timestamp_ms, max_timestamp_ms)


def _load_tron_classified_streaming(
    path: Path,
    min_ts: int | None,
    max_ts: int | None,
) -> list[dict[str, Any]]:
    try:
        import ijson
    except ImportError:
        logger.warning("ijson not available; loading full JSON then filtering")
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        rows = [_tron_tx_from_raw(tx) for tx in data if isinstance(tx, dict)]
        return _filter_by_time(rows, min_ts, max_ts)

    out: list[dict[str, Any]] = []
    with path.open("rb") as f:
        for tx in ijson.items(f, "item"):
            if not isinstance(tx, dict) or "timestamp" not in tx:
                continue
            ts = int(tx["timestamp"])
            if min_ts is not None and ts < min_ts:
                continue
            if max_ts is not None and ts > max_ts:
                continue
            out.append(_tron_tx_from_raw(tx))
    logger.info(
        "Stream-loaded %s txs from %s (window %s .. %s)",
        len(out),
        path.name,
        min_ts,
        max_ts,
    )
    return out


def _filter_by_time(
    rows: list[dict[str, Any]],
    min_ts: int | None,
    max_ts: int | None,
) -> list[dict[str, Any]]:
    out = []
    for tx in rows:
        ts = int(tx["timestamp"])
        if min_ts is not None and ts < min_ts:
            continue
        if max_ts is not None and ts > max_ts:
            continue
        out.append(tx)
    return out


def history_time_window_ms(
    history: list[dict[str, Any]],
    td_ms: int,
    tw_ms: int,
    extra_pad_ms: int = 86_400_000,
) -> tuple[int | None, int | None]:
    """Compute [min,max] ms window for loading on-chain txs around off-chain history."""
    from src_ground_truth.match import history_time_ms

    times = [history_time_ms(h) for h in history]
    times = [t for t in times if t is not None]
    if not times:
        return None, None
    return min(times) - td_ms - extra_pad_ms, max(times) + td_ms + tw_ms + extra_pad_ms


def calendar_year_window_ms(year: int) -> tuple[int, int]:
    from datetime import datetime, timezone

    min_ts = int(datetime(year, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
    max_ts = int(datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc).timestamp() * 1000)
    return min_ts, max_ts


def write_jsonl_line(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, default=json_default) + "\n")
        f.flush()


def json_default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


def _normalize_onchain_record(x: Any, source: str) -> dict[str, Any]:
    if not isinstance(x, dict):
        raise ValueError(f"Invalid record in {source}: expected dict")

    missing = [k for k in ("timestamp", "token", "amount", "network") if k not in x]
    if missing:
        raise ValueError(f"Missing fields {missing} in {source}")

    tx_hash = x.get("tx_hash") or x.get("txid") or x.get("hash")
    return {
        "timestamp": int(x["timestamp"]),
        "token": str(x["token"]),
        "amount": float(x["amount"]),
        "network": str(x["network"]),
        "tx_hash": str(tx_hash) if tx_hash is not None else None,
        "from": x.get("from"),
        "to": x.get("to"),
        "raw": x,
    }

