import json
import os
from typing import List, Dict, Any
from .deposit_address_finder import is_contract_address
from .data_normalizer import normalize_transactions_from_files


def is_valid_token_symbol(token: str) -> bool:
    if not token or not isinstance(token, str):
        return False
    token = token.strip()
    if not token or token.upper() == "UNKNOWN":
        return False
    if len(token) > 12:
        return False
    if any(ch.isspace() for ch in token):
        return False
    if not token.isalnum():
        return False
    return True


def filter_noise_transactions(
    normalized_data: List[Dict[str, Any]], hot_wallet: str
) -> List[Dict[str, Any]]:
    clean_transactions = []
    ignored_counts = {
        "hotwallet_internal": 0,
        "token_noise": 0,
        "contract_noise": 0,
    }

    for tx in normalized_data:
        from_addr = tx.get("from") or ""
        to_addr = tx.get("to") or ""
        token = tx.get("token") or ""

        if from_addr == hot_wallet and to_addr == hot_wallet:
            ignored_counts["hotwallet_internal"] += 1
            continue

        if not is_valid_token_symbol(token):
            ignored_counts["token_noise"] += 1
            continue

        if is_contract_address(from_addr) or is_contract_address(to_addr):
            ignored_counts["contract_noise"] += 1
            continue

        clean_transactions.append(tx)

    print(
        f"Filtered transactions: hotwallet_internal={ignored_counts['hotwallet_internal']}, "
        f"token_noise={ignored_counts['token_noise']}, contract_noise={ignored_counts['contract_noise']}"
    )
    return clean_transactions


def run_transaction_normalizer(
    trx_file: str, trc20_file: str, hot_wallet: str, min_frequency: int = 5
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Run the full transaction normalizer pipeline: load, normalize, classify.
    Note: Since data only contains transactions related to hot_wallet, deposits are approximated as tx to hot_wallet.
    """
    # Create log directory if not exists
    log_dir = "results/logs/normalizer+classifier"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(
        log_dir,
        f"normalizer_classifier_{os.path.basename(trx_file).replace('_trx.json', '.log')}",
    )

    with open(log_file, "w", encoding="utf-8") as log:
        log.write("Starting transaction normalizer pipeline...\n")

        # Check if files exist
        if not os.path.exists(trx_file):
            log.write(f"Error: TRX file not found: {trx_file}\n")
            return {"deposits": [], "withdrawals": []}
        if not os.path.exists(trc20_file):
            log.write(f"Error: TRC-20 file not found: {trc20_file}\n")
            return {"deposits": [], "withdrawals": []}

        # Normalize
        try:
            from src.utils.configs import TOKEN_WHITELIST

            normalized = normalize_transactions_from_files(trx_file, trc20_file)
            log.write(f"Normalized {len(normalized)} transactions\n")
            print(f"Normalized {len(normalized)} transactions")
            # Lọc chỉ giữ token hợp lệ theo whitelist
            before = len(normalized)
            normalized = [tx for tx in normalized if tx.get("token") in TOKEN_WHITELIST]
            log.write(
                f"Filtered by whitelist {TOKEN_WHITELIST}, remaining: {len(normalized)} (removed {before-len(normalized)})\n"
            )
            print(
                f"Filtered by whitelist {TOKEN_WHITELIST}, remaining: {len(normalized)} (removed {before-len(normalized)})"
            )
            # Save normalized transactions to data/normalize
            os.makedirs("data/normalize", exist_ok=True)
            norm_file = os.path.join(
                "data/normalize",
                f"normalized_{os.path.basename(trx_file).replace('_trx.json', '.json')}",
            )
            from src.transaction_normalizer.data_normalizer import (
                save_normalized_transactions,
            )

            save_normalized_transactions(normalized, norm_file)
            log.write(f"Saved normalized transactions to {norm_file}\n")
            print(f"Saved normalized transactions to {norm_file}")
        except Exception as e:
            log.write(f"Error during normalization: {e}\n")
            print(f"Error during normalization: {e}")
            return {"deposits": [], "withdrawals": []}

        if not normalized:
            log.write("No transactions to process after normalization.\n")
            print("No transactions to process after normalization.")
            return {"deposits": [], "withdrawals": []}

        # Filter noise before classification
        try:
            filtered = filter_noise_transactions(normalized, hot_wallet)
            log.write(
                f"Filtered transactions down to {len(filtered)} records after noise removal\n"
            )
            print(
                f"Filtered transactions down to {len(filtered)} records after noise removal"
            )
        except Exception as e:
            log.write(f"Error during noise filtering: {e}\n")
            print(f"Error during noise filtering: {e}")
            return {"deposits": [], "withdrawals": []}

        # Classify directly (approximating deposits as tx to hot_wallet)
        try:
            classified = classify_transactions_approx(filtered, hot_wallet)
            log.write(
                f"Classified into {len(classified['deposits'])} deposits, {len(classified['withdrawals'])} withdrawals, {len(classified.get('unclassified_trx', []))} unclassified_trx\n"
            )
            print(
                f"Classified into {len(classified['deposits'])} deposits, {len(classified['withdrawals'])} withdrawals, {len(classified.get('unclassified_trx', []))} unclassified_trx"
            )
            # Save classified to data/classified
            os.makedirs("data/classified", exist_ok=True)
            deposits_file = os.path.join(
                "data/classified",
                f"deposits_{os.path.basename(trx_file).replace('_trx.json', '.json')}",
            )
            withdrawals_file = os.path.join(
                "data/classified",
                f"withdrawals_{os.path.basename(trx_file).replace('_trx.json', '.json')}",
            )
            from src.transaction_normalizer.transaction_classifier import (
                save_classified_transactions,
            )

            save_classified_transactions(classified, deposits_file, withdrawals_file)
            log.write(f"Saved classified deposits to {deposits_file}\n")
            log.write(f"Saved classified withdrawals to {withdrawals_file}\n")
        except Exception as e:
            log.write(f"Error during classification: {e}\n")
            print(f"Error during classification: {e}")
            classified = {"deposits": [], "withdrawals": [], "unclassified_trx": []}

        log.write("Pipeline completed.\n")
        print("Pipeline completed.")

    return classified


def classify_transactions_approx(
    normalized_data: List[Dict[str, Any]], hot_wallet: str
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Approximate classification: deposits = tx to hot_wallet (from user), withdrawals = tx from hot_wallet (to user).
    """
    deposits = []
    withdrawals = []
    for tx in normalized_data:
        from_addr = tx["from"]
        to_addr = tx["to"]
        token = tx.get("token", "")
        txid = f"{from_addr}_{tx['timestamp']}_{to_addr}"
        tx["txid"] = txid
        # Phân loại cho tất cả token, bao gồm cả TRX
        if to_addr == hot_wallet and from_addr != hot_wallet:
            deposits.append(tx)
        elif from_addr == hot_wallet and to_addr != hot_wallet:
            withdrawals.append(tx)
        # Các trường hợp còn lại (ví dụ: chuyển nội bộ, hoặc không xác định) sẽ bị bỏ qua
    return {"deposits": deposits, "withdrawals": withdrawals}


def save_classified_transactions(
    classified: Dict[str, List[Dict[str, Any]]],
    deposits_file: str,
    withdrawals_file: str,
):
    """
    Save deposits and withdrawals to separate JSON files.
    """
    with open(deposits_file, "w", encoding="utf-8") as f:
        json.dump(classified["deposits"], f, indent=2, ensure_ascii=False)
    with open(withdrawals_file, "w", encoding="utf-8") as f:
        json.dump(classified["withdrawals"], f, indent=2, ensure_ascii=False)
