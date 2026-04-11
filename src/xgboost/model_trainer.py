# Module: model_trainer.py
# Chức năng: Huấn luyện mô hình XGBoost để phân loại cặp ứng viên (match hoặc không match), đánh giá bằng F1-score.

import xgboost as xgb
from sklearn.metrics import f1_score
import numpy as np


def train_xgboost_classifier(X_train, y_train, X_test, y_test, scale_pos_weight=1.0):
    """
    Huấn luyện mô hình XGBoost phân loại nhị phân trên tập train và đánh giá trên tập test.
    Tham số:
        - X_train, y_train: Dữ liệu đặc trưng và nhãn cho huấn luyện.
        - X_test, y_test: Dữ liệu đặc trưng và nhãn cho kiểm tra.
        - scale_pos_weight: Tham số cân bằng mẫu dương/âm (hữu ích khi dữ liệu mất cân bằng).
    Các bước thực hiện:
        1. Khởi tạo mô hình XGBClassifier với các siêu tham số:
            - max_depth: Độ sâu tối đa của cây quyết định.
            - learning_rate: Tốc độ học.
            - n_estimators: Số lượng cây (vòng boosting).
            - objective: Hàm mất mát (binary:logistic cho phân loại nhị phân).
            - scale_pos_weight: Cân bằng nhãn dương/âm.
            - use_label_encoder: Không dùng encoder cũ (theo khuyến nghị mới).
            - eval_metric: Chỉ số đánh giá (logloss).
        2. Huấn luyện mô hình trên tập train (model.fit).
        3. Dự đoán nhãn trên tập test (model.predict).
        4. Tính toán F1-score trên tập test để đánh giá chất lượng mô hình.
        5. In ra F1-score và trả về model đã huấn luyện.
    """
    # 1. Khởi tạo mô hình XGBoost với các siêu tham số phù hợp cho phân loại nhị phân
    model = xgb.XGBClassifier(
        max_depth=5,  # Độ sâu tối đa của mỗi cây quyết định
        learning_rate=0.1,  # Tốc độ học
        n_estimators=100,  # Số lượng cây boosting
        objective="binary:logistic",  # Phân loại nhị phân
        scale_pos_weight=scale_pos_weight,  # Cân bằng nhãn dương/âm
        use_label_encoder=False,  # Không dùng encoder cũ
        eval_metric="logloss",  # Đánh giá bằng logloss
    )
    # 2. Huấn luyện mô hình trên tập train
    model.fit(X_train, y_train)
    # 3. Dự đoán nhãn trên tập test
    y_pred = model.predict(X_test)
    # 4. Tính F1-score để đánh giá hiệu quả mô hình
    f1 = f1_score(y_test, y_pred)
    print(f"F1 score: {f1:.4f}")
    # 5. Trả về model đã huấn luyện
    return model
