# TRON-ICE

TRON-ICE is a research-oriented framework for tracing deposit-withdrawal relationships associated with Instant Cryptocurrency Exchanges (ICEs) on the Tron blockchain. It is designed for blockchain forensics, AML-oriented analysis, and transaction matching experiments where the real counterparties are not directly visible on-chain.

The repository combines several components:

- on-chain data collection from Tron hot wallets,
- transaction classification into deposits and withdrawals,
- normalization and feature engineering,
- weakly supervised label construction,
- XGBoost-based scoring,
- matching and evaluation pipelines.

## 1. What this project does

The goal of TRON-ICE is to link suspicious on-chain deposits and withdrawals that are routed through ICE services. Instead of relying only on rigid threshold rules such as a fixed time window or value tolerance, the system uses a structured pipeline that learns matching behavior from weak supervision and then produces candidate links for forensic review.

In practice, the workflow is:

1. identify service hot wallets,
2. collect associated Tron transactions,
3. classify them as deposits or withdrawals,
4. build candidate transaction pairs,
5. score each pair with features such as time difference, value deviation, token consistency, and address reuse,
6. output matched pairs for analysis.

## 2. System overview

The overall workflow consists of the following stages:

- Data collection: gather raw Tron transactions and TRC-20 transfers related to selected ICE services.
- Transaction normalization/classification: convert raw records into structured deposit and withdrawal operations.
- Candidate generation: construct plausible deposit-withdrawal pairs under temporal and value constraints.
- Feature engineering: build features used to distinguish true matches from background noise.
- Label construction: create weak labels from strict seeds and high-confidence pseudo-labels.
- Model scoring: train and apply an XGBoost classifier to estimate match probability.
- Matching: select one-to-one links and save outputs for downstream analysis.

## 3. Repository structure

- [main.py](main.py): main entry point for running the pipeline.
- [src](src): implementation of collection, normalization, matching, and utilities.
- [ground-truth](ground-truth): scripts for off-chain/on-chain labeling, training, prediction, and evaluation.
- [data](data): raw, processed, classified, and matched transaction files.
- [cache](cache): cached price data and intermediate artifacts.
- [results](results): logs, model outputs, and experiment results.
- [paper.tex](paper.tex): the LaTeX source for the research paper.

## 4. Environment setup

This project is implemented in Python. The required dependencies are listed in [requirements.txt](requirements.txt).

Install them with:

```bash
pip install -r requirements.txt
```

It is recommended to use a Python 3.10+ environment.

## 5. Data requirements

The pipeline expects transaction data for selected services such as:

- ChangeNOW
- FixedFloat
- SideShift

The project uses:

- TronGrid-style transaction data,
- TRC-20 transfers,
- hot-wallet activity for the target ICE service,
- price data for value normalization.

If the dataset is not already present, the first step is to collect it from Tron-related sources.

## 6. Running the pipeline

### 6.1 Collect raw transaction data

```bash
python main.py --service sideshift --year 2025 --mode data_collection
```

This stage collects transactions related to the configured hot wallets for the chosen service and year.

### 6.2 Classify transactions into deposits and withdrawals

```bash
python main.py --service sideshift --year 2025 --mode transaction_classifier
```

This step produces classified deposit and withdrawal files under the data/classified folder.

### 6.3 Build ground-truth labels and training data

```bash
python main.py --service sideshift --year 2025 --mode ground_truth
```

This stage builds weakly supervised labels by combining strict seeds with pseudo-labels and prepares data for later model training.

### 6.4 Run the full matching workflow

The repository also contains dedicated scripts under [ground-truth](ground-truth) for more advanced ground-truth and model-training steps.

Example:

```bash
python ground-truth/run_ground_truth.py --service sideshift --year 2025 --export-training
```

and for training the model:

```bash
python ground-truth/train_xgboost.py --service sideshift --year 2025
```

## 7. Output files

The pipeline generates several output categories:

- raw data in [data/raw](data/raw)
- processed transaction files in [data/processed](data/processed)
- classified deposits/withdrawals in [data/classified](data/classified)
- matched pairs in [data/matched](data/matched)
- logs and evaluation artifacts in [results](results)
- trained model artifacts in [ground-truth/models](ground-truth/models)

Depending on the run mode, outputs may include:

- CSV files of classified deposits and withdrawals,
- matched-pair results,
- training pairs for model fitting,
- evaluation logs and summaries.

## 8. Main design ideas

The system is built around the idea that ICE matching is not just a simple one-rule problem. The matching process uses a combination of:

- temporal proximity,
- value similarity,
- token consistency,
- address reuse signals,
- learned decision boundaries from weak supervision.

This makes the approach more suitable for real-world transaction tracing than fixed heuristics alone.

## 9. Notes and limitations

This repository is intended for research and forensic analysis. It is not a production-grade AML monitoring platform, and it should be used as a reproducible experimental framework rather than a fully automated investigative system.

Some limitations are inherent to the setting:

- on-chain evidence may be incomplete,
- labeling depends on weak or heuristic supervision,
- hot-wallet behavior can vary across services and periods,
- the system may miss highly obfuscated or long-delay flows.

## 10. Citation and usage context

The project is tied to the associated research paper in [paper.tex](paper.tex). It is intended to support experiments on Tron-based ICE transaction matching and to provide reproducible artifacts for academic review.
