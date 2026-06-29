from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.tron_ice.config.multichain import EVM_CHAINS, service_hot_wallets


def _load_json(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def _txid(tx: dict[str, Any]) -> str | None:
    return tx.get("hash") or tx.get("transactionHash") or tx.get("tx_hash") or tx.get("txid")


def _normalize_native(tx: dict[str, Any], chain: str, native_token: str) -> dict[str, Any] | None:
    try:
        amount = int(tx.get("value", "0")) / 10**18
        if amount <= 0:
            return None
        ts = int(tx["timeStamp"]) * 1000
        return {
            "chain": chain,
            "network": chain,
            "timestamp": ts,
            "token": native_token,
            "amount": amount,
            "from": str(tx.get("from") or "").lower(),
            "to": str(tx.get("to") or "").lower(),
            "tx_hash": _txid(tx),
            "raw": tx,
        }
    except Exception:
        return None


def _normalize_token(tx: dict[str, Any], chain: str) -> dict[str, Any] | None:
    try:
        decimals = int(tx.get("tokenDecimal") or 0)
        amount = int(tx.get("value", "0")) / 10**decimals
        if amount <= 0:
            return None
        ts = int(tx["timeStamp"]) * 1000
        return {
            "chain": chain,
            "network": chain,
            "timestamp": ts,
            "token": str(tx.get("tokenSymbol") or "").upper(),
            "amount": amount,
            "from": str(tx.get("from") or "").lower(),
            "to": str(tx.get("to") or "").lower(),
            "tx_hash": _txid(tx),
            "contract": str(tx.get("contractAddress") or "").lower(),
            "raw": tx,
        }
    except Exception:
        return None


def _classify(rows: list[dict[str, Any]], wallets: set[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    deposits: list[dict[str, Any]] = []
    withdrawals: list[dict[str, Any]] = []
    for tx in rows:
        from_addr = str(tx.get("from") or "").lower()
        to_addr = str(tx.get("to") or "").lower()
        if to_addr in wallets and from_addr not in wallets:
            deposits.append(tx)
        elif from_addr in wallets and to_addr not in wallets:
            withdrawals.append(tx)
    return deposits, withdrawals


def normalize_evm_chain(service: str, chain: str, year: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cfg = EVM_CHAINS[chain]
    wallets = {w.lower() for w in service_hot_wallets(service, chain)}
    if not wallets:
        raise SystemExit(f"Missing {service.upper()}_HOT_WALLETS_{chain.upper()} in .env")

    raw_dir = REPO_ROOT / "data" / "raw" / "multichain" / service / str(year) / chain
    rows: list[dict[str, Any]] = []
    for wallet in wallets:
        for tx in _load_json(raw_dir / f"{wallet}_native.json"):
            norm = _normalize_native(tx, chain, cfg.native_token)
            if norm:
                rows.append(norm)
        for tx in _load_json(raw_dir / f"{wallet}_token.json"):
            norm = _normalize_token(tx, chain)
            if norm:
                rows.append(norm)

    deposits, withdrawals = _classify(rows, wallets)
    deposits.sort(key=lambda x: x["timestamp"])
    withdrawals.sort(key=lambda x: x["timestamp"])
    return deposits, withdrawals


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize EVM raw files into multichain classified files")
    parser.add_argument("--service", required=True, choices=["sideshift", "fixedfloat", "changenow"])
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--chains", nargs="+", default=["ethereum", "bsc", "polygon", "arbitrum", "base"])
    args = parser.parse_args()

    out_dir = REPO_ROOT / "data" / "classified" / "multichain"
    out_dir.mkdir(parents=True, exist_ok=True)
    all_deposits: list[dict[str, Any]] = []
    all_withdrawals: list[dict[str, Any]] = []

    for chain in args.chains:
        deposits, withdrawals = normalize_evm_chain(args.service, chain, args.year)
        all_deposits.extend(deposits)
        all_withdrawals.extend(withdrawals)
        print(f"{chain}: deposits={len(deposits)} withdrawals={len(withdrawals)}")

    all_deposits.sort(key=lambda x: x["timestamp"])
    all_withdrawals.sort(key=lambda x: x["timestamp"])
    dep_path = out_dir / f"deposits_{args.service}_{args.year}.json"
    wit_path = out_dir / f"withdrawals_{args.service}_{args.year}.json"
    dep_path.write_text(json.dumps(all_deposits, indent=2, ensure_ascii=False), encoding="utf-8")
    wit_path.write_text(json.dumps(all_withdrawals, indent=2, ensure_ascii=False), encoding="utf-8")
    print({"deposits": len(all_deposits), "withdrawals": len(all_withdrawals), "deposit_file": str(dep_path), "withdrawal_file": str(wit_path)})


if __name__ == "__main__":
    main()
