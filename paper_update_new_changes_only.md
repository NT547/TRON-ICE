# Những điểm mới so với bài báo cũ

## 1. Cấu trúc hệ thống đã thay đổi
- Hệ thống tách rõ `baseline_algorithm` và pipeline `ground-truth`/XGBoost.
- `main.py` không còn sử dụng `--mode xgboost`; XGBoost giờ được quản lý bằng các script riêng trong `ground-truth/`.

## 2. Logic matching baseline mới
- Baseline matcher hiện chỉ tìm `withdrawal` ở phía sau `deposit` trong một khoảng `time_window`, không còn dùng cửa sổ `± time_window`.
- Baseline ưu tiên `address reuse` trước khi chọn candidate khác.
- Baseline xếp hạng ứng viên theo tổng sai lệch giá-trị và thời gian (Minimal V and T), thay vì chỉ dựa vào threshold đơn thuần.

## 3. Cập nhật metric giá trị
- Độ lệch giá trị nên so sánh theo `|vd - vw| / max(vd, vw)` hoặc tương đương, để nhất quán với feature XGBoost.

## 4. Dữ liệu đầu vào/đầu ra hiện tại
- Input matcher hiện dùng file `data/classified/deposits_trongrid_{service}_{year}*.csv` và `data/classified/withdrawals_trongrid_{service}_{year}*.csv`.
- Output matcher là `data/matched/matched_pairs_{service}_{year}.csv`, với file mẫu `_samples` xử lý riêng.

## 5. Workflow XGBoost mới
- XGBoost training và dự đoán chạy riêng qua:
  - `ground-truth/train_xgboost.py`
  - `ground-truth/predict_xgboost.py`
- Nếu bài báo còn nói XGBoost chạy trực tiếp trong CLI chung, đó là thông tin cũ.

## 6. SideShift và ground truth
- Hiện có workflow SideShift semi-supervised được mô tả trong `docs/sideshift_semisupervised.md`.
- Nếu bài báo cũ chỉ dùng ground truth cứng thuần, cần bổ sung điểm này như phần mở rộng hiện tại.

## 7. Điều nên xóa khỏi bài báo cũ
- Các mô tả về `main.py --mode xgboost` legacy.
- Các mô tả baseline dùng cửa sổ thời gian hai chiều.
- Các mô tả XGBoost matcher chỉ chọn candidate theo xác suất cao nhất mà không nhắc tới reuse/tiebreak logic.
