# TRON-ICE: Sơ đồ hệ thống và kiến trúc

## 1. Sơ đồ Kiến trúc Tổng thể

```mermaid
graph TB
    subgraph "💾 Dữ liệu Gốc"
        TronGrid["TronGrid API<br/>(TRON Blockchain)"]
        OffChain["Off-Chain Services<br/>ChangeNow, SideShift, FixedFloat"]
        PriceAPI["CoinGecko API<br/>(Lịch sử giá)"]
    end

    subgraph "🔄 Pipeline Xử lý"
        Scraper["Data Collection<br/>scraper_trongrid.py"]
        Normalizer["Transaction Normalizer<br/>Định nghĩa schema chuẩn"]
        Classifier["Transaction Classifier<br/>Phân loại: Deposit/Withdrawal"]
        Pricer["Price Calculator<br/>Tính giá trị USD"]
    end

    subgraph "🎯 Matching Engines"
        Baseline["Baseline Matcher<br/>(Greedy 1-1)<br/>Time Window + Value Threshold"]
        CandidateGen["Candidate Generator<br/>Lọc cặp khả thi"]
        FeatureEng["Feature Engineering<br/>Trích xuất đặc trưng"]
        XGBoost["XGBoost Classifier<br/>ML-based Prediction"]
    end

    subgraph "📊 Ground Truth Pipeline"
        GTExtract["Extract Labels<br/>Từ On-Chain Traces"]
        GTBuilder["Build Training Pairs<br/>Weak + Strict Labels"]
        GTExport["Export for Training<br/>JSONL Format"]
    end

    subgraph "📈 Output & Evaluation"
        Matched["Matched Pairs CSV/JSON<br/>Final Results"]
        Evaluation["Performance Metrics<br/>Precision, Recall, F1"]
    end

    TronGrid --> Scraper
    OffChain --> Classifier
    PriceAPI --> Pricer
    Scraper --> Normalizer
    Normalizer --> Classifier
    Classifier --> Pricer
    Pricer --> CandidateGen

    CandidateGen --> Baseline
    Baseline --> Matched

    CandidateGen --> FeatureEng
    FeatureEng --> XGBoost
    XGBoost --> Matched

    TronGrid --> GTExtract
    GTExtract --> GTBuilder
    GTBuilder --> GTExport
    GTExport --> XGBoost

    Matched --> Evaluation
    Evaluation -.-> Baseline
    Evaluation -.-> XGBoost

    classDef dataSource fill:#e1f5ff,stroke:#01579b,stroke-width:2px
    classDef processing fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef matching fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef groundtruth fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px
    classDef output fill:#fce4ec,stroke:#880e4f,stroke-width:2px

    class TronGrid,OffChain,PriceAPI dataSource
    class Scraper,Normalizer,Classifier,Pricer processing
    class Baseline,CandidateGen,FeatureEng,XGBoost matching
    class GTExtract,GTBuilder,GTExport groundtruth
    class Matched,Evaluation output
```

---

## 2. Chi tiết Luồng Matching Baseline

```mermaid
graph TD
    A["📥 Deposits + Withdrawals<br/>(đã định giá USD)"]
    B["1️⃣ Nhóm theo Token<br/>Tách TRX, USDT, ..."]
    C["2️⃣ Sắp xếp theo Timestamp<br/>Deposits & Withdrawals"]
    D["3️⃣ Duyệt Deposits"]
    E["4️⃣ Tìm Withdrawals<br/>trong Time Window"]
    F["✅ Điều kiện Matching:<br/>- Thời gian: ΔT ≤ time_window<br/>- Giá trị: |V_dep - V_with| / V_dep ≤ value_threshold<br/>- Token: Cùng loại"]
    G["✅ Cặp khớp được tìm thấy"]
    H["❌ Loại cặp Deposit<br/>Không tìm được match"]
    I["🎯 Greedy 1-1 Matching<br/>Mỗi Deposit/Withdrawal<br/>chỉ khớp 1 lần"]
    J["📊 Paired Transactions<br/>+ Unmatched Transactions"]

    A --> B
    B --> C
    C --> D
    D --> E
    E --> F
    F -->|Match| G
    F -->|No Match| H
    G --> I
    H --> I
    I --> J

    classDef input fill:#e1f5ff,stroke:#01579b
    classDef process fill:#fff3e0,stroke:#e65100
    classDef condition fill:#fce4ec,stroke:#880e4f
    classDef output fill:#f3e5f5,stroke:#4a148c

    class A input
    class B,C,D,E process
    class F,G,H condition
    class I,J output
```

**Tham số chính:**
- `time_window` (default: 300s) - Cửa sổ thời gian tối đa giữa nạp-rút
- `value_threshold` (default: 0.05 = 5%) - Sai số giá trị tối đa
- `bucket_minutes` (default: 5) - Độ rộng bucket để mapping thời gian→giá

---

## 3. Chi tiết Pipeline XGBoost

```mermaid
graph LR
    subgraph "Phase 1: Chuẩn bị Dữ liệu"
        A["📥 Load Deposits<br/>+ Withdrawals<br/>(priced)"]
    end

    subgraph "Phase 2: Sinh Ứng viên"
        B["Candidate Generator<br/>generate_candidates<br/>- Time: ΔT ≤ 600s<br/>- Relative Value: ≤ 15%<br/>- Token: Same"]
        C["📊 Candidate Pool<br/>~100K - 1M pairs"]
    end

    subgraph "Phase 3: Trích Đặc trưng"
        D["Feature Engineering<br/>extract_features<br/>- Time diff<br/>- Value diff %<br/>- Price volatility<br/>- Frequency patterns"]
        E["🔢 Feature Matrix X<br/>Shape: N × D<br/>D ≈ 20-50 features"]
    end

    subgraph "Phase 4: Huấn luyện"
        F["📚 Ground Truth Labels<br/>y ∈ {0, 1}"]
        G["XGBoost Classifier<br/>- n_estimators: 100-500<br/>- max_depth: 4-8<br/>- learning_rate: 0.01-0.1"]
        H["🎓 Trained Model<br/>models/xgboost_*.pkl"]
    end

    subgraph "Phase 5: Dự đoán"
        I["Predict Probabilities<br/>predict_proba"]
        J["🎲 Prob. Scores<br/>p_match ∈ [0, 1]"]
    end

    subgraph "Phase 6: Ghép Cặp"
        K["Greedy Matcher<br/>- Sort by score ↓<br/>- 1-1 matching<br/>- Threshold: default 0.5"]
        L["✅ Final Matched Pairs"]
    end

    A --> B
    B --> C
    C --> D
    D --> E
    E --> G
    F --> G
    G --> H
    H --> I
    I --> J
    J --> K
    K --> L

    classDef phase1 fill:#e1f5ff,stroke:#01579b,stroke-width:2px
    classDef phase2 fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef phase3 fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef phase4 fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px
    classDef phase5 fill:#fce4ec,stroke:#880e4f,stroke-width:2px

    class A phase1
    class B,C phase2
    class D,E phase3
    class F,G,H phase4
    class I,J phase5
    class K,L phase1
```

---

## 4. Kiến trúc Liên chuỗi (Cross-Chain Tracing)

```mermaid
graph TB
    subgraph "TRON Network"
        TronICE["🔥 ICE Hot Wallets<br/>FixedFloat, ChangeNow,<br/>SideShift"]
        TronTx["TRON Tx Data<br/>(TRC-20 USDT, TRX)"]
    end

    subgraph "Off-Chain Layer"
        ChangeNowAPI["ChangeNow API Crawler<br/>→ Deposit Addresses<br/>→ Withdrawal Addresses"]
        SideShiftAPI["SideShift API Crawler<br/>→ Exchange History<br/>→ Deposit/Output Addrs"]
        FixedFloatAPI["FixedFloat Manual Tracking<br/>→ Known Deposit Addrs<br/>→ Output Traces"]
    end

    subgraph "Cross-Chain Tracing"
        TraceEngine["N-Hop Tracer<br/>--trace-depth 2<br/>TRON → EVM Chain<br/>(Bridged USDT)"]
        HistoryFilter["History Network Filter<br/>- tron-any: Any TRON hop<br/>- tron-both: Both sides on TRON<br/>- all: Include multichain"]
    end

    subgraph "Output Data"
        MultiChainGT["🌐 Multichain Ground Truth<br/>ground_truth_*_multichain.json"]
        CrossChainPairs["↔️ Cross-Chain Pairs<br/>TRON → Ethereum<br/>TRON → Polygon<br/>etc."]
    end

    TronICE --> TronTx
    TronTx --> TraceEngine
    ChangeNowAPI --> TraceEngine
    SideShiftAPI --> TraceEngine
    FixedFloatAPI --> TraceEngine

    TraceEngine --> HistoryFilter
    HistoryFilter --> MultiChainGT
    HistoryFilter --> CrossChainPairs

    classDef tron fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px
    classDef offchain fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef tracing fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef output fill:#fce4ec,stroke:#880e4f,stroke-width:2px

    class TronICE,TronTx tron
    class ChangeNowAPI,SideShiftAPI,FixedFloatAPI offchain
    class TraceEngine,HistoryFilter tracing
    class MultiChainGT,CrossChainPairs output
```

**Các chế độ Trace:**
- `trace-depth 0`: Không trace (chỉ TRON)
- `trace-depth 1`: Trace 1 hop (TRON → EVM)
- `trace-depth 2`: Trace 2 hops (TRON → EVM → EVM)

---

## 5. Luồng Dữ liệu Chi tiết (Data Flow)

```mermaid
graph LR
    subgraph "🔵 Input"
        Raw["Raw TronGrid Data<br/>(TRON blockchain)"]
    end

    subgraph "🟡 Processing"
        P1["Normalize<br/>schema"]
        P2["Classify<br/>Dep/Wit"]
        P3["Price USD<br/>conversion"]
    end

    subgraph "🟢 Matching Decision Tree"
        MBaseline{"Baseline<br/>Match<br/>available?"}
        MXG{"XGBoost<br/>Model<br/>trained?"}
    end

    subgraph "🔴 Output"
        Out1["baseline_matched_pairs.csv"]
        Out2["xgboost_matched_pairs.csv"]
    end

    Raw --> P1
    P1 --> P2
    P2 --> P3
    P3 --> MBaseline
    MBaseline -->|YES| Out1
    MBaseline -->|NO| MXG
    MXG -->|YES| Out2
    MXG -->|NO| Out1

    classDef input fill:#bbdefb,stroke:#1565c0,stroke-width:2px
    classDef proc fill:#fff9c4,stroke:#f57f17,stroke-width:2px
    classDef decision fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px
    classDef output fill:#ffccbc,stroke:#d84315,stroke-width:2px

    class Raw input
    class P1,P2,P3 proc
    class MBaseline,MXG decision
    class Out1,Out2 output
```

---

## 6. Bảng So sánh: Baseline vs XGBoost

| Tiêu chí | Baseline Matcher | XGBoost Matcher |
|---------|-----------------|-----------------|
| **Thuật toán** | Greedy 1-1 heuristic | ML-based classification |
| **Đặc trưng** | Time + Value + Token | 20-50 engineered features |
| **Huấn luyện** | Không cần training | Cần ground truth labels |
| **Tốc độ** | ⚡ Rất nhanh (ms) | 🐢 Chậm hơn (s) |
| **Độ chính xác** | 📊 ~70-80% | 📊 ~85-95% |
| **Tham số** | `time_window`, `value_threshold` | Hyperparameters XGBoost |
| **Sử dụng** | Nhanh chóng, PoC, baseline | Production, high-accuracy |
| **Lợi ích** | Đơn giản, không cần label | Cao hơn, linh hoạt hơn |
| **Hạn chế** | Cứng nhắc, kém linh hoạt | Cần dữ liệu training chất lượng |

---

## 7. Sơ đồ Chu kỳ Phát triển (Development Cycle)

```mermaid
graph TB
    Start["🚀 Bắt đầu:<br/>Service + Year"]
    Step1["1️⃣ Thu thập dữ liệu<br/>scraper_trongrid.py"]
    Step2["2️⃣ Chuẩn hóa + Phân loại<br/>normalizer + classifier"]
    Step3["3️⃣ Định giá USD<br/>price_calculator.py"]
    Step4["4️⃣ Sinh Ground Truth<br/>run_ground_truth.py"]
    Step5["5️⃣ Xây dựng Training Pairs<br/>build_weak_training_pairs.py"]
    Step6["6️⃣ Huấn luyện XGBoost<br/>train_xgboost.py"]
    Step7["7️⃣ Dự đoán + Ghép cặp<br/>predict_xgboost.py"]
    Step8["8️⃣ Đánh giá kết quả<br/>Metrics: Precision, Recall"]
    Decision{"Độ chính xác<br/>đạt yêu cầu?"}
    Tuning["🔧 Điều chỉnh:<br/>- Hyperparameters<br/>- Feature engineering<br/>- Training data"]
    End["✅ Hoàn thành<br/>Matched pairs output"]

    Start --> Step1
    Step1 --> Step2
    Step2 --> Step3
    Step3 --> Step4
    Step4 --> Step5
    Step5 --> Step6
    Step6 --> Step7
    Step7 --> Step8
    Step8 --> Decision
    Decision -->|Không| Tuning
    Tuning --> Step5
    Decision -->|Có| End

    classDef step fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
    classDef decision fill:#fff9c4,stroke:#f57f17,stroke-width:2px
    classDef end fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px

    class Step1,Step2,Step3,Step4,Step5,Step6,Step7,Step8 step
    class Decision decision
    class Start,End end
```

---

## 8. Cấu trúc Dữ liệu CSV/JSON

### Deposit/Withdrawal CSV
```csv
tx_hash,from_address,to_address,token,amount,timestamp,block_number,transaction_fee,usd_value
0x123...,TCN7x...,TJLL...,USDT,1000.00,2024-01-15 10:30:45,50000000,1.0,1000.00
```

### Matched Pairs JSON
```json
{
  "deposit_tx": {
    "tx_hash": "0xabc...",
    "timestamp": "2024-01-15 10:30:45",
    "amount": 1000.00,
    "usd_value": 1000.00
  },
  "withdrawal_tx": {
    "tx_hash": "0xdef...",
    "timestamp": "2024-01-15 10:35:12",
    "amount": 999.50,
    "usd_value": 999.50
  },
  "time_diff": 267,
  "value_diff_pct": 0.05,
  "match_method": "baseline",
  "confidence_score": 0.92
}
```

### Ground Truth JSONL
```json
{"dep_tx": "0xabc...", "wit_tx": "0xdef...", "label": 1, "weight": 1.0}
{"dep_tx": "0x123...", "wit_tx": "0x456...", "label": 0, "weight": 0.5}
```

---

## 9. Lệnh Chạy Hệ thống

```bash
# 1. Thu thập dữ liệu cho một ICE service
python main.py --service fixedfloat --year 2025 --mode data_collection

# 2. Chạy baseline matching
python main.py --service fixedfloat --year 2025 --mode baseline_algorithm

# 3. Tạo ground truth và huấn luyện XGBoost
python ground-truth/run_full_pipeline.py --service sideshift --year 2026 --trace-depth 2

# 4. Dự đoán XGBoost trên dữ liệu mới
python ground-truth/predict_xgboost.py --service fixedfloat --year 2025

# 5. Chạy toàn bộ pipeline
python main.py --service changenow --year 2025 --mode full \
  --time_window 300 --value_threshold 0.05
```

---

## 10. Tóm tắt Kiến trúc

- **Matching Engines:** 2 phương pháp (Baseline heuristic + XGBoost ML)
- **Data Flow:** TronGrid → Normalize → Classify → Price → Match → Output
- **Cross-Chain Support:** Optional N-hop tracing (TRON ↔ EVM chains)
- **Training Pipeline:** Ground truth generation → XGBoost training → Inference
- **Services Supported:** FixedFloat, ChangeNow, SideShift
