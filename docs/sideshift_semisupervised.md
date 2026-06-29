# SideShift Semi-Supervised Ground Truth

This workflow treats SideShift off-chain records as the anchor and only uses
high-precision rule matches as seed labels.

## Date Split

- Crawl window: `2026-05-22` through `2026-06-28`.
- Train window: `2026-05-22` through `2026-06-10`.
- Test window: `2026-06-11` through `2026-06-28`.

The semi-supervised loop runs only on the train window. Test labels are strict
rule labels generated independently from the test window.

## Chain Policy

Collection priority for SideShift analysis:

1. `ethereum`
2. `solana`
3. `liquid`
4. `bitcoin`
5. `bsc`
6. `polygon`
7. `tron`

Default observable chains are `ethereum,bsc,polygon,tron`. Solana is supported
by the local JSON-RPC collector/normalizer once `SIDESHIFT_HOT_WALLETS_SOLANA`
is configured. `bitcoin` and `liquid` are intentionally not used for strict D-W
labels by default because they do not fit the account-style classifier used by
this pipeline.

## On-Chain Collection

```bash
python -m src.tron_ice.cli collect-onchain \
  --service sideshift \
  --year 2026 \
  --chains ethereum solana liquid bitcoin bsc polygon tron \
  --start-date 2026-05-22 \
  --end-date 2026-06-28
```

`bitcoin` and `liquid` are reported as skipped for strict labels. They can still
be investigated manually or with a future UTXO-specific module.

If `SIDESHIFT_HOT_WALLETS_SOLANA` is not configured, Solana is reported as an
error and the batch continues to the next chain. Broad block-range fallback is
disabled by default because it can run for a long time. Use
`--allow-wide-fallback` only when you explicitly want that slow scan.

Then normalize supported account-style chains:

```bash
python -m src.tron_ice.cli normalize-onchain \
  --service sideshift \
  --year 2026 \
  --chains ethereum solana bsc polygon tron
```

## Run

```bash
python -m src.tron_ice.cli semi-supervised \
  --service sideshift \
  --year 2026 \
  --start-date 2026-05-22 \
  --split-date 2026-06-11 \
  --end-date 2026-06-28
```

To include a newly supported chain:

```bash
python -m src.tron_ice.cli semi-supervised \
  --service sideshift \
  --observable-chains ethereum,solana,bsc,polygon,tron
```

Outputs:

- `ground-truth/output/training_pairs_sideshift_2026_temporal_semisupervised.jsonl`
- `ground-truth/output/holdout_pairs_sideshift_2026_temporal_semisupervised.jsonl`
- `ground-truth/result/sideshift_2026_temporal_semisupervised_metrics.json`
- `ground-truth/result/sideshift_2026_temporal_semisupervised_baseline_misses.json`
- `ground-truth/models/xgboost_sideshift_2026_temporal_semisupervised.pkl`

The `baseline_misses` file contains high-confidence model discoveries that the
strict baseline rule did not label. Review these before presenting them as true
positives.

## Cleanup

Generated artifacts are ignored by git. To inspect cleanup candidates:

```powershell
.\scripts\clean_artifacts.ps1
```

To delete generated artifact contents:

```powershell
.\scripts\clean_artifacts.ps1 -Apply
```
