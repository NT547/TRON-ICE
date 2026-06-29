---
name: TRON-ICE Instructions
description: "Use when: working on TRON-ICE blockchain forensics project. Covers transaction analysis, matching algorithms, ML pipelines for cryptocurrency flow detection."
applyTo: ["**/TRON-ICE/**"]
---

# TRON-ICE Development Instructions

## Project Overview

TRON-ICE is a blockchain forensics system that detects and matches deposit/withdrawal transaction pairs on the TRON network to trace flows through Instant Cryptocurrency Exchange (ICE) services (FixedFloat, ChangeNow, SideShift). The system combines baseline heuristic algorithms with XGBoost ML predictions for transaction pair matching.

**Key Technologies**: Python, pandas, XGBoost, TronGrid API, scikit-learn

## Code Organization & Structure

### Core Directories

```
src/
├── data_collection/        # TronGrid API scrapers for raw blockchain data
├── baseline_algorithm/     # Greedy matching (time-window + value-threshold heuristics)
├── transaction_classifier/ # Identify deposits/withdrawals per ICE service
├── transaction_normalizer/ # Standardize raw tx data schema
├── xgboost/               # ML pipeline: feature engineering, training, prediction
├── off-chain/             # ICE service data crawlers (SideShift, ChangeNow)
├── preprocessing/         # Data validation, cleaning utilities
└── utils/                 # Helpers, config management, price caching

ground-truth/             # Parallel pipeline: labeled training data → model training
notebooks/                # Ad-hoc analysis & experimentation
data/
├── raw/                   # Original blockchain data from TronGrid
├── processed/             # Normalized transaction data
├── classified/            # Deposit/withdrawal classified CSVs
├── matched/               # Transaction pair matching results
└── ground_truth/          # Labeled training pairs for supervised learning

cache/                     # Price history JSON cache (historical rates)
```

### Key Entry Points

- **main.py**: CLI with modes: `full_pipeline`, `data_collection`, `transaction_normalizer`, `baseline_algorithm`, `ground_truth`, `xgboost`
- **ground-truth/run_full_pipeline.py**: End-to-end ground truth generation
- **ground-truth/predict_xgboost.py**: Run inference on new transaction data

## Coding Standards & Best Practices

### Python Style & Conventions

1. **Code Style**:
   - Follow PEP 8 (4-space indentation, snake_case for functions/variables)
   - Use type hints for function parameters and returns (Python 3.7+)
   - Keep functions focused: single responsibility, max 50 lines preferred
   - Add docstrings for all public functions/classes (Google style)

2. **Naming Conventions**:
   - Transaction data: `tx` (abbreviation) or `transaction` (full form in class/module names)
   - Exchange services: `exchange`, `service`, or abbreviation (`fixedfloat`, `changenow`, `sideshift`)
   - Dataset collections: plural `deposits`, `withdrawals`
   - Configuration: `config`, `params`, `settings`
   - File prefixes match content: `deposits_*`, `withdrawals_*`, `matched_pairs_*`

3. **Imports**:
   - Standard library first, then third-party (pandas, numpy), then local modules
   - Use explicit imports; avoid `import *`
   - Group imports: stdlib → third-party → local, separated by blank lines

### Data Handling

1. **CSV/JSON Files**:
   - Store transaction data in CSV with clear column headers (lowercase, snake_case)
   - Use JSONL (JSON Lines) for labeled training data; one JSON object per line
   - Always validate schema after loading (check required columns, data types)
   - Cache price history as JSON in `cache/` to avoid repeated API calls

2. **Data Normalization**:
   - TRX amounts always in "sun" (smallest unit); convert to TRX with `/1e6` for display
   - Timestamps always UTC, ISO 8601 format `YYYY-MM-DD HH:MM:SS`
   - Addresses: lowercase, validate TRON address format
   - USD prices rounded to 2 decimals; store as float

3. **Error Handling**:
   - Validate API responses before processing (check HTTP status, JSON structure)
   - Log malformed records to `data/logs/` instead of crashing
   - Use pandas `.dropna()` or `.fillna()` explicitly; avoid silent NaN propagation
   - Test with sample CSVs in `data/samples/` before full pipeline runs

### Logging & Debugging

1. **Logging**:
   - Use Python's `logging` module, not `print()`
   - Log at appropriate levels: DEBUG (detailed flow), INFO (milestones), WARNING (non-blocking issues), ERROR (failures)
   - Save logs to `data/logs/` or `result/logs/` with timestamp in filename

2. **Debugging**:
   - Use Jupyter notebooks in `notebooks/` for exploratory debugging
   - Profile data: row counts, column nullity, value distributions before/after each step
   - For ML: log feature statistics, model metrics (precision, recall, F1) per fold/epoch

## Development Workflow

### Git & Branching

- Main branch: `main` (production-ready code)
- Feature branches: `feature/descriptive-name` (e.g., `feature/xgboost-pipeline`, `feature/sideshift-classifier`)
- Bugfix branches: `bugfix/issue-description`
- Commit messages: `[component] Description` (e.g., `[xgboost] Add cross-validation for hyperparameter tuning`)

### Testing & Validation

1. **Unit Testing**:
   - Test data transformations with small sample CSVs in `data/samples/`
   - Validate transaction normalization for each ICE service separately
   - Check matching algorithm against ground truth labels

2. **Pipeline Validation**:
   - Run full pipeline with `--sample` flag on small datasets first
   - Compare baseline vs XGBoost predictions on same test set
   - Generate sample outputs (first 100 rows) in `result/` for manual inspection

3. **Data Quality Checks**:
   - Row counts consistency across pipeline stages (shouldn't lose rows unexpectedly)
   - No missing critical columns (transaction hash, timestamp, from/to address, amount)
   - Price data completeness (detect gaps in price history cache)

### Running the Pipeline

```bash
# Activate virtual environment
source .venv/bin/activate

# Full pipeline: data collection → normalization → classification → matching
python main.py --mode full_pipeline --year 2024 --exchange fixedfloat

# Individual components
python main.py --mode data_collection --year 2024
python main.py --mode transaction_normalizer --year 2024
python main.py --mode baseline_algorithm --year 2024 --time-window 7200

# Ground truth & XGBoost
cd ground-truth
python run_full_pipeline.py --year 2024
python train_xgboost.py --model-name v1 --year 2024
python predict_xgboost.py --model-path models/v1.pkl --year 2024
```

### Dependencies & Environment

- Python 3.8+, use virtual environment (`.venv/`)
- Install dependencies: `pip install -r requirements.txt`
- API keys (TronGrid, CoinGecko) in `.env` file (not committed to git)
- Cache updates: price history cached locally; manually refresh if stale (`data_collection/price_fetcher.py`)

## Common Tasks & Patterns

### Adding a New Exchange Service

1. Create classifier in `src/transaction_classifier/` following existing pattern (fixedfloat, changenow)
2. Define deposit/withdrawal address patterns for that exchange
3. Add test data in `data/classified/deposits_trongrid_[exchange]_samples.csv`
4. Update `main.py` and ground-truth pipeline to include new service

### Debugging Low Matching Accuracy

1. Check baseline algorithm parameters:
   - `--time-window`: Adjust if many legit pairs fall outside window
   - `--value-threshold`: Too strict threshold misses real pairs; too loose creates noise

2. Feature engineering for XGBoost:
   - Review feature importance in model artifacts
   - Check if features contain sufficient signal (not correlated with label by chance)
   - Validate on ground truth samples first

3. Data quality:
   - Verify price history cache is complete for date range
   - Check classified deposits/withdrawals counts per exchange (compare to manual spot checks)

### Performance Optimization

- Use `joblib` for parallel processing when available (data loading, feature extraction)
- Cache computed features in JSONL if reused across multiple runs
- Profile with `cProfile` for hotspots in matching algorithm
- Consider downsampling candidates for XGBoost if dataset > 1M pairs

## File Naming & Output Conventions

- Input CSV: `{deposits|withdrawals}_trongrid_{exchange}_{year}{_samples}.csv`
- Classified CSV: `{deposits|withdrawals}_trongrid_{exchange}_{year}_{classified|raw}.csv`
- Matched output: `matched_pairs_{exchange}_{year}.csv`
- Ground truth: `ground_truth_{exchange}_{year}.jsonl`
- Model artifact: `{model_name}_{version}.pkl` or `.joblib`
- Logs: `{timestamp}_{process_name}.log`

## Important Notes

- **Privacy**: Malicious wallet addresses in `data/raw/malicious_wallets.json`; use with caution in publications
- **Academic Usage**: Results are for research validation; include disclaimers in papers
- **API Rate Limits**: TronGrid has rate limits; implement exponential backoff in `data_collection/`
- **Price Data**: Use Binance SPOT market for USDT/TRX pairs; handle missing data gracefully
- **Version Control**: Don't commit large CSV/model files; use DVC or store in `data/` (`.gitignore` configured)

---

**Last Updated**: 2025  
**Contact**: Project team documentation
