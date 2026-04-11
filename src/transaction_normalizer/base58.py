# Module: base58.py
# Chức năng: Chuyển đổi địa chỉ Tron từ định dạng hex (bắt đầu bằng '41') sang định dạng base58 (bắt đầu bằng 'T').

import base58


def hex_to_base58(hex_addr: str) -> str:
    """
    Chuyển đổi địa chỉ Tron từ định dạng hex (bắt đầu bằng '41') sang định dạng base58 (bắt đầu bằng 'T').
    - hex_addr: Địa chỉ hex (chuỗi ký tự, ví dụ: '41...')
    Trả về: Địa chỉ base58 (chuỗi ký tự, ví dụ: 'T...'), hoặc None nếu không hợp lệ.
    """
    if not hex_addr or not isinstance(hex_addr, str):
        return None
    if hex_addr.startswith("41"):
        addr_bytes = bytes.fromhex(hex_addr)
        return base58.b58encode_check(addr_bytes).decode()
    return None
