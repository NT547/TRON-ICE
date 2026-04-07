from src.utils.helper import normalize_trx

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
            "txid": tx["txID"],
            "from": val.get("owner_address"),
            "to": val.get("to_address"),
            "value": normalize_trx(val.get("amount", 0)),  # convert sun → TRX
            "token": None,
            "timestamp": tx["block_timestamp"],
        }

    except Exception:
        return None