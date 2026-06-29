# Clean Pipeline Refactor Map

This project is being migrated from script-oriented research code into explicit pipeline stages:

```text
Data Collection
-> Normalization
-> Ground Truth Construction
-> Candidate Generation
-> Feature Engineering
-> Model Training
-> Prediction
-> Evaluation
```

## Stage Ownership

| Stage | New package | Legacy fallback kept for comparison |
|---|---|---|
| Data Collection | `src/tron_ice/collection` | `src/data_collection`, `src/off-chain` |
| Normalization | `src/tron_ice/normalization` | `src/transaction_normalizer` |
| Ground Truth | `src/tron_ice/ground_truth` | `ground-truth/src_ground_truth` |
| Candidate Generation | `src/tron_ice/candidates` | `src/xgboost/candidate_generator.py` |
| Feature Engineering | `src/tron_ice/features` | `src/xgboost/feature_engineering.py` |
| Training | `src/tron_ice/training` | `ground-truth/train_xgboost.py` now imports new feature/pricing modules |
| Prediction | `src/tron_ice/prediction` | `ground-truth/predict_xgboost.py` now imports new candidate/feature/prediction modules |
| Evaluation | `src/tron_ice/evaluation` | `ground-truth/evaluate_baseline_vs_xgboost.py` now imports new feature modules |

`src/tron_ice` now contains copied core modules, not only wrappers. Legacy modules are intentionally left in place so outputs can be compared before deletion.

## Current File Decisions

### Keep And Move Gradually

- `src/data_collection/scraper_trongrid.py`
- `src/data_collection/scaper_multithreaded.py`
- `src/data_collection/fetch_time_chunk.py`
- `src/data_collection/evm_collector.py`
- `src/transaction_normalizer/*.py`
- `src/off-chain/registry.py`
- `src/off-chain/schemas.py`
- `src/off-chain/SideShift_crawler/*.py`
- `src/off-chain/ChangeNOW_crawler/*.py`
- `ground-truth/src_ground_truth/*.py`
- `ground-truth/run_ground_truth.py`
- `ground-truth/run_multichain_ground_truth.py`
- `ground-truth/train_xgboost.py`
- `ground-truth/predict_xgboost.py`
- `ground-truth/evaluate_baseline_vs_xgboost.py`
- `src/xgboost/candidate_generator.py`
- `src/xgboost/feature_engineering.py`
- `src/xgboost/matcher.py`
- `src/xgboost/predictor.py`

### Legacy Candidates

- `src/data_collection/v1/*`
- `src/heuristic/*`
- `src/preprocessing/*`
- `src/processing/parser.py`
- `src/xgboost/labeling.py`
- `src/xgboost/pipeline.py`
- `test.py`
- `src/data_collection/rates_scraper.py`

Do not delete these until smoke tests for the new package and archived outputs pass.

## Known Risks To Remove

- `sys.path` mutation caused by `ground-truth` and `src/off-chain`.
- Mixed schemas: `txid` vs `tx_hash`, `amount` vs `value`, `network` vs `chain`.
- Random negative sampling can leak distribution-specific information into holdout evaluation.
- Side effects inside processing functions: data loading, transformation, logging, and file writing are often coupled.
- Historical price code previously referenced `COINGECKO_API_KEY` without defining it.

## Migration Order

1. Keep old commands working while adding wrappers under `src/tron_ice`.
2. Standardize canonical schemas in `src/tron_ice/normalization/schemas.py`.
3. Move stage internals behind package imports, one stage at a time.
4. Replace hardcoded paths with `src/tron_ice/io/paths.py`.
5. Merge TRON and multichain ground-truth runners behind one API.
6. Replace demo XGBoost pipeline with training/prediction scripts backed by real labels.
7. Archive legacy CSV and v1 collectors after parity checks.

## New Compatibility CLI

The new stage-oriented CLI is available without removing the legacy `main.py`:

```bash
python -m src.tron_ice.cli collect --service sideshift --year 2026
python -m src.tron_ice.cli normalize --service sideshift --year 2026
python -m src.tron_ice.cli ground-truth --service sideshift --year 2026 --export-training
python -m src.tron_ice.cli train --service sideshift --year 2026
python -m src.tron_ice.cli predict --service sideshift --year 2026
```
