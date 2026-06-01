# ICE ground-truth pipeline

Liên kết **off-chain user request** (SideShift, FixedFloat, ChangeNOW…) với **on-chain deposit D** và **settlement W**, hỗ trợ **trace TRON n-hop** (`UserA -> ... -> hot-wallet -> ... -> UserB`).

## Cấu trúc

```
src/off-chain/
  registry.py              # service -> JSONL path
  schemas.py               # HistoryRecord schema
  SideShift_crawler/       # crawl user requests

ground-truth/
  run_ground_truth.py      # H <-> D <-> W
  run_full_pipeline.py     # ground-truth + train .pkl
  train_xgboost.py         # train từ training_pairs.jsonl
  predict_xgboost.py       # predict bằng .pkl
  output/                  # JSONL + training_pairs
  result/                  # JSON kết quả
  log/
  models/                  # xgboost_{service}_{year}.pkl
```

## Luồng chạy nhanh

### 1. Off-chain (user request)

SideShift:

```bash
python src/off-chain/SideShift_crawler/__main__.py
```

ChangeNOW (điền `CHANGENOW_API_KEY` **public** trong `.env`, không có khoảng trắng sau `=`):

```bash
python src/off-chain/ChangeNOW_crawler/__main__.py --check
python src/off-chain/ChangeNOW_crawler/__main__.py
```

**Lưu ý:** ChangeNOW hiện có thể từ chối `GET /v1/transactions/{api_key}` với public key (`401` — *Use private key for this endpoint*). Private key chỉ dùng cho `v2/exchanges`, không dùng được cho crawler list. Nếu `--check` fail, dùng on-chain hot-wallet (`changenow`) hoặc liên hệ `api@changenow.io`.

### 2. On-chain (hot-wallet)

```bash
python main.py --mode data_collection --service fixedfloat --year 2025
python main.py --mode transaction_normalizer --service fixedfloat --year 2025
```

### 3. Ground-truth (khuyến nghị: lọc on-chain theo thời gian off-chain)

```bash
python main.py --mode ground_truth --service sideshift --year 2025 --export-training
```

Hoặc:

```bash
python ground-truth/run_ground_truth.py --service sideshift --year 2025 --export-training
```

Trace n-hop (gọi TronGrid, chậm hơn):

```bash
python ground-truth/run_ground_truth.py --service fixedfloat --year 2025 --trace-depth 3 --export-training
```

### 4. Full pipeline (ground-truth + train .pkl)

```bash
python ground-truth/run_full_pipeline.py --service sideshift --year 2025 --trace-depth 0
```

### 5. Train / predict

```bash
python ground-truth/train_xgboost.py --service sideshift --year 2025
python ground-truth/predict_xgboost.py --service sideshift --year 2025
```

## Output schema (result)

| Field | Mô tả |
|-------|--------|
| `service` | sideshift / fixedfloat / changenow |
| `history` | Off-chain request H |
| `deposit`, `settlement` | Tx quanh hot-wallet |
| `deposit_path[]` | Trace ngược về user (n-hop) |
| `settlement_path[]` | Trace ra user (n-hop) |
| `deposit_trace`, `settlement_trace` | Hop gần user nhất |
| `match_score`, `label` | 1 nếu match đủ D+W |

## Tối ưu hiệu năng

- Mặc định **lọc on-chain** theo khoảng thời gian của file off-chain (dùng `ijson` stream, không load 650k tx).
- Matcher dùng **bisect** theo token + timestamp.
- `--no-filter-onchain`: load full file (chậm).

## Giới hạn

- SideShift public API không có `depositAddress` — trace on-chain là heuristic.
- Trace hiện chỉ TRON (TronGrid).
