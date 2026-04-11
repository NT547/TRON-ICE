import requests
import time
from datetime import datetime

def get_historical_price(coin_id, timestamp):
    """
    Hàm lấy giá USD của một token tại một thời điểm cụ thể (Timestamp).
    coin_id: 'tether' (USDT) hoặc 'tron' (TRX)
    timestamp: UNIX timestamp của giao dịch trên mạng Tron
    """
    # Mở rộng khoảng thời gian tìm kiếm (+/- 1 giờ) để đảm bảo CoinGecko có điểm dữ liệu
    from_time = timestamp - 3600
    to_time = timestamp + 3600
    
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart/range"
    params = {
        'vs_currency': 'usd',
        'from': from_time,
        'to': to_time
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        # Lấy điểm giá gần nhất với timestamp của giao dịch
        if 'prices' in data and len(data['prices']) > 0:
            # Dữ liệu trả về có dạng [[timestamp_ms, price], ...]
            prices = data['prices']
            # Tìm giá trị trung bình hoặc lấy giá trị đầu tiên trong khoảng thời gian đó
            closest_price = prices[0][1] 
            return closest_price
        else:
            return None
            
    except Exception as e:
        print(f"Lỗi khi gọi API: {e}")
        return None

# --- CHẠY THỬ (TEST) ---
# Ví dụ: Lấy giá TRX vào ngày 01/01/2024
tx_timestamp = int(datetime(2024, 1, 1).timestamp())
trx_price_usd = get_historical_price('tron', tx_timestamp)

print(f"Giá TRX tại thời điểm {tx_timestamp} là: ${trx_price_usd}")

# TRÁNH RATE LIMIT CỦA COINGECKO:
time.sleep(3) # Bắt buộc phải cho script nghỉ 3-5 giây sau mỗi lần gọi!