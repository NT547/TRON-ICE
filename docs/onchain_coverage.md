# On-Chain Coverage Audit

Current SideShift target window:

- Off-chain crawl: `2026-05-22` through `2026-06-28`.
- Train labels: `2026-05-22` through `2026-06-10`.
- Test labels: `2026-06-11` through `2026-06-28`.

## Existing Data In This Workspace

- TRON classified data exists:
  - `data/classified/deposits_trongrid_sideshift_2026.json`
  - `data/classified/withdrawals_trongrid_sideshift_2026.json`
- Multichain classified data exists:
  - `data/classified/multichain/deposits_sideshift_2026.json`
  - `data/classified/multichain/withdrawals_sideshift_2026.json`
- Raw multichain folders currently visible:
  - `data/raw/multichain/sideshift/2026/ethereum`
  - `data/raw/multichain/sideshift/2026/bsc`

## Collector/Normalizer Support

| Chain | Collector | Normalizer | Strict labels by default |
|---|---|---|---|
| ethereum | `src/tron_ice/collection/evm.py` | `src/tron_ice/normalization/evm.py` | yes |
| bsc | `src/tron_ice/collection/evm.py` | `src/tron_ice/normalization/evm.py` | yes |
| polygon | `src/tron_ice/collection/evm.py` | `src/tron_ice/normalization/evm.py` | yes |
| tron | `src/tron_ice/collection/tron.py` | `src/tron_ice/normalization/tron.py` | yes |
| solana | `src/tron_ice/collection/solana.py` | `src/tron_ice/normalization/solana.py` | optional |
| bitcoin | skipped | skipped | no |
| liquid | skipped | skipped | no |

Bitcoin and Liquid are intentionally skipped for strict D-W seed labels because
the current model assumes account-style deposits/withdrawals. They should be
handled by a separate UTXO/confidential-transaction module or manual review.

Solana requires one or more valid Solana public keys in:

```env
SIDESHIFT_HOT_WALLETS_SOLANA=wallet1,wallet2
```

If the value is not a 32-byte base58 Solana public key, the collector stops that
chain with a clear validation error.

## Main Commands

Collect the research window:

```bash
python -m src.tron_ice.cli collect-onchain --service sideshift --year 2026 \
  --chains ethereum solana liquid bitcoin bsc polygon tron \
  --start-date 2026-05-22 --end-date 2026-06-28
```

Normalize account-style chains:

```bash
python -m src.tron_ice.cli normalize-onchain --service sideshift --year 2026 \
  --chains ethereum solana bsc polygon tron
```

Run leakage-safe semi-supervised labels:

```bash
python -m src.tron_ice.cli semi-supervised --service sideshift --year 2026 \
  --start-date 2026-05-22 --split-date 2026-06-11 --end-date 2026-06-28
```
