import hashlib
import base58
from src.utils.helper import normalize_trx
# ==========================================
# HÀM HELPER CHUYỂN ĐỔI ĐỊA CHỈ TRON
# ==========================================
def hex_to_base58(hex_string):
    """Chuyển đổi địa chỉ Hex (41...) của Tron sang Base58 (T...)"""
    if not hex_string:
        return None
    try:
        # Nếu đã là Base58 (Bắt đầu bằng T) thì giữ nguyên
        if hex_string.startswith('T'):
            return hex_string
            
        # Nếu bắt đầu bằng 0x thì đổi thành 41 (Chuẩn Hex của Tron)
        if hex_string.startswith('0x'):
            hex_string = '41' + hex_string[2:]
            
        b = bytes.fromhex(hex_string)
        # Chuẩn mã hóa Base58Check của mạng Tron
        hash1 = hashlib.sha256(b).digest()
        hash2 = hashlib.sha256(hash1).digest()
        checksum = hash2[:4]
        
        return base58.b58encode(b + checksum).decode('utf-8')
    except Exception as e:
        print(f"Lỗi convert địa chỉ {hex_string}: {e}")
        return hex_string
    
def parse_trc20(tx):
    try:
        value = int(tx.get("value", 0))
        decimals = int(tx["token_info"].get("decimals", 0))

        return {
            "chain": "tron",
            "type": "TRC20",
            "txid": tx.get("transaction_id"),
            "from": tx.get("from"),
            "to": tx.get("to"),
            "value": value / (10 ** decimals),  # normalize
            "token": tx["token_info"].get("symbol"),
            "timestamp": tx.get("block_timestamp"),
        }

    except Exception:
        return None

def parse_trx(tx):
    try:
        contract = tx["raw_data"]["contract"][0]

        # check đúng loại
        if contract["type"] != "TransferContract":
            return None

        val = contract["parameter"]["value"]

        return {
            "chain": "tron",
            "type": "TRX",
            "txid": tx.get("txID"),
            # Convert Hex sang Base58
            "from": hex_to_base58(val.get("owner_address")),
            "to": hex_to_base58(val.get("to_address")),
            "value": normalize_trx(val.get("amount", 0)),  # convert sun → TRX
            "token": "TRX",  # Clean code: Nên ghi rõ "TRX" thay vì None để dễ filter
            # Fallback timestamp đề phòng raw_data cấu trúc khác
            "timestamp": tx.get("block_timestamp", tx.get("raw_data", {}).get("timestamp")),
        }

    except Exception:
        return None