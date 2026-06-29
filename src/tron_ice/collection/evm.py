from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, time as dt_time, timezone
from pathlib import Path
from typing import Any

import requests

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.tron_ice.config.multichain import EVM_CHAINS, service_hot_wallets


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _time_bounds(year: int, start_date: str | None, end_date: str | None) -> tuple[int, int]:
    if start_date:
        start_dt = datetime.combine(_parse_date(start_date), dt_time.min, tzinfo=timezone.utc)
    else:
        start_dt = datetime(year, 1, 1, tzinfo=timezone.utc)
    if end_date:
        end_dt = datetime.combine(_parse_date(end_date), dt_time.max, tzinfo=timezone.utc)
    else:
        end_dt = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    start = int(start_dt.timestamp())
    end = int(end_dt.timestamp())
    now = int(datetime.now(timezone.utc).timestamp())
    return start, min(end, now)


def _request_with_retry(url: str, params: dict[str, Any], *, delay: float) -> list[dict[str, Any]]:
    for attempt in range(5):
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        result = data.get("result")
        if isinstance(result, list):
            return result
        message = str(data.get("message") or "")
        if "No transactions found" in message:
            return []
        if attempt == 4:
            raise RuntimeError(f"Explorer API error: {data}")
        time.sleep(delay * (attempt + 1))
    return []


def _request_scalar_with_retry(url: str, params: dict[str, Any], *, delay: float) -> int:
    for attempt in range(5):
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        result = data.get("result")
        if isinstance(result, int) or (isinstance(result, str) and result.isdigit()):
            return int(result)
        if attempt == 4:
            raise RuntimeError(f"Explorer API error: {data}")
        time.sleep(delay * (attempt + 1))
    return 0


def _request_block_by_timestamp_or_none(
    chain_id: int,
    api_key: str,
    timestamp: int,
    closest: str,
    *,
    api_url: str,
    use_legacy_api: bool,
    delay: float,
    allow_wide_fallback: bool,
) -> int | None:
    try:
        return block_by_timestamp(
            chain_id,
            api_key,
            timestamp,
            closest,
            api_url=api_url,
            use_legacy_api=use_legacy_api,
            delay=delay,
        )
    except Exception as exc:
        if not allow_wide_fallback:
            print(f"block_by_timestamp unavailable for chainid={chain_id}: {exc}")
            raise
        print(
            "block_by_timestamp unavailable for "
            f"chainid={chain_id}; using broad block fallback: {exc}"
        )
        return None


def _api_url(cfg: Any, use_legacy_api: bool) -> str:
    if use_legacy_api and cfg.legacy_api_url:
        return cfg.legacy_api_url
    return "https://api.etherscan.io/v2/api"


def _with_chain_id(params: dict[str, Any], chain_id: int, use_legacy_api: bool) -> dict[str, Any]:
    if not use_legacy_api:
        return {"chainid": chain_id, **params}
    return params


def block_by_timestamp(
    chain_id: int,
    api_key: str,
    timestamp: int,
    closest: str,
    *,
    api_url: str,
    use_legacy_api: bool,
    delay: float,
) -> int:
    return _request_scalar_with_retry(
        api_url,
        _with_chain_id(
            {
            "module": "block",
            "action": "getblocknobytime",
            "timestamp": timestamp,
            "closest": closest,
            "apikey": api_key,
            },
            chain_id,
            use_legacy_api,
        ),
        delay=delay,
    )


def _fetch_range(
    *,
    chain_id: int,
    api_key: str,
    address: str,
    action: str,
    start_ts: int,
    end_ts: int,
    block_start: int,
    block_end: int,
    api_url: str,
    use_legacy_api: bool,
    delay: float,
) -> list[dict[str, Any]]:
    params = _with_chain_id(
        {
        "module": "account",
        "action": action,
        "address": address,
        "startblock": block_start,
        "endblock": block_end,
        "page": 1,
        "offset": 10_000,
        "sort": "asc",
        "apikey": api_key,
        },
        chain_id,
        use_legacy_api,
    )
    batch = _request_with_retry(api_url, params, delay=delay)
    return [
        tx for tx in batch
        if start_ts <= int(tx.get("timeStamp", 0)) <= end_ts
    ]


def _build_block_ranges(start_block: int, end_block: int, block_step: int) -> list[tuple[int, int]]:
    ranges = []
    cur = start_block
    while cur <= end_block:
        nxt = min(cur + block_step - 1, end_block)
        ranges.append((cur, nxt))
        cur = nxt + 1
    return ranges


def fetch_evm_account_action(
    *,
    chain_id: int,
    api_key: str,
    address: str,
    action: str,
    start_ts: int,
    end_ts: int,
    start_block: int,
    end_block: int,
    api_url: str,
    use_legacy_api: bool,
    delay: float,
    workers: int,
    block_step: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    ranges = _build_block_ranges(start_block, end_block, block_step)
    max_workers = max(1, workers)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(
                _fetch_range,
                chain_id=chain_id,
                api_key=api_key,
                address=address,
                action=action,
                start_ts=start_ts,
                end_ts=end_ts,
                block_start=block_start,
                block_end=block_end,
                api_url=api_url,
                use_legacy_api=use_legacy_api,
                delay=delay,
            )
            for block_start, block_end in ranges
        ]
        for future in as_completed(futures):
            rows.extend(future.result())
    return rows


def collect_evm_chain(
    service: str,
    chain: str,
    year: int,
    *,
    delay: float = 0.25,
    workers: int = 4,
    block_step: int = 100_000,
    use_legacy_api: bool = False,
    allow_wide_fallback: bool = False,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    cfg = EVM_CHAINS[chain]
    if chain != "ethereum" and cfg.legacy_api_url and not use_legacy_api:
        print(f"{chain}: using legacy explorer API ({cfg.legacy_api_url})")
        use_legacy_api = True

    api_key = cfg.api_key
    if use_legacy_api:
        import os

        api_key = os.getenv(cfg.api_key_env)
        if not api_key and chain == "ethereum":
            api_key = cfg.api_key
    if not api_key:
        if use_legacy_api and chain != "ethereum":
            raise SystemExit(f"Missing {cfg.api_key_env} in .env for {chain} legacy explorer API")
        raise SystemExit(f"Missing ETHERSCAN_API_KEY or {cfg.api_key_env} in .env")
    wallets = service_hot_wallets(service, chain)
    if not wallets:
        raise SystemExit(f"Missing {service.upper()}_HOT_WALLETS_{chain.upper()} in .env")

    start_ts, end_ts = _time_bounds(year, start_date, end_date)
    api_url = _api_url(cfg, use_legacy_api)
    start_block = _request_block_by_timestamp_or_none(
        cfg.chain_id,
        api_key,
        start_ts,
        "after",
        api_url=api_url,
        use_legacy_api=use_legacy_api,
        delay=delay,
        allow_wide_fallback=allow_wide_fallback,
    )
    end_block = _request_block_by_timestamp_or_none(
        cfg.chain_id,
        api_key,
        end_ts,
        "before",
        api_url=api_url,
        use_legacy_api=use_legacy_api,
        delay=delay,
        allow_wide_fallback=allow_wide_fallback,
    )
    if start_block is None or end_block is None:
        start_block = 0
        end_block = 99_999_999
    out_dir = REPO_ROOT / "data" / "raw" / "multichain" / service / str(year) / chain
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "service": service,
        "chain": chain,
        "year": year,
        "start_date": start_date,
        "end_date": end_date,
        "wallets": wallets,
        "native": 0,
        "token": 0,
    }
    for wallet in wallets:
        native = fetch_evm_account_action(
            chain_id=cfg.chain_id,
            api_key=api_key,
            address=wallet,
            action="txlist",
            start_ts=start_ts,
            end_ts=end_ts,
            start_block=start_block,
            end_block=end_block,
            api_url=api_url,
            use_legacy_api=use_legacy_api,
            delay=delay,
            workers=workers,
            block_step=block_step,
        )
        token = fetch_evm_account_action(
            chain_id=cfg.chain_id,
            api_key=api_key,
            address=wallet,
            action="tokentx",
            start_ts=start_ts,
            end_ts=end_ts,
            start_block=start_block,
            end_block=end_block,
            api_url=api_url,
            use_legacy_api=use_legacy_api,
            delay=delay,
            workers=workers,
            block_step=block_step,
        )
        safe_wallet = wallet.lower()
        (out_dir / f"{safe_wallet}_native.json").write_text(json.dumps(native, indent=2), encoding="utf-8")
        (out_dir / f"{safe_wallet}_token.json").write_text(json.dumps(token, indent=2), encoding="utf-8")
        summary["native"] += len(native)
        summary["token"] += len(token)
        print(f"{chain}:{wallet} native={len(native)} token={len(token)}")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect EVM hot-wallet txs from Etherscan-family APIs")
    parser.add_argument("--service", required=True, choices=["sideshift", "fixedfloat", "changenow"])
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--chains", nargs="+", default=["ethereum", "bsc", "polygon", "arbitrum", "base"])
    parser.add_argument("--delay", type=float, default=0.25)
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--block-step", type=int, default=100_000)
    parser.add_argument("--legacy-api", action="store_true", help="Use chain-specific V1 explorer APIs and keys")
    parser.add_argument(
        "--allow-wide-fallback",
        action="store_true",
        help="If block timestamp lookup fails, scan 0..99999999 blocks. Slow and usually not recommended.",
    )
    args = parser.parse_args()

    summaries = []
    for chain in args.chains:
        if chain not in EVM_CHAINS:
            raise SystemExit(f"Unsupported EVM chain: {chain}. Known: {', '.join(EVM_CHAINS)}")
        try:
            summaries.append(
                collect_evm_chain(
                    args.service,
                    chain,
                    args.year,
                    delay=args.delay,
                    workers=args.workers,
                    block_step=args.block_step,
                    use_legacy_api=args.legacy_api,
                    allow_wide_fallback=args.allow_wide_fallback,
                    start_date=args.start_date,
                    end_date=args.end_date,
                )
            )
        except Exception as exc:
            summary = {
                "service": args.service,
                "chain": chain,
                "year": args.year,
                "error": str(exc),
                "native": 0,
                "token": 0,
            }
            summaries.append(summary)
            print(f"SKIP {chain}: {exc}")
    print(json.dumps(summaries, indent=2))


if __name__ == "__main__":
    main()
