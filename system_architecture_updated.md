# Kiến trúc hệ thống TRON-ICE hiện tại

Dưới đây là sơ đồ Mermaid thể hiện cấu trúc pipeline sau khi đã chỉnh sửa, phù hợp với code hiện tại trong repository.

```mermaid
flowchart TB
    subgraph "💾 Data Sources"
        A1[TronGrid API<br/>(TRON blockchain)]
        A2[Off-chain ICE Services<br/>FixedFloat, ChangeNOW, SideShift]
        A3[Price History API<br/>(CoinGecko / cache)]
    end

    subgraph "🔄 Preprocessing & Normalization"
        B1[Data Collection<br/>`src/tron_ice/collection` / legacy collectors]
        B2[Transaction Normalizer<br/>`src/transaction_normalizer`]
        B3[Transaction Classifier<br/>Deposit / Withdrawal labels]
        B4[USD Pricing<br/>`src/baseline_algorithm/price_calculator.py`]
    end

    subgraph "🎯 Matching Engines"
        C1[Baseline Matcher<br/>`src/baseline_algorithm/matcher.py`]
        C2[Candidate Generator<br/>`src/xgboost/candidate_generator.py`]
        C3[Feature Engineering<br/>`src/xgboost/feature_engineering.py`]
        C4[XGBoost Prediction<br/>`ground-truth/predict_xgboost.py`]
    end

    subgraph "📚 Ground Truth & Training"
        D1[Ground Truth Construction<br/>`ground-truth/run_ground_truth.py`]
        D2[Weak/Strict Label Builder<br/>`ground-truth/build_weak_training_pairs.py`]
        D3[XGBoost Training<br/>`ground-truth/train_xgboost.py`]
    end

    subgraph "📄 Outputs"
        E1[Matched Pairs CSV<br/>`data/matched/matched_pairs_{service}_{year}.csv`]
        E2[Ground Truth / Training JSONL<br/>`ground-truth/output/*.jsonl`]
        E3[Evaluation Metrics<br/>Precision / Recall / F1]
    end

    A1 --> B1
    A2 --> B1
    A3 --> B4

    B1 --> B2
    B2 --> B3
    B3 --> B4
    B4 --> C1
    B4 --> C2

    C1 --> E1
    C2 --> C3
    C3 --> C4
    C4 --> E1

    D1 --> D2
    D2 --> D3
    D3 --> C4
    D2 --> E2

    E1 --> E3
    E2 --> E3

    classDef source fill:#e1f5ff,stroke:#0288d1,stroke-width:2px
    classDef preprocess fill:#fff3e0,stroke:#ef6c00,stroke-width:2px
    classDef matching fill:#f3e5f5,stroke:#6a1b9a,stroke-width:2px
    classDef groundtruth fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    classDef output fill:#fce4ec,stroke:#c2185b,stroke-width:2px

    class A1,A2,A3 source
    class B1,B2,B3,B4 preprocess
    class C1,C2,C3,C4 matching
    class D1,D2,D3 groundtruth
    class E1,E2,E3 output
```

## Ghi chú quan trọng
- Baseline matcher hiện tuân thủ yêu cầu: `withdrawal` phải xảy ra sau `deposit`.
- Baseline ưu tiên `address reuse` và tiebreak bằng tổng sai lệch giá-trị và thời gian.
- XGBoost hiện là một phần của ground truth pipeline, được huấn luyện từ dữ liệu gán nhãn và dự đoán qua `ground-truth/predict_xgboost.py`.
- File input matcher dùng các file `data/classified/deposits_trongrid_{service}_{year}*.csv` và `data/classified/withdrawals_trongrid_{service}_{year}*.csv`.
- Output matching được lưu vào `data/matched/matched_pairs_{service}_{year}.csv`.
