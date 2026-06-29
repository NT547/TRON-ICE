from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.tron_ice.config.multichain import EVM_CHAINS, canonical_chain
from src.tron_ice.normalization.evm import normalize_evm_chain
from src.tron_ice.normalization.solana import normalize_solana_chain
from src.tron_ice.normalization.tron import normalize_tron_hot_wallet


REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_json(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def _merge_chain_rows(path: Path, chain: str, new_rows: list[dict[str, Any]]) -> None:
    old_rows = [row for row in _load_json(path) if row.get("chain") != chain and row.get("network") != chain]
    rows = old_rows + new_rows
    rows.sort(key=lambda x: int(x.get("timestamp") or 0))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")


def normalize_onchain(
    service: str,
    year: int,
    *,
    chains: list[str],
) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    out_dir = REPO_ROOT / "data" / "classified" / "multichain"
    dep_path = out_dir / f"deposits_{service}_{year}.json"
    wit_path = out_dir / f"withdrawals_{service}_{year}.json"
    for raw_chain in chains:
        chain = canonical_chain(raw_chain)
        try:
            if chain in EVM_CHAINS:
                deposits, withdrawals = normalize_evm_chain(service, chain, year)
                _merge_chain_rows(dep_path, chain, deposits)
                _merge_chain_rows(wit_path, chain, withdrawals)
                summaries.append(
                    {
                        "chain": chain,
                        "deposits": len(deposits),
                        "withdrawals": len(withdrawals),
                        "status": "normalized",
                    }
                )
            elif chain == "solana":
                deposits, withdrawals = normalize_solana_chain(service, year)
                _merge_chain_rows(dep_path, "solana", deposits)
                _merge_chain_rows(wit_path, "solana", withdrawals)
                summaries.append(
                    {
                        "chain": "solana",
                        "deposits": len(deposits),
                        "withdrawals": len(withdrawals),
                        "status": "normalized",
                    }
                )
            elif chain == "tron":
                normalize_tron_hot_wallet(service, year)
                summaries.append({"chain": "tron", "status": "normalized"})
            elif chain in {"bitcoin", "liquid"}:
                summaries.append(
                    {
                        "chain": chain,
                        "status": "skipped",
                        "reason": "Not used for strict labels in this account-style pipeline.",
                    }
                )
            else:
                summaries.append({"chain": chain, "status": "skipped", "reason": "No normalizer configured."})
        except Exception as exc:
            summaries.append({"chain": chain, "status": "error", "error": str(exc)})
    print(json.dumps(summaries, indent=2, ensure_ascii=False))
    return summaries
