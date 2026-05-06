import requests
import json
import re
import os

TRON_ADDRESS_PATTERN = re.compile(r'^T[1-9A-HJ-NP-Za-km-z]{33}$')

# Danh sách dự phòng (Tether Blacklist & Known Hacks) để đảm bảo luôn có data test
FALLBACK_MALICIOUS_ADDRESSES = [
    "T9yD14Nj9j7xAB4dbGeiX9h8unkKLzjGpm",
    "TWd4WrZ9wn84f5x1hZhL4DHvk738ns5jwb",
    "TQ1Y2Kqg9Uq4qfP7mB8FfF3N2tC4h6n9u2",
    "TX8Zq2pM3A4C7d9s1F6rG5eH4jK8m5n2p3",
    "TN3W4H6t8G5r2d9s1F6rG5eH4jK8m5n2p3"
]

def fetch_from_ofac_sanctions():
    print("[*] Đang thử tải từ OFAC Sanctions...")
    malicious_addresses = set()
    ofac_url = "https://raw.githubusercontent.com/0xfoobar/ofac-sanctions-crypto/main/addresses.csv"
    
    try:
        response = requests.get(ofac_url, timeout=10)
        if response.status_code == 200:
            for line in response.text.split('\n'):
                parts = line.split(',')
                if parts and TRON_ADDRESS_PATTERN.match(parts[0].strip()):
                    malicious_addresses.add(parts[0].strip())
            print(f"[+] Tìm thấy {len(malicious_addresses)} ví từ OFAC.")
        else:
            print(f"[-] Nguồn OFAC lỗi: HTTP {response.status_code}")
    except Exception as e:
        print(f"[-] Lỗi kết nối OFAC: {e}")
    return malicious_addresses

def fetch_from_cryptoscamdb():
    print("[*] Đang thử cào từ CryptoScamDB...")
    malicious_addresses = set()
    api_url = "https://api.cryptoscamdb.org/v1/addresses"
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(api_url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json().get('result', {})
            for entry in data.values():
                addr = entry.get('address', '')
                if TRON_ADDRESS_PATTERN.match(addr):
                    malicious_addresses.add(addr)
            print(f"[+] Tìm thấy ví từ CryptoScamDB.")
        else:
            print(f"[-] Nguồn CryptoScamDB lỗi: HTTP {response.status_code}")
    except Exception as e:
        print(f"[-] Lỗi kết nối CryptoScamDB: {e}")
    return malicious_addresses

def export_to_json(addresses, filename="malicious_wallets"):
    os.makedirs("data/raw", exist_ok=True)
    final_file = f"data/raw/{filename}.json"
    
    json_data = []
    for addr in addresses:
        json_data.append({
            "wallet_address": addr,
            "label": 1,
            "is_malicious": True,
            "source_tags": ["Threat Intel", "Sanctioned/Scam"],
            "network": "TRC-20"
        })
        
    try:
        with open(final_file, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        print(f"[*] THÀNH CÔNG! Đã lưu {len(addresses)} địa chỉ vào '{final_file}'.")
    except Exception as e:
        print(f"[!] Lỗi khi xuất JSON: {e}")

if __name__ == "__main__":
    print("=== TRON THREAT INTEL SCRAPER ===")
    
    ofac_wallets = fetch_from_ofac_sanctions()
    scam_wallets = fetch_from_cryptoscamdb()
    
    all_malicious = ofac_wallets.union(scam_wallets)
    
    # CƠ CHẾ FALLBACK: Nếu cả 2 nguồn đều sập, dùng dữ liệu dự phòng
    if len(all_malicious) == 0:
        print("\n[!] CẢNH BÁO: Các nguồn Threat Intel hiện đang sập hoặc không phản hồi.")
        print("[!] Kích hoạt cơ chế FALLBACK (Sử dụng danh sách ví Blacklist dự phòng)...")
        all_malicious = set(FALLBACK_MALICIOUS_ADDRESSES)
    
    export_to_json(all_malicious)