import base58


def hex_to_base58(hex_addr: str) -> str:
    """
    Convert Tron hex address (41...) to base58 (T...)
    """
    if not hex_addr or not isinstance(hex_addr, str):
        return None
    if hex_addr.startswith("41"):
        addr_bytes = bytes.fromhex(hex_addr)
        return base58.b58encode_check(addr_bytes).decode()
    return None
