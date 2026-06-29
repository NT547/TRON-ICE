from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, datetime, time as dt_time, timezone
from pathlib import Path
from typing import Any

import requests

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.tron_ice.config.multichain import service_hot_wallets


DEFAULT_RPC_URL = "https://api.mainnet-beta.solana.com"
BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
BASE58_INDEX = {ch: idx for idx, ch in enumerate(BASE58_ALPHABET)}


class SolanaRpcError(RuntimeError):
    def __init__(self, method: str, error: Any) -> None:
        self.method = method
        self.error = error
        super().__init__(f"Solana RPC error in {method}: {error}")


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _date_bounds(start_date: str, end_date: str) -> tuple[int, int]:
    start = datetime.combine(_parse_date(start_date), dt_time.min, tzinfo=timezone.utc)
    end = datetime.combine(_parse_date(end_date), dt_time.max, tzinfo=timezone.utc)
    return int(start.timestamp()), int(end.timestamp())


def _mask(value: str) -> str:
    if len(value) <= 12:
        return value
    return f"{value[:6]}...{value[-6:]}"


def _base58_decode(value: str) -> bytes:
    n = 0
    for ch in value:
        if ch not in BASE58_INDEX:
            raise ValueError(f"invalid base58 character {ch!r}")
        n = n * 58 + BASE58_INDEX[ch]

    raw = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    pad = 0
    for ch in value:
        if ch == "1":
            pad += 1
        else:
            break
    return b"\x00" * pad + raw


def _validate_solana_address(address: str) -> None:
    try:
        decoded = _base58_decode(address)
    except ValueError as exc:
        raise SystemExit(
            f"Invalid Solana hot wallet in SIDESHIFT_HOT_WALLETS_SOLANA: {_mask(address)} ({exc})"
        ) from exc
    if len(decoded) != 32:
        raise SystemExit(
            "Invalid Solana hot wallet in SIDESHIFT_HOT_WALLETS_SOLANA: "
            f"{_mask(address)} decodes to {len(decoded)} bytes, expected 32"
        )


def _rpc(rpc_url: str, method: str, params: list[Any], *, delay: float) -> Any:
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    for attempt in range(5):
        resp = requests.post(rpc_url, json=payload, timeout=45)
        if resp.status_code == 429:
            time.sleep(delay * (attempt + 2))
            continue
        resp.raise_for_status()
        data = resp.json()
        if "error" not in data:
            return data.get("result")
        if attempt == 4:
            raise SolanaRpcError(method, data["error"])
        time.sleep(delay * (attempt + 1))
    return None


def fetch_signatures(
    rpc_url: str,
    address: str,
    *,
    start_ts: int,
    end_ts: int,
    delay: float,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    before: str | None = None
    while True:
        opts: dict[str, Any] = {"limit": limit}
        if before:
            opts["before"] = before
        batch = _rpc(rpc_url, "getSignaturesForAddress", [address, opts], delay=delay) or []
        if not batch:
            break

        stop = False
        for item in batch:
            block_time = item.get("blockTime")
            if block_time is None:
                continue
            if block_time < start_ts:
                stop = True
                continue
            if block_time <= end_ts:
                rows.append(item)
        before = batch[-1].get("signature")
        if stop or not before:
            break
        time.sleep(delay)
    return rows


def fetch_transaction(
    rpc_url: str,
    signature: str,
    *,
    delay: float,
) -> dict[str, Any] | None:
    params = [
        signature,
        {
            "encoding": "jsonParsed",
            "maxSupportedTransactionVersion": 0,
            "commitment": "confirmed",
        },
    ]
    try:
        return _rpc(rpc_url, "getTransaction", params, delay=delay)
    except SolanaRpcError as exc:
        error = exc.error if isinstance(exc.error, dict) else {}
        if error.get("code") != -32602:
            raise
        return _rpc(
            rpc_url,
            "getTransaction",
            [signature, {"encoding": "jsonParsed", "commitment": "confirmed"}],
            delay=delay,
        )


def collect_solana_chain(
    service: str,
    year: int,
    *,
    start_date: str,
    end_date: str,
    rpc_url: str | None = None,
    delay: float = 0.2,
) -> dict[str, Any]:
    wallets = service_hot_wallets(service, "solana")
    if not wallets:
        raise SystemExit(f"Missing {service.upper()}_HOT_WALLETS_SOLANA in .env")
    for wallet in wallets:
        _validate_solana_address(wallet)

    rpc = rpc_url or os.getenv("SOLANA_RPC_URL") or DEFAULT_RPC_URL
    start_ts, end_ts = _date_bounds(start_date, end_date)
    out_dir = REPO_ROOT / "data" / "raw" / "multichain" / service / str(year) / "solana"
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "service": service,
        "chain": "solana",
        "year": year,
        "start_date": start_date,
        "end_date": end_date,
        "wallets": wallets,
        "signatures": 0,
        "transactions": 0,
    }
    for wallet in wallets:
        signatures = fetch_signatures(
            rpc,
            wallet,
            start_ts=start_ts,
            end_ts=end_ts,
            delay=delay,
        )
        txs = []
        for item in signatures:
            sig = item.get("signature")
            if not sig:
                continue
            tx = fetch_transaction(rpc, sig, delay=delay)
            if tx:
                txs.append({"signature_info": item, "transaction": tx})
            time.sleep(delay)

        (out_dir / f"{wallet}_transactions.json").write_text(
            json.dumps(txs, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        summary["signatures"] += len(signatures)
        summary["transactions"] += len(txs)
        print(f"solana:{wallet} signatures={len(signatures)} transactions={len(txs)}")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect Solana hot-wallet transactions")
    parser.add_argument("--service", required=True, choices=["sideshift", "fixedfloat", "changenow"])
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--start-date", default="2026-05-22")
    parser.add_argument("--end-date", default="2026-06-28")
    parser.add_argument("--rpc-url", default=None)
    parser.add_argument("--delay", type=float, default=0.2)
    args = parser.parse_args()
    print(
        json.dumps(
            collect_solana_chain(
                args.service,
                args.year,
                start_date=args.start_date,
                end_date=args.end_date,
                rpc_url=args.rpc_url,
                delay=args.delay,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
