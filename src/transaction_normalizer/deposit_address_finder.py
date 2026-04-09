import json
import os
from typing import List, Dict, Any, Set
from collections import Counter
from .data_normalizer import normalize_transactions_from_files


from typing import Optional


def is_contract_address(address: Optional[str]) -> bool:
    """
    Heuristic to check if an address is a contract address.
    Contract addresses on TRON often start with specific prefixes or have patterns.
    """
    if not isinstance(address, str):
        return False
    # Simple heuristic: if address starts with 'T9' or '41', likely contract
    # But this is not perfect; in practice, might need more checks
    return address.startswith("T9") or address.startswith("41")


def find_deposit_addresses_from_files(
    trx_file: str, trc20_file: str, hot_wallet: str, min_frequency: int = 5
) -> List[str]:
    """
    Load, normalize, and find deposit addresses.
    """
    normalized = normalize_transactions_from_files(trx_file, trc20_file)
    return find_deposit_addresses(normalized, hot_wallet, min_frequency)


def find_deposit_addresses_from_files(
    trx_file: str, trc20_file: str, hot_wallet: str, min_frequency: int = 5
) -> List[str]:
    """
    Load, normalize, and find deposit addresses.
    """
    normalized = normalize_transactions_from_files(trx_file, trc20_file)
    return find_deposit_addresses(normalized, hot_wallet, min_frequency)


def find_deposit_addresses(
    normalized_data: List[Dict[str, Any]], hot_wallet: str, min_frequency: int = 5
) -> List[str]:
    """
    Find deposit addresses by analyzing transactions to hot wallet.
    """
    deposit_candidates = []
    tx_to_hot_wallet = 0
    for tx in normalized_data:
        if tx["to"] == hot_wallet:
            tx_to_hot_wallet += 1
            from_addr = tx["from"]
            if not is_contract_address(from_addr):
                deposit_candidates.append(from_addr)

    print(f"Transactions to hot wallet: {tx_to_hot_wallet}")
    print(f"Deposit candidates after filtering contracts: {len(deposit_candidates)}")

    # Count frequency
    freq = Counter(deposit_candidates)
    print(f"Frequency counts: {dict(freq.most_common(10))}")  # Top 10

    # Filter by minimum frequency to avoid noise
    deposit_addresses = [addr for addr, count in freq.items() if count >= min_frequency]
    print(
        f"Deposit addresses after frequency filter (>= {min_frequency}): {len(deposit_addresses)}"
    )
    return deposit_addresses


def save_deposit_addresses(deposit_addresses: List[str], output_file: str):
    """
    Save deposit addresses to JSON file.
    """
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(deposit_addresses, f, indent=2, ensure_ascii=False)
