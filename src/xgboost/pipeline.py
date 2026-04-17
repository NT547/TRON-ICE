# Module: pipeline.py
# Chức năng: Chạy toàn bộ pipeline XGBoost từ nạp dữ liệu, sinh cặp ứng viên, trích xuất đặc trưng, huấn luyện mô hình, dự đoán và ghép cặp cuối cùng.

import os
import numpy as np
from .data_loader import load_transactions
from .candidate_generator import generate_candidates
from .feature_engineering import extract_features
from .model_trainer import train_xgboost_classifier
from .predictor import predict_proba
from .matcher import greedy_matcher


def run_xgboost_pipeline(service, year, args):
    """
    Chạy toàn bộ pipeline XGBoost matching cho giao dịch blockchain.
    Tham số:
        - service: tên dịch vụ (ví dụ: fixedfloat)
        - year: năm dữ liệu
        - args: các tham số cấu hình pipeline
    Các bước thực hiện:
        1. Nạp dữ liệu giao dịch nạp (deposit) và rút (withdrawal) đã được định giá (usd_value)
        2. Sinh các cặp ứng viên (candidate pairs) thỏa mãn điều kiện thời gian, giá trị, token
        3. Trích xuất đặc trưng (feature engineering) cho từng cặp ứng viên
        4. (Demo) Sinh nhãn giả (toàn 0), thực tế cần thay bằng ground truth để huấn luyện thật
        5. Huấn luyện mô hình (hoặc load model), ở đây demo dùng XGBoost với nhãn giả
        6. Dự đoán xác suất match cho từng cặp ứng viên
        7. Ghép cặp cuối cùng bằng thuật toán greedy one-to-one và lưu kết quả ra file
    """

    # 1. Nạp dữ liệu giao dịch nạp và rút đã được định giá (usd_value)
    depo_file = f"data/priced/deposit_trongrid_{service}_{year}.json"  # File chứa các giao dịch nạp đã pricing
    with_file = f"data/priced/withdrawal_trongrid_{service}_{year}.json"  # File chứa các giao dịch rút đã pricing
    deposits = load_transactions(depo_file)  # Danh sách dict giao dịch nạp
    withdrawals = load_transactions(with_file)  # Danh sách dict giao dịch rút

    # 2. Sinh các cặp ứng viên (candidate pairs) thỏa mãn điều kiện thời gian, giá trị, token
    # - Chỉ ghép các cặp deposit/withdrawal cùng token, thời gian hợp lệ, giá trị hợp lệ
    candidates = generate_candidates(
        deposits, withdrawals, max_time_diff=600, max_rv=0.15
    )
    print(f"Generated {len(candidates)} candidate pairs.")

    # 3. Trích xuất đặc trưng cho từng cặp ứng viên
    # - Tạo ma trận đặc trưng X cho các cặp ứng viên (feature engineering)
    X = extract_features(candidates)
    print(f"Feature matrix shape: {X.shape}")

    # 4. (Demo) Sinh nhãn giả (toàn 0), thực tế cần thay bằng ground truth để huấn luyện thật
    # - y là vector nhãn (label), ở đây chỉ để demo nên toàn 0
    y = np.zeros(X.shape[0])

    # 5. Huấn luyện mô hình (hoặc load model)
    # - Thực tế nên tách train/test, ở đây demo fit toàn bộ để lấy model
    # - Có thể thay bằng train_xgboost_classifier nếu có nhãn thật
    import xgboost as xgb

    model = xgb.XGBClassifier()
    model.fit(X, y)  # Dummy fit với nhãn giả

    # 6. Dự đoán xác suất match cho từng cặp ứng viên
    y_hat = predict_proba(model, X)

    # 7. Ghép cặp cuối cùng bằng thuật toán greedy one-to-one và lưu kết quả ra file
    output_file = f"data/xgboost_matched/matched_xgboost_pairs_{service}_{year}.json"
    matches = greedy_matcher(
        deposits, withdrawals, candidates, y_hat, threshold=0.5, output_file=output_file
    )
    print(f"Saved {len(matches)} matches to {output_file}")
