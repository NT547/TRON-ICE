# Phân tích thuật toán Matching và XGBoost (TRON-ICE)

Tập tin này tổng hợp kiểm tra hiện trạng các thuật toán matching trong project, so sánh với các quy tắc yêu cầu, và đề xuất chỉnh sửa thực thi.

Ghi chú: đã áp sửa code vào `src/baseline_algorithm/matcher.py` và `src/xgboost/matcher.py` để buộc W sau D, ưu tiên address reuse trước chọn xác suất, và tiebreak theo tổng lệch V+T.

## Yêu cầu mong đợi (tóm tắt)
- Thứ tự thời gian: withdrawal (W) phải xảy ra sau deposit (D).
- Lọc theo ngưỡng: chỉ chọn W trong ngưỡng sai lệch giá trị (V) và thời gian (T).
- Ngưỡng V thường 1%–5% (0.01–0.05).
- Ngưỡng T ngắn (ví dụ 5 phút = 300s).
- Ưu tiên **Address Reuse**: nếu W.to == D.from, chọn ngay bất kể các ứng viên khác nhiễu hơn.
- Nếu nhiều ứng viên thỏa điều kiện (không reuse), chọn ứng viên có tổng độ lệch về giá và thời gian nhỏ nhất (rule "Minimal V and T").

## Tệp đã kiểm tra
- Baseline matcher: [src/baseline_algorithm/matcher.py](src/baseline_algorithm/matcher.py#L1-L300)
- Baseline price calculator: [src/baseline_algorithm/price_calculator.py](src/baseline_algorithm/price_calculator.py#L1-L300)
- XGBoost candidate generator: [src/xgboost/candidate_generator.py](src/xgboost/candidate_generator.py#L1-L200)
- XGBoost feature engineering: [src/xgboost/feature_engineering.py](src/xgboost/feature_engineering.py#L1-L200)
- XGBoost matcher: [src/xgboost/matcher.py](src/xgboost/matcher.py#L1-L200)
- XGBoost pipeline entry: [src/xgboost/pipeline.py](src/xgboost/pipeline.py#L1-L300)

## Kết luận nhanh
- `candidate_generator` (XGBoost) tuân thủ rõ ràng quy tắc **thứ tự thời gian** (chỉ tìm W sau D) và áp ngưỡng `max_time_diff` + `max_rv`.
- `feature_engineering` cung cấp cờ `reuse` (address reuse) — tốt để model học ưu tiên, nhưng hiện tại **không có bảo đảm thuật toán** cưỡng chế ưu tiên reuse trước mọi tiêu chí khác.
- `xgboost.matcher.greedy_matcher` chọn ứng viên theo **xác suất cao nhất** (probability) và không áp dụng một bước ưu tiên reuse độc lập trước khi so sánh probability.
- `baseline_algorithm.matcher.match_deposit_withdrawal` hiện dùng cửa sổ thời gian hai chiều (± time_window) — cho phép W xảy ra trước D, trái với yêu cầu **W phải sau D**.
- Baseline matcher không hiện có bước tường minh để ưu tiên `address reuse` hoặc áp quy tắc "Minimal V and T" khi nhiều ứng viên hợp lệ.

## Vấn đề cụ thể và vị trí (chi tiết)
1) Thứ tự thời gian vi phạm (Baseline)
   - Vị trí: [src/baseline_algorithm/matcher.py](src/baseline_algorithm/matcher.py#L1-L120)
   - Chi tiết: `match_deposit_withdrawal` dùng

```py
left = bisect.bisect_left(withdrawal_timestamps, dep_ts - time_window * 1000)
right = bisect.bisect_right(withdrawal_timestamps, dep_ts + time_window * 1000)
```

  Điều này cho phép chọn các withdrawal trước khi deposit (khoảng âm) vì tìm trong interval `dep_ts - window`..`dep_ts + window`.

2) Filtering theo ngưỡng (Baseline)
   - Vị trí: cùng hàm `match_deposit_withdrawal`.
   - Chi tiết: giá trị so sánh `value_diff = abs(w_value - dep_value) / dep_value` và so sánh `<= value_threshold` — đây là lọc hợp lệ, nhưng **giá trị chuẩn (scale)** dùng deposit làm mẫu trong mẫu này; nên nhất quán với XGBoost (dùng max(vd, vw)).

3) Address reuse priority
   - Vị trí: `feature_engineering` tạo `reuse` flag; nhưng `xgboost.matcher.greedy_matcher` *không* ưu tiên reuse trước khi dùng probability.
   - Hậu quả: model có thể học ưu tiên reuse, nhưng nếu model không hoàn hảo, thuật toán vẫn chọn một withdrawal khác có `probability` lớn hơn thay vì ép chọn `reuse` candidate.

4) Quy tắc "Minimal V and T"
   - Vị trí: cả baseline và greedy matcher hiện không thực thi tường minh.
   - Hậu quả: khi nhiều ứng viên thỏa ngưỡng, baseline trả về nhiều matches, nhưng không chọn sinh ra một 1-1 tối thiểu theo tổng chi phí; greedy XGBoost chọn theo xác suất (không phải phép đo tổng hợp V+T tối thiểu).

## Đề xuất chỉnh sửa (ưu tiên và cụ thể)
Gồm hai nhóm: (A) sửa `baseline` để tuân thủ ngay các quy tắc, (B) thay đổi `xgboost.matcher` để cưỡng chế ưu tiên reuse và tie-break bằng minimal V+T.

A. Sửa `baseline_algorithm/matcher.py`
- Trong `match_deposit_withdrawal`: thay window tìm kiếm thành chỉ tìm W sau D:

```py
left = bisect.bisect_right(withdrawal_timestamps, dep_ts)
right = bisect.bisect_right(
    withdrawal_timestamps, dep_ts + time_window * 1000
)
candidates = withdrawals[left:right]
```

- Kiểm tra `delta_t = (withdrawal['timestamp'] - dep_ts) // 1000` và `delta_t > 0` trước tính tiếp.
- Dùng cùng metric lệch giá như XGBoost để so sánh: `rv = abs(vd - vw) / max(vd, vw)` (thay vì chia cho vd) để tránh bias khi vd nhỏ.
- Sau thu thập `matches`, nếu cần chọn 1-1 trong baseline (không trả về nhiều match), bổ sung bước chọn với thứ tự ưu tiên: 1) any candidate with address reuse (pick the reuse with smallest delta_t if multiple), else 2) pick candidate with minimal combined score S = normalized_rv + normalized_dt, where normalized_dt = delta_t / time_window, normalized_rv = rv / value_threshold (cap at 1).

B. Sửa `xgboost/matcher.py` (`greedy_matcher`)
- Trước khi chọn theo xác suất, kiểm tra candidate list cho deposit `d` để tìm bất kỳ `w` sao cho `d.get('from') == w.get('to')` (address reuse). Nếu tồn tại, chọn **reuse** candidate ngay lập tức (nếu nhiều reuse chọn nhỏ nhất theo delta_t hoặc theo rv).
- Nếu không có reuse, thu thập tất cả candidates có `prob >= threshold` (hoặc có thể dùng top-k), nếu có >1, áp phép đo tiebreak:

  S = alpha * (rv / max_rv) + (1 - alpha) * (delta_t / max_time_diff)

  - `rv` = abs(vd - vw) / max(vd, vw)
  - `alpha` có thể mặc định 0.5 (cân bằng V và T) hoặc cấu hình.
  - Chọn candidate có S nhỏ nhất.

- Nên log rõ metadata cho mỗi match: `reuse_flag`, `rv`, `delta_t`, `probability`, `tie_break_score`.

C. Parametrize thresholds và make defaults conservative
- Đặt mặc định `value_threshold` = 0.05 (5%) ở mức pipeline, nhưng khuyến nghị giảm còn 0.01–0.05 tùy dịch vụ.
- Đặt mặc định `time_window` = 300 (5 phút).

## Snippets mẫu thay thế (xgboost matcher)
Ví dụ sửa `greedy_matcher` (ý tưởng):

```py
def select_candidate_for_deposit(d, candidate_list, probabilities, time_window, max_rv, alpha=0.5, threshold=0.5):
    # 1) address reuse
    reuse_candidates = [ (p,w) for (p,w) in candidate_list if d.get('from') == w.get('to') ]
    if reuse_candidates:
        # chọn reuse nhỏ nhất theo delta_t
        return min(reuse_candidates, key=lambda pw: (pw[1]['timestamp'] - d['timestamp']))
    # 2) lọc theo threshold rồi tiebreak bằng S
    valid = [ (p,w) for (p,w) in candidate_list if p >= threshold ]
    if not valid:
        return None
    def score(pw):
        p,w = pw
        rv = abs(d['usd_value'] - w['usd_value']) / max(d['usd_value'], w['usd_value'])
        dt = (w['timestamp'] - d['timestamp']) // 1000
        norm_rv = min(1.0, rv / max_rv)
        norm_dt = min(1.0, dt / time_window)
        return alpha * norm_rv + (1-alpha) * norm_dt
    return min(valid, key=score)
```

## Ghi chú testing & triển khai
- Sau áp thay đổi cần chạy pipeline `--mode baseline_algorithm` và `--mode xgboost` trên một sample dataset (ví dụ changenow 2024 samples) để so sánh các chỉ số: precision, recall, F1, distribution of delta_t, fraction of matches with reuse.
- Thực hiện A/B test: hiện trạng vs. cập nhật để đảm bảo không giảm performance tổng thể.

## Next steps tôi có thể làm giúp bạn
1. Áp patch code trực tiếp cho `baseline` và `xgboost.matcher` theo các snippets ở trên.
2. Chạy một thử nghiệm nhỏ trên bộ sample (các file `data/processed/...samples.csv`) và trả lại báo cáo thay đổi (precision/recall/F1).

Vui lòng cho biết bạn muốn tôi: (A) chỉ tạo file phân tích này (đã xong), (B) áp các sửa đổi code mẫu ngay bây giờ, hoặc (C) áp sửa và chạy tests mẫu.
