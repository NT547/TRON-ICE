# Module: predictor.py
# Chức năng: Dự đoán xác suất (probability) cho các cặp ứng viên bằng mô hình đã huấn luyện.

import numpy as np


def predict_proba(model, X):
    """
    Trả về xác suất dự đoán (probability) cho từng cặp ứng viên (match = 1) bằng mô hình đã huấn luyện.
    - model: mô hình đã huấn luyện (XGBoost, v.v.)
    - X: ma trận đặc trưng
    Trả về: mảng numpy chứa xác suất match cho từng cặp.
    """
    return model.predict_proba(X)[:, 1]
