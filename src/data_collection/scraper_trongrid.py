import requests
import json
import os
import time
from datetime import datetime
from dotenv import load_dotenv
import sys

# Load environment variables
load_dotenv()
TRONGRID_API_KEY = os.getenv("TRONGRID_API_KEY") 
CONTRACT_ADDRESS = os.getenv("contract_address")
RELATED_ADDRESS = os.getenv("relatedAddress")

# Đổi URL sang TRONGRID
URL = f"https://api.trongrid.io/v1/accounts/{RELATED_ADDRESS}/transactions/trc20"

HEADERS = {
    "Accept": "application/json",
    "TRON-PRO-API-KEY": TRONGRID_API_KEY 
}

def scrape_trongrid_unlimited():
    os.makedirs("data/raw", exist_ok=True)
    all_transfers = []
    min_timestamp = datetime(2023, 1, 1).timestamp() * 1000  # Mốc thời gian cũ để bắt đầu
    max_timestamp = datetime(2023, 12,31,23,59,59).timestamp() * 1000  # Mốc thời gian cũ để bắt đầu  # Mốc thời gian hiện tại
    # Param ban đầu của TronGrid
    params = {
        "limit": 200, # TronGrid cho phép lấy tối đa 200 txs mỗi lần
        "order_by": "block_timestamp,asc", # Sắp xếp từ mới nhất đến cũ nhất 
        "contract_address": CONTRACT_ADDRESS,
        "only_confirmed": "true",
        "min_timestamp": int(min_timestamp),
        "max_timestamp": int(max_timestamp)
    }

    print(f"🚀 BẮT ĐẦU VÉT CẠN VÍ BẰNG TRONGRID: {RELATED_ADDRESS}")
    fingerprint = None
    page = 1

    try:
        while True:
            # Nếu có fingerprint từ lần gọi trước, ném vào params để lật trang
            if fingerprint:
                params["fingerprint"] = fingerprint

            response = requests.get(URL, headers=HEADERS, params=params)
            
            # Xử lý Rate Limit
            if response.status_code == 429:
                print("⚠️ Bị Rate Limit! Nghỉ 5s...")
                time.sleep(5)
                continue
                
            response.raise_for_status()
            data = response.json()
            
            # Lấy data giao dịch
            transfers = data.get("data", [])
            if not transfers:
                print("\n🎉 ĐÃ VÉT SẠCH! Không còn giao dịch nào trong ví này nữa.")
                break
                
            all_transfers.extend(transfers)
            
            # In log xem tiến độ
            oldest_time = datetime.fromtimestamp(transfers[-1]['block_timestamp'] / 1000).strftime('%Y-%m-%d %H:%M:%S')
            print(f"Trang {page}: Kéo thành công {len(transfers)} txs. Tổng: {len(all_transfers)} | Lùi về mốc: {oldest_time}")
            
            # Lấy fingerprint (chìa khóa lật trang) cho vòng lặp tiếp theo
            meta = data.get("meta", {})
            fingerprint = meta.get("fingerprint")
            
            # BƯỚC NGOẶT: Nếu API không trả về fingerprint nữa, nghĩa là đã chạm đáy ví
            if not fingerprint:
                print("\n✅ ĐÃ CHẠM ĐÁY VÍ (HẾT FINGERPRINT)!")
                break
                
            page += 1
            time.sleep(0.5) # Sleep nửa giây để bảo vệ API key

    except KeyboardInterrupt:
        print("\n🛑 [WARNING] Phát hiện Ctrl+C! Dừng khẩn cấp và chuẩn bị lưu file...")
    except Exception as e:
        print(f"\n❌ Lỗi API: {e}")

    finally:
        # Cơ chế an toàn: Luôn lưu file dù chạy xong hay bị dừng giữa chừng
        if all_transfers:
            final_file = f"data/raw/trongrid_{RELATED_ADDRESS[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(final_file, "w", encoding="utf-8") as f:
                json.dump(all_transfers, f, indent=4, ensure_ascii=False)
            print(f"\n🎉 QUÁ TRÌNH KẾT THÚC! Đã lưu an toàn {len(all_transfers)} giao dịch vào {final_file}")
        else:
            print("\n⚠️ Không có dữ liệu nào được thu thập.")
            sys.exit(0)

if __name__ == "__main__":
    scrape_trongrid_unlimited()