# SideShift Temporal Semi-Supervised Experiment

Use only SideShift off-chain history for the crawl window `2026-05-22` through
`2026-06-28`. The matching scripts for other ICE services are kept for
reference, but they are not part of this experiment.

Run:

```bash
python ground-truth/semisupervised_sideshift.py \
  --start-date 2026-05-22 \
  --end-date 2026-06-28 \
  --eval-negative-ratio 1000
```

Scope:

- This experiment is TRON-anchored: a usable SideShift record must expose a
  TRON deposit side, a TRON withdrawal/settlement side, or both. Non-TRON-only
  records are excluded from the semi-supervised training and holdout metrics.
- Full `D-W` seed labels are created only when both sides are observable in the
  configured on-chain data.
- Bitcoin/Liquid-related requests are treated as structurally different
  one-sided evidence unless the non-TRON side has comparable classified data.
  They should not be interpreted with the same account-style TRON/EVM matching
  assumptions.

What this changes compared with the old random-split training:

- filters off-chain SideShift and on-chain candidate pairs to TRON-related
  records in the same date window;
- splits train/test by off-chain UTC days, not by random rows;
- uses strict rule matches only as seed labels, not as final ground truth;
- self-trains by adding pairs with probability `>=0.99` as pseudo-positive and
  `<=0.01` as pseudo-negative;
- evaluates on a temporal holdout with a realistic negative ratio and reports
  PR-AUC;
- exports high-confidence test pairs missed by the baseline rule for manual
  review.

Important limitation: if a SideShift request is cross-chain, for example
`bitcoin -> tron` or `liquid -> tron`, the TRON crawl can observe the TRON side
but not necessarily the Bitcoin/Liquid side. Such rows cannot become full `D-W`
seed positives unless both sides are observable in the current on-chain data.
Treat exported `baseline_misses` as candidates for manual validation, not as
automatic true positives.
