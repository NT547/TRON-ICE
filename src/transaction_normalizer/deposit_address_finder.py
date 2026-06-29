import json
from collections import Counter
from typing import Any, Dict, List, Optional

from .data_normalizer import normalize_transactions_from_files


def is_contract_address(address: Optional[str]) -> bool:
    """Heuristic TRON contract-address filter."""
    if not isinstance(address, str):
        return False
    return address.startswith("T9") or address.startswith("41")

def find_deposit_addresses_from_files(
    trx_file: str,
    trc20_file: str,
    hot_wallet: str,
    min_frequency: int = 5,
) -> List[str]:
    normalized = normalize_transactions_from_files(trx_file, trc20_file)
    return find_deposit_addresses(normalized, hot_wallet, min_frequency)


def find_deposit_addresses(
    normalized_data: List[Dict[str, Any]],
    hot_wallet: str,
    min_frequency: int = 5,
) -> List[str]:
    deposit_candidates = []
    tx_to_hot_wallet = 0
    hot_wallet_norm = hot_wallet.lower()

    for tx in normalized_data:
        to_addr = tx.get("to")
        from_addr = tx.get("from")
        if isinstance(to_addr, str) and to_addr.lower() == hot_wallet_norm:
            tx_to_hot_wallet += 1
            if not is_contract_address(from_addr):
                deposit_candidates.append(from_addr)

    print(f"Transactions to hot wallet: {tx_to_hot_wallet}")
    print(f"Deposit candidates after filtering contracts: {len(deposit_candidates)}")

    freq = Counter(deposit_candidates)
    print(f"Frequency counts: {dict(freq.most_common(10))}")

    deposit_addresses = [
        addr for addr, count in freq.items()
        if addr is not None and count >= min_frequency
    ]
    print(
        f"Deposit addresses after frequency filter (>= {min_frequency}): "
        f"{len(deposit_addresses)}"
    )
    return deposit_addresses


def save_deposit_addresses(deposit_addresses: List[str], output_file: str) -> None:
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(deposit_addresses, f, indent=2, ensure_ascii=False)
