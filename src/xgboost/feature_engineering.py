import math
from datetime import datetime
from typing import Dict, List

import numpy as np


STABLE_TOKENS = {"USDT", "USDC", "DAI", "BUSD", "TUSD", "USDD", "EURC", "USDT0"}


FEATURE_NAMES = [
    "rv",
    "delta_t",
    "sT",
    "token_match",
    "chain_match",
    "cross_chain",
    "stable_in",
    "stable_out",
    "stable_pair",
    "reuse",
    "log_deposit_usd",
    "log_withdrawal_usd",
    "amount_ratio_log",
    "hour",
]


def _norm(value: object) -> str:
    return str(value or "").strip().lower()


def _token(value: object) -> str:
    return str(value or "").strip().upper()


def _chain(tx: Dict) -> str:
    return _norm(tx.get("chain") or tx.get("network"))


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def extract_features(
    candidate_pairs: List[Dict], lambda_decay: float = 0.005
) -> np.ndarray:
    """
    Extract numeric features for deposit/withdrawal candidate pairs.

    The schema supports cross-token and cross-chain swaps. It keeps token/chain
    equality as model features instead of filtering candidates before scoring.
    """
    features = []
    for pair in candidate_pairs:
        d = pair["deposit"]
        w = pair["withdrawal"]

        vd = _safe_float(d.get("usd_value"))
        vw = _safe_float(w.get("usd_value"))
        ad = _safe_float(d.get("amount"))
        aw = _safe_float(w.get("amount"))
        td = int(d["timestamp"])
        tw = int(w["timestamp"])

        rv = abs(vd - vw) / max(abs(vd), abs(vw), 1e-12)
        delta_t = (tw - td) // 1000
        sT = math.exp(-lambda_decay * max(delta_t, 0))

        d_token = _token(d.get("token"))
        w_token = _token(w.get("token"))
        d_chain = _chain(d)
        w_chain = _chain(w)

        token_match = 1 if d_token == w_token and d_token else 0
        chain_match = 1 if d_chain == w_chain and d_chain else 0
        cross_chain = 1 if d_chain and w_chain and d_chain != w_chain else 0
        stable_in = 1 if d_token in STABLE_TOKENS else 0
        stable_out = 1 if w_token in STABLE_TOKENS else 0
        stable_pair = 1 if stable_in and stable_out else 0

        reuse = 1 if d.get("from") and d.get("from") == w.get("to") else 0
        log_deposit_usd = math.log(max(vd, 0.0) + 1.0)
        log_withdrawal_usd = math.log(max(vw, 0.0) + 1.0)
        amount_ratio_log = math.log((abs(ad) + 1e-12) / (abs(aw) + 1e-12))
        hour = datetime.utcfromtimestamp(td // 1000).hour

        features.append(
            [
                rv,
                delta_t,
                sT,
                token_match,
                chain_match,
                cross_chain,
                stable_in,
                stable_out,
                stable_pair,
                reuse,
                log_deposit_usd,
                log_withdrawal_usd,
                amount_ratio_log,
                hour,
            ]
        )

    return np.array(features)
