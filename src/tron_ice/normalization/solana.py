from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.tron_ice.config.multichain import SOLANA_TOKEN_MINTS, service_hot_wallets


LAMPORTS_PER_SOL = 1_000_000_000


def _load_json(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def _account_keys(tx: dict[str, Any]) -> list[str]:
    message = ((tx.get("transaction") or {}).get("message") or {})
    keys = []
    for item in message.get("accountKeys") or []:
        if isinstance(item, dict):
            keys.append(str(item.get("pubkey") or ""))
        else:
            keys.append(str(item))
    return keys


def _tx_timestamp_ms(wrapper: dict[str, Any]) -> int | None:
    info = wrapper.get("signature_info") or {}
    tx = wrapper.get("transaction") or {}
    block_time = tx.get("blockTime") or info.get("blockTime")
    if block_time is None:
        return None
    return int(block_time) * 1000


def _signature(wrapper: dict[str, Any]) -> str | None:
    info = wrapper.get("signature_info") or {}
    tx = wrapper.get("transaction") or {}
    sigs = ((tx.get("transaction") or {}).get("signatures") or [])
    return info.get("signature") or (sigs[0] if sigs else None)


def _token_amount(balance: dict[str, Any]) -> float:
    amount = ((balance.get("uiTokenAmount") or {}).get("uiAmount"))
    if amount is not None:
        return float(amount)
    raw = (balance.get("uiTokenAmount") or {}).get("amount") or "0"
    decimals = int((balance.get("uiTokenAmount") or {}).get("decimals") or 0)
    return int(raw) / (10 ** decimals)


def _sol_rows(wrapper: dict[str, Any], wallets: set[str]) -> list[dict[str, Any]]:
    tx = wrapper.get("transaction") or {}
    meta = tx.get("meta") or {}
    keys = _account_keys(tx)
    pre = meta.get("preBalances") or []
    post = meta.get("postBalances") or []
    timestamp = _tx_timestamp_ms(wrapper)
    sig = _signature(wrapper)
    if timestamp is None or not sig:
        return []

    rows = []
    fee_payer = keys[0] if keys else None
    for idx, pubkey in enumerate(keys):
        if pubkey not in wallets or idx >= len(pre) or idx >= len(post):
            continue
        delta = (int(post[idx]) - int(pre[idx])) / LAMPORTS_PER_SOL
        if not delta:
            continue
        # Fee payer pays fees; keep the signed amount delta because it reflects
        # wallet balance movement visible to an investigator.
        rows.append(
            {
                "chain": "solana",
                "network": "solana",
                "timestamp": timestamp,
                "token": "SOL",
                "amount": abs(delta),
                "direction": "deposit" if delta > 0 else "withdrawal",
                "from": None if delta > 0 else pubkey,
                "to": pubkey if delta > 0 else None,
                "tx_hash": sig,
                "fee_payer": fee_payer,
                "raw": wrapper,
            }
        )
    return rows


def _token_deltas(wrapper: dict[str, Any], wallets: set[str]) -> list[dict[str, Any]]:
    tx = wrapper.get("transaction") or {}
    meta = tx.get("meta") or {}
    timestamp = _tx_timestamp_ms(wrapper)
    sig = _signature(wrapper)
    if timestamp is None or not sig:
        return []

    pre_by_key = {}
    post_by_key = {}
    for balance in meta.get("preTokenBalances") or []:
        key = (balance.get("accountIndex"), balance.get("mint"), balance.get("owner"))
        pre_by_key[key] = _token_amount(balance)
    for balance in meta.get("postTokenBalances") or []:
        key = (balance.get("accountIndex"), balance.get("mint"), balance.get("owner"))
        post_by_key[key] = _token_amount(balance)

    rows = []
    for key in sorted(set(pre_by_key) | set(post_by_key), key=str):
        _, mint, owner = key
        if owner not in wallets:
            continue
        before = pre_by_key.get(key, 0.0)
        after = post_by_key.get(key, 0.0)
        delta = after - before
        if not delta:
            continue
        token = SOLANA_TOKEN_MINTS.get(str(mint), str(mint))
        rows.append(
            {
                "chain": "solana",
                "network": "solana",
                "timestamp": timestamp,
                "token": token,
                "amount": abs(delta),
                "direction": "deposit" if delta > 0 else "withdrawal",
                "from": None if delta > 0 else owner,
                "to": owner if delta > 0 else None,
                "tx_hash": sig,
                "contract": mint,
                "raw": wrapper,
            }
        )
    return rows


def normalize_solana_chain(service: str, year: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    wallets = set(service_hot_wallets(service, "solana"))
    if not wallets:
        raise SystemExit(f"Missing {service.upper()}_HOT_WALLETS_SOLANA in .env")

    raw_dir = REPO_ROOT / "data" / "raw" / "multichain" / service / str(year) / "solana"
    rows: list[dict[str, Any]] = []
    for wallet in wallets:
        for wrapper in _load_json(raw_dir / f"{wallet}_transactions.json"):
            rows.extend(_sol_rows(wrapper, wallets))
            rows.extend(_token_deltas(wrapper, wallets))

    deposits = [row for row in rows if row.get("direction") == "deposit"]
    withdrawals = [row for row in rows if row.get("direction") == "withdrawal"]
    for row in deposits + withdrawals:
        row.pop("direction", None)
    deposits.sort(key=lambda x: x["timestamp"])
    withdrawals.sort(key=lambda x: x["timestamp"])
    return deposits, withdrawals


def _merge_chain_rows(
    path: Path,
    chain: str,
    new_rows: list[dict[str, Any]],
) -> None:
    old_rows = [row for row in _load_json(path) if row.get("chain") != chain and row.get("network") != chain]
    rows = old_rows + new_rows
    rows.sort(key=lambda x: int(x.get("timestamp") or 0))
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize Solana raw files into multichain classified files")
    parser.add_argument("--service", required=True, choices=["sideshift", "fixedfloat", "changenow"])
    parser.add_argument("--year", type=int, required=True)
    args = parser.parse_args()

    deposits, withdrawals = normalize_solana_chain(args.service, args.year)
    out_dir = REPO_ROOT / "data" / "classified" / "multichain"
    out_dir.mkdir(parents=True, exist_ok=True)
    dep_path = out_dir / f"deposits_{args.service}_{args.year}.json"
    wit_path = out_dir / f"withdrawals_{args.service}_{args.year}.json"
    _merge_chain_rows(dep_path, "solana", deposits)
    _merge_chain_rows(wit_path, "solana", withdrawals)
    print(
        {
            "chain": "solana",
            "deposits": len(deposits),
            "withdrawals": len(withdrawals),
            "deposit_file": str(dep_path),
            "withdrawal_file": str(wit_path),
        }
    )


if __name__ == "__main__":
    main()
