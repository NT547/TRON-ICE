from typing import Dict, List
import bisect


def generate_candidates(
    deposits: List[Dict],
    withdrawals: List[Dict],
    max_time_diff: int = 600,
    max_rv: float = 0.15,
    same_token_only: bool = False,
) -> List[Dict]:
    """
    Generate candidate deposit/withdrawal pairs.

    Cross-chain swaps can change token and chain, so token equality is no
    longer a hard filter by default. Use same_token_only=True for the legacy
    same-token TRON flow behavior.
    """
    withdrawals_sorted = sorted(withdrawals, key=lambda x: x["timestamp"])
    w_times = [w["timestamp"] for w in withdrawals_sorted]

    candidates = []
    for d in deposits:
        td = d["timestamp"]
        vd = float(d["usd_value"])
        left = bisect.bisect_right(w_times, td)
        right = bisect.bisect_right(w_times, td + max_time_diff * 1000)

        for w in withdrawals_sorted[left:right]:
            if same_token_only and d.get("token") != w.get("token"):
                continue

            tw = w["timestamp"]
            vw = float(w["usd_value"])
            delta_t = (tw - td) // 1000
            if delta_t <= 0 or delta_t > max_time_diff:
                continue

            rv = abs(vd - vw) / max(abs(vd), abs(vw), 1e-12)
            if rv > max_rv:
                continue

            candidates.append({"deposit": d, "withdrawal": w})

    return candidates
