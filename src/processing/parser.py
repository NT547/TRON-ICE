# ==========================================
# Module: parser.py
# Mục đích: Cung cấp các hàm phân tích (parse) dữ liệu giao dịch TRON (TRX, TRC20),
# chuyển đổi địa chỉ, chuẩn hóa dữ liệu đầu vào cho các bước xử lý tiếp theo.
# ==========================================

import hashlib
import base58
from src.utils.helper import normalize_trx


# ==========================================
# HÀM HELPER CHUYỂN ĐỔI ĐỊA CHỈ TRON
# ==========================================
def hex_to_base58(hex_string):
    """
    Chuyển đổi địa chỉ Hex (bắt đầu bằng 41 hoặc 0x) của Tron sang địa chỉ Base58 (bắt đầu bằng T).
    Nếu đầu vào đã là Base58 thì trả về luôn.
    Nếu đầu vào là Hex, thực hiện mã hóa Base58Check theo chuẩn Tron.
    Trả về địa chỉ Base58 hoặc giữ nguyên nếu lỗi.
    """
    if not hex_string:
        return None
    try:
        # Nếu đã là Base58 (Bắt đầu bằng T) thì giữ nguyên
        if hex_string.startswith("T"):
            return hex_string
        # Nếu bắt đầu bằng 0x thì đổi thành 41 (Chuẩn Hex của Tron)
        if hex_string.startswith("0x"):
            hex_string = "41" + hex_string[2:]
        b = bytes.fromhex(hex_string)
        # Chuẩn mã hóa Base58Check của mạng Tron
        hash1 = hashlib.sha256(b).digest()
        hash2 = hashlib.sha256(hash1).digest()
        checksum = hash2[:4]
        return base58.b58encode(b + checksum).decode("utf-8")
    except Exception as e:
        print(f"Lỗi convert địa chỉ {hex_string}: {e}")
        return hex_string


def parse_trc20(tx):
    """
    Phân tích một giao dịch TRC20 từ dữ liệu JSON gốc.
    Chuẩn hóa giá trị token theo decimals, lấy các trường quan trọng.

    Tham số:
        tx (dict): Dữ liệu giao dịch TRC20 dạng dict.

    Trả về:
        dict chứa thông tin đã chuẩn hóa hoặc None nếu lỗi.
    """
    try:
        value = int(tx.get("value", 0))
        decimals = int(tx["token_info"].get("decimals", 0))

        return {
            "chain": "tron",
            "type": "TRC20",
            "txid": tx.get("transaction_id"),
            "from": tx.get("from"),
            "to": tx.get("to"),
            "value": value / (10**decimals),  # normalize
            "token": tx["token_info"].get("symbol"),
            "timestamp": tx.get("block_timestamp"),
        }

    except Exception:
        return None


def parse_trx(tx):
    """
    Phân tích một giao dịch TRX (native coin) từ dữ liệu JSON gốc.
    Lấy các trường quan trọng, chuyển đổi địa chỉ từ Hex sang Base58, chuẩn hóa giá trị.

    Tham số:
        tx (dict): Dữ liệu giao dịch TRX dạng dict.

    Trả về:
        dict chứa thông tin đã chuẩn hóa hoặc None nếu lỗi.
    """
    try:
        contract = tx["raw_data"]["contract"][0]

        # Kiểm tra đúng loại giao dịch chuyển TRX
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
            "timestamp": tx.get(
                "block_timestamp", tx.get("raw_data", {}).get("timestamp")
            ),
        }

    except Exception:
        return None
