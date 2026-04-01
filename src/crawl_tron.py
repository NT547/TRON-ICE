import requests
import pandas as pd
import json
import os
import time
from datetime import datetime
from dotenv import load_dotenv
from config import TRONGRID_API, TRONGRID_API_KEY, HOT_WALLETS, REQUEST_DELAY


HEADERS = {"Accept": "application/json", "TRON-PRO-API-KEY": TRONGRID_API_KEY}

ONLY_USDT = False  # True nếu chỉ muốn USDT


# ===== NORMALIZE =====
def normalize_trx(value):
    return value / 1_000_000


def normalize_token(value, decimals):
    return int(value) / (10 ** int(decimals))


# ===== CRAWL TRC20 =====
def crawl_trc20_full(address, max_tx):
    url = f"{TRONGRID_API}/accounts/{address}/transactions/trc20"

    params = {"limit": 200, "order_by": "block_timestamp,asc", "only_confirmed": "true"}

    all_data = []
    fingerprint = None
    page = 1

    while True:
        if fingerprint:
            params["fingerprint"] = fingerprint

        res = requests.get(url, headers=HEADERS, params=params)

        if res.status_code == 429:
            print("⚠️ Rate limit, sleep...")
            time.sleep(5)
            continue

        res.raise_for_status()
        data = res.json()

        txs = data.get("data", [])
        if not txs:
            break

        all_data.extend(txs)

        # 🛑 STOP SỚM
        if len(all_data) >= max_tx:
            print(f"🛑 STOP TRC20 API: reached {max_tx}")
            return all_data[:max_tx]

        meta = data.get("meta", {})
        fingerprint = meta.get("fingerprint")

        print(f"[TRC20] {address} | Page {page} | +{len(txs)}")

        if not fingerprint:
            break

        page += 1
        time.sleep(REQUEST_DELAY)

    return all_data


# ===== CRAWL TRX =====
def crawl_trx_full(address, max_tx):
    url = f"{TRONGRID_API}/accounts/{address}/transactions"

    params = {"limit": 200, "order_by": "block_timestamp,asc", "only_confirmed": "true"}

    all_data = []
    fingerprint = None
    page = 1

    while True:
        if fingerprint:
            params["fingerprint"] = fingerprint

        res = requests.get(url, headers=HEADERS, params=params)

        if res.status_code == 429:
            print("⚠️ Rate limit, sleep...")
            time.sleep(5)
            continue

        res.raise_for_status()
        data = res.json()

        txs = data.get("data", [])
        if not txs:
            break

        all_data.extend(txs)

        # 🛑 STOP SỚM
        if len(all_data) >= max_tx:
            print(f"🛑 STOP TRX API: reached {max_tx}")
            return all_data[:max_tx]

        meta = data.get("meta", {})
        fingerprint = meta.get("fingerprint")

        print(f"[TRX] {address} | Page {page} | +{len(txs)}")

        if not fingerprint:
            break

        page += 1
        time.sleep(REQUEST_DELAY)

    return all_data


# ===== PARSE =====
def parse_trc20(tx):
    try:
        token = tx["token_info"]["symbol"]

        if ONLY_USDT and token != "USDT":
            return None

        return {
            "chain": "tron",
            "type": "TRC20",
            "txid": tx["transaction_id"],
            "from": tx["from"],
            "to": tx["to"],
            "value": normalize_token(tx["value"], tx["token_info"]["decimals"]),
            "token": token,
            "timestamp": tx["block_timestamp"],
        }
    except:
        return None


def parse_trx(tx):
    try:
        val = tx["raw_data"]["contract"][0]["parameter"]["value"]

        return {
            "chain": "tron",
            "type": "TRX",
            "txid": tx["txID"],
            "from": val.get("owner_address"),
            "to": val.get("to_address"),
            "value": normalize_trx(val.get("amount", 0)),
            "token": None,
            "timestamp": tx["block_timestamp"],
        }
    except:
        return None


# ===== MAIN =====
def main():
    os.makedirs("data/raw/tron", exist_ok=True)
    os.makedirs("data/processed/tron", exist_ok=True)

    MAX_TX = 30000  # 🔥 GIỚI HẠN TỔNG

    for service, wallets in HOT_WALLETS.items():
        print(f"\n=== SERVICE: {service} ===")

        raw_all = []
        processed_all = []

        for w in wallets:
            print(f"\n>>> Crawling wallet: {w}")

            remaining = MAX_TX - len(processed_all)
            if remaining <= 0:
                print("🛑 STOP ALL: reached MAX_TX")
                break

            # ===== TRC20 =====
            trc20_raw = crawl_trc20_full(w, remaining)

            for tx in trc20_raw:
                raw_all.append(tx)

                parsed = parse_trc20(tx)
                if parsed:
                    parsed["service"] = service
                    parsed["wallet"] = w
                    processed_all.append(parsed)

                if len(processed_all) >= MAX_TX:
                    print("🛑 STOP after TRC20")
                    break

            # Nếu đã đủ thì không cần crawl TRX nữa
            if len(processed_all) >= MAX_TX:
                break

            # ===== TRX =====
            remaining = MAX_TX - len(processed_all)

            trx_raw = crawl_trx_full(w, remaining)

            for tx in trx_raw:
                raw_all.append(tx)

                parsed = parse_trx(tx)
                if parsed:
                    parsed["service"] = service
                    parsed["wallet"] = w
                    processed_all.append(parsed)

                if len(processed_all) >= MAX_TX:
                    print("🛑 STOP after TRX")
                    break

            if len(processed_all) >= MAX_TX:
                break

        # ===== SAVE RAW =====
        raw_file = f"data/raw/tron/{service}_raw.json"
        with open(raw_file, "w", encoding="utf-8") as f:
            json.dump(raw_all, f, indent=2)

        # ===== SAVE PROCESSED =====
        df = pd.DataFrame(processed_all)
        csv_file = f"data/processed/tron/{service}_processed.csv"
        df.to_csv(csv_file, index=False)

        print(f"💾 Saved RAW: {raw_file}")
        print(f"💾 Saved CSV: {csv_file}")
        print(f"✅ Total processed: {len(processed_all)}")


if __name__ == "__main__":
    main()
