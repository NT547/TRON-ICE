# Phân loại giao dịch thành DEPOSIT và WITHDRAWAL dựa trên danh sách hot wallets của từng service
# Ghi các file phân loại vào thư mục data/classified/{service}_deposits.csv và {service}_withdrawals.csv
import pandas as pd
import os
from config import HOT_WALLETS


def identify_operations(df, wallets):
    all_deposits = []
    all_withdrawals = []

    for hot_wallet in wallets:
        hot_wallet = hot_wallet.lower()

        d = df[df["to"].str.lower() == hot_wallet]
        w = df[df["from"].str.lower() == hot_wallet]

        all_deposits.append(d)
        all_withdrawals.append(w)

    deposits = pd.concat(all_deposits, ignore_index=True)
    withdrawals = pd.concat(all_withdrawals, ignore_index=True)

    return deposits, withdrawals


def main():
    os.makedirs("data/processed", exist_ok=True)

    for service, wallets in HOT_WALLETS.items():
        print(f"\n=== SERVICE: {service} ===")

        file_path = f"data/processed/tron/{service}_processed.csv"

        if not os.path.exists(file_path):
            print(f"❌ File not found: {file_path}")
            continue

        df = pd.read_csv(file_path)

        deposits, withdrawals = identify_operations(df, wallets)

        print(f"Deposits: {len(deposits)}")
        print(f"Withdrawals: {len(withdrawals)}")

        deposits.to_csv(f"data/classified/{service}_deposits.csv", index=False)
        withdrawals.to_csv(f"data/classified/{service}_withdrawals.csv", index=False)

        print("💾 Saved deposits & withdrawals")


if __name__ == "__main__":
    main()
