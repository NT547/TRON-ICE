from __future__ import annotations

import json
from typing import Any

from src.tron_ice.collection.evm import collect_evm_chain
from src.tron_ice.collection.solana import collect_solana_chain
from src.tron_ice.collection.tron import collect_trongrid_year
from src.tron_ice.config.multichain import EVM_CHAINS, canonical_chain


UNSUPPORTED_STRICT_CHAINS = {"bitcoin", "liquid"}


def collect_onchain_window(
    service: str,
    year: int,
    *,
    chains: list[str],
    start_date: str,
    end_date: str,
    workers: int = 4,
    use_legacy_api: bool = False,
    allow_wide_fallback: bool = False,
) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for raw_chain in chains:
        chain = canonical_chain(raw_chain)
        if not chain:
            continue
        try:
            if chain in EVM_CHAINS:
                summaries.append(
                    collect_evm_chain(
                        service,
                        chain,
                        year,
                        workers=workers,
                        start_date=start_date,
                        end_date=end_date,
                        use_legacy_api=use_legacy_api,
                        allow_wide_fallback=allow_wide_fallback,
                    )
                )
            elif chain == "solana":
                summaries.append(
                    collect_solana_chain(
                        service,
                        year,
                        start_date=start_date,
                        end_date=end_date,
                    )
                )
            elif chain == "tron":
                collect_trongrid_year(
                    service,
                    year,
                    workers=workers,
                    start_date=start_date,
                    end_date=end_date,
                )
                summaries.append(
                    {
                        "service": service,
                        "chain": "tron",
                        "year": year,
                        "start_date": start_date,
                        "end_date": end_date,
                        "status": "collected",
                    }
                )
            elif chain in UNSUPPORTED_STRICT_CHAINS:
                summaries.append(
                    {
                        "service": service,
                        "chain": chain,
                        "year": year,
                        "status": "skipped",
                        "reason": "UTXO/confidential structure is not used for strict D-W labels in this pipeline.",
                    }
                )
            else:
                summaries.append(
                    {
                        "service": service,
                        "chain": chain,
                        "year": year,
                        "status": "skipped",
                        "reason": "No collector configured.",
                    }
                )
        except (Exception, SystemExit) as exc:
            summaries.append(
                {
                    "service": service,
                    "chain": chain,
                    "year": year,
                    "status": "error",
                    "error": str(exc),
                }
            )
    print(json.dumps(summaries, indent=2, ensure_ascii=False))
    return summaries
