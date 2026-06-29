# Đề xuất chỉnh sửa nội dung bài báo cho hệ thống TRON-ICE mới

Tài liệu này tổng hợp các thay đổi nên áp dụng vào bài báo để đồng bộ với pipeline hiện tại của hệ thống mới. Nội dung được viết theo hướng có thể trực tiếp chuyển thành đoạn văn, mục mới hoặc thay thế trong bài báo.

## 1. Những thay đổi chính cần cập nhật

Hệ thống hiện tại đã phát triển từ một pipeline đơn giản sang một pipeline end-to-end có cấu trúc rõ ràng hơn:

- Tách riêng rõ ràng giữa baseline matching và XGBoost-based matching.
- Baseline matcher hiện thực hiện matching theo quy tắc nghiêm ngặt: withdrawal chỉ được xét nếu xảy ra sau deposit, trong cùng cửa sổ thời gian giới hạn, và có mức độ chênh lệch giá trị hợp lý.
- Baseline còn bổ sung ưu tiên theo address reuse, tức là nếu địa chỉ receiver của withdrawal từng xuất hiện trong danh sách sender của deposit thì được xếp hạng cao hơn.
- XGBoost không còn được mô tả như một công cụ chạy độc lập trong luồng cũ; thay vào đó, nó được huấn luyện và dự đoán qua một pipeline riêng hiện đại.
- Hệ thống hiện đã có bước candidate generation, feature engineering, model scoring và greedy one-to-one matching, thay vì chỉ dừng ở việc chọn cặp có xác suất cao nhất.

## 2. Đề xuất chỉnh sửa từng phần trong paper

### 2.1. Abstract

Nên cập nhật abstract để phản ánh đúng hệ thống hiện tại, thay vì chỉ mô tả một hệ thống “XGBoost classifier” đơn thuần. Gợi ý nội dung mới:

- TRON-ICE không chỉ dựa trên heuristic matching mà còn xây dựng một pipeline hoàn chỉnh gồm thu thập dữ liệu, chuẩn hóa giao dịch, sinh candidate pairs, trích xuất đặc trưng và dự đoán bằng XGBoost.
- Cuối cùng, hệ thống áp dụng greedy one-to-one matching với các quy tắc ưu tiên như address reuse và độ lệch thời gian/giá trị tối thiểu.

### 2.2. Introduction

Phần Introduction nên thay đổi để nhấn mạnh rằng nghiên cứu này không chỉ “áp dụng XGBoost” mà là “thiết kế một framework forensics end-to-end cho ICE trên Tron”.

Đoạn cần thay thế:

- “We replace rigid heuristic thresholds with an XGBoost classifier...”

Thành:

- “We replace rigid heuristic thresholds with an end-to-end matching framework that combines candidate generation, feature engineering, XGBoost-based scoring, and one-to-one matching with address-reuse-aware tie-breaking.”

### 2.3. Methodology

Phần Methodology nên được viết lại theo cấu trúc hiện tại của hệ thống mới như sau:

1. Data collection from TronGrid and historical price sources.
2. Transaction normalization and classification into deposits and withdrawals.
3. Candidate generation under temporal and value constraints.
4. Feature engineering using temporal proximity, value deviation, token consistency, address reuse, and behavioral signals.
5. XGBoost-based scoring and final greedy matching.
6. Ground-truth construction and model training through a dedicated training-and-inference pipeline.

### 2.4. Experimental section

Phần thực nghiệm nên được trình bày theo hướng tập trung vào quy trình xây dựng dữ liệu, cách đánh giá và kết quả chính, thay vì mô tả kỹ thuật quá chi tiết.

#### 2.4.1. Experimental protocol

Có thể viết lại thành đoạn sau:

> We conducted the evaluation on a temporal holdout set constructed from SideShift-related Tron requests collected between 2026-05-22 and 2026-06-28. The training period covered requests before 2026-06-20, while the holdout period covered requests from 2026-06-21 to 2026-06-28. In total, 1,561 requests involving Tron were considered. The strict positive seeds were formed by matching deposit-withdrawal pairs to off-chain request records when the chain/network, token, amount, and temporal ordering were consistent. Negative samples were drawn from candidate pairs that were not selected as strict positives. The initial XGBoost model was trained on these strict positives and sampled negatives, and then refined through self-training using high-confidence pseudo-labels.

#### 2.4.2. Evaluation setting

Có thể viết lại thành đoạn sau:

> Evaluation was conducted on the temporal holdout set, where a pair was considered a positive match only when the model confidence was at least 0.99. This conservative threshold was chosen because the matching task prioritizes precision over recall in forensic applications.

#### 2.4.3. Results

Có thể dùng một bảng ngắn gọn hơn trong LaTeX như sau:

```latex
\begin{table}[t]
\centering
\caption{Temporal holdout evaluation at the high-confidence threshold of 0.99.}
\label{tab:results}
\begin{tabular}{lcccccccccc}
\toprule
Method & Threshold & Accuracy & Precision & Recall & F1 & PR-AUC & TP & FP & TN & FN \
\midrule
Baseline strict rule & $dt \le 120s, rv \le 0.005$ & 0.9420 & 0.0000 & 0.0000 & 0.0000 & 0.0580 & 0 & 0 & 2258 & 139 \
XGBoost & $p \ge 0.99$ & 0.9912 & 0.9836 & 0.8633 & 0.9195 & 0.9931 & 120 & 2 & 2256 & 19 \
\bottomrule
\end{tabular}
\end{table}
```

Đoạn văn mô tả đi kèm có thể là:

> On the temporal holdout set, the proposed model identified 122 matching pairs with only two false positives, substantially outperforming the strict heuristic baseline in both precision and recall.

### 2.5. Conclusion

Nên cập nhật kết luận để nhấn mạnh TRON-ICE là một hệ thống forensic toàn diện, chứ không chỉ là một mô hình phân lớp.

## 3. Đề xuất chèn sơ đồ kiến trúc vào đầu Methodology

Đây là thay đổi quan trọng nhất để bài báo phản ánh đúng hệ thống mới. Nên chèn sơ đồ kiến trúc ngay sau tiêu đề section Methodology, trước subsection Notation hoặc trước phần Data Collection.

### 3.1. Vị trí chèn

Chèn ngay sau:

```latex
\section{Methodology}
```

và trước:

```latex
\subsection{Notation}
```

### 3.2. Mẫu LaTeX để chèn

```latex
\begin{figure*}[t]
  \centering
  \includegraphics[width=\textwidth]{<tên-hình-kiến-truc>}
  \caption{Overall architecture of the proposed TRON-ICE framework. The pipeline begins with on-chain data collection and transaction normalization, then generates candidate deposit-withdrawal pairs, scores them with XGBoost, and produces final one-to-one matches through address-reuse-aware matching.}
  \label{fig:architecture}
\end{figure*}
```

### 3.3. Đoạn văn mô tả đi kèm

Có thể thêm một đoạn ngắn ngay sau figure như sau:

> TRON-ICE follows an end-to-end pipeline for ICE transaction matching on Tron. First, raw on-chain transactions are collected and normalized into structured deposits and withdrawals. Second, candidate pairs are generated under temporal and value constraints. Third, each candidate is represented by handcrafted features and scored by an XGBoost classifier. Finally, a greedy one-to-one matcher produces the final deposit-withdrawal pairs while preserving address-reuse and deviation-based ranking rules.

## 4. Đề xuất đoạn mô tả Methodology mới

Có thể thay thế phần mô tả methodology cũ bằng đoạn ngắn sau:

> Given a set of classified deposits and withdrawals, TRON-ICE first generates a candidate pool of feasible pairs based on temporal ordering, token consistency, and relative value similarity. Each candidate is then represented by features capturing temporal proximity, value deviation, address reuse, and behavioral signals. A trained XGBoost classifier outputs a matching probability for each candidate, and a one-to-one greedy matcher selects the final pairs while enforcing address-reuse-aware tie-breaking and minimal deviation ranking.

## 5. Các điểm cần bỏ hoặc đổi trong paper cũ

- Bỏ mô tả rằng baseline matcher dùng cửa sổ thời gian hai chiều ± time window.
- Bỏ hoặc sửa mô tả rằng XGBoost chạy trực tiếp qua một công cụ huấn luyện/đánh giá cũ.
- Thay bằng mô tả một pipeline huấn luyện và dự đoán hiện đại, tập trung vào việc tạo nhãn, học mô hình và đánh giá trên tập holdout theo thời gian.
- Nếu vẫn giữ phần mô tả baseline, nên ghi rõ rằng nó ưu tiên thời gian sau deposit và áp dụng address reuse trước khi chọn ứng viên khác.

## 6. Tài liệu tham khảo nội bộ nên dùng để đối chiếu

- Các tài liệu phân tích về matching hiện tại.
- Tài liệu mô tả kiến trúc hệ thống.
- Tài liệu về workflow SideShift semi-supervised.

---

> Ghi chú: Đây là bản đề xuất có thể dùng trực tiếp làm nền để chỉnh lại paper.tex theo hệ thống hiện tại của TRON-ICE.
