# Phân chia công việc

Link viết bài báo: [overleaf](https://www.overleaf.com/2462761284ynddbdcwbfvz#eb6e42)

Bài mẫu: 

https://drive.google.com/file/d/1E06OPKjQmP6IQnzlyK-3GC2G_RW_In7d/view?usp=sharing

## 1. Đánh giá khả năng & Chiến lược điểm nhấn

- **Mức độ khả thi:** Trung bình - Khó. Rào cản lớn nhất là thời gian cào dữ liệu và thiết kế thuật toán mới.
- **Chiến lược chọn "Chain mới":** Chọn mạng **Tron (TRC-20)**.
- **Lý do chọn Tron:** Cấu trúc tài khoản (Account-based) khá giống Ethereum nên dễ tái hiện thuật toán cũ, nhưng Tron lại là mạng được tội phạm sử dụng nhiều nhất để chuyển USDT qua các sàn ICE nhờ phí rẻ. Đây là một "Research Gap" cực kỳ thuyết phục cho bài báo mới.
- **Chiến lược "Nâng cấp thuật toán":** Thay vì chỉ dùng luật IF-ELSE cứng nhắc cho thời gian và giá trị như bài gốc, hãy áp dụng một mô hình Học máy cơ bản (như Random Forest hoặc XGBoost) để phân loại các cặp giao dịch "Nạp - Rút". Hoặc đơn giản hơn là thêm một trọng số phạt theo thời gian (Time-decay weighting) để linh hoạt hóa biên độ $\bigtriangleup T$

---

## 2. Lộ trình thực hiện (Roadmap 19 ngày)

| **Khung thời gian** | **Giai đoạn** | **Mục tiêu công việc (Deliverables)** |
| --- | --- | --- |
| **Ngày 1-3** | **Thu thập & Làm sạch dữ liệu** | - Xác định ví nóng (Hot Wallet) của 2 sàn ICE (VD: FixedFloat, ChangeNOW) trên mạng Tron.
- Viết script dùng TronGrid API để cào dữ liệu trong 3-5 ngày gần nhất.
- **Dev:** Trả ra file CSV chứa dữ liệu giao dịch đã quy đổi sang USD. |
| **Ngày 4-6** | **Tái hiện Baseline (Bản gốc)** | - Code lại thuật toán khớp nối theo giá trị và thời gian của bài báo gốc (Section 5).
- **Dev:** Chạy thử trên tập dữ liệu đã cào, ghi nhận độ chính xác cơ bản. |
| **Ngày 7-9** | **Nâng cấp thuật toán** | - Áp dụng điểm mới (Học máy hoặc Trọng số linh hoạt).
- Lấy dữ liệu Nạp/Rút làm tập huấn luyện (Training set).
- **Dev:** Hoàn thiện code thuật toán phiên bản 2.0. |
| **Ngày 10-12** | **Thực nghiệm trên Tron** | - Chạy thuật toán 2.0 trên toàn bộ tập dữ liệu mạng Tron.
- **Research:** Bắt đầu viết Introduction, Related Work và Methodology cho bài báo mới. |
| **Ngày 13-15** | **Đánh giá & Tìm Case Study** | - Tính toán các chỉ số False Positive, False Negative. So sánh Baseline vs 2.0.
- Tìm trên Twitter (ZachXBT) 1 vụ lừa đảo dùng Tron và ICE để minh họa.
- **Dev:** Vẽ biểu đồ so sánh, trực quan hóa dòng tiền (dùng Gephi). |
| **Ngày 16-18** | **Viết & Ráp nối báo cáo** | - Đưa biểu đồ, dữ liệu vào bài. Viết phần Evaluation và Conclusion.
- **Research + Dev:** Review chéo bài viết, format theo chuẩn IEEE/ACM. |
| **Ngày 19** | **Buffer & Nộp bài** | - Chỉnh sửa lỗi chính tả, kiểm tra format slide thuyết trình.
- Đóng gói source code lên GitHub. Nộp bài. |

---

## 3. Phương pháp & Tài nguyên

- **Từ khóa tìm kiếm (Keywords):** `Tron blockchain tracking`, `TRC-20 money laundering via ICE`, `Heuristic transaction matching cryptocurrency`, `Machine learning cross-chain tracing`.
- **Công cụ / Phần mềm:**
    - **Ngôn ngữ:** Python (Bắt buộc để đi nhanh).
    - **Thư viện:** `tronpy` hoặc `requests` (gọi API Tron), `pandas` (xử lý dataframe), `scikit-learn` (nếu dùng Học máy).
    - **API & Dữ liệu:** TronGrid API (mạng Tron), Etherscan API (nếu cần so sánh), CoinGecko API (lấy tỷ giá USD).
    - **Trực quan hóa:** Gephi (xuất file CSV từ Python ra Gephi để vẽ đồ thị mạng lưới dòng tiền).

---

## 4. Cấu trúc báo cáo chuẩn (Outline)

- **1. Abstract:** Tóm tắt vấn đề, phương pháp cải tiến và kết quả (viết cuối cùng).
- **2. Introduction:** Bối cảnh ICE bị lạm dụng. Nhấn mạnh "Research Gap" (bài cũ chưa làm trên Tron và thuật toán còn cứng nhắc).
- **3. Background & Related Work:** Cơ chế hoạt động của mạng Tron và ICE. Tóm tắt nhanh bài báo gốc.
- **4. Methodology (Trọng tâm):**
    - 4.1. Data Collection trên mạng Tron.
    - 4.2. Thuật toán gốc (Baseline Method).
    - 4.3. Thuật toán nâng cấp (Proposed Upgraded Algorithm).
- **5. Evaluation:** Bảng so sánh hiệu suất giữa thuật toán cũ và mới. Đồ thị phân phối thời gian xử lý của mạng Tron so với Ethereum.
- **6. Case Study:** Minh họa 1 dòng tiền bẩn thực tế đi qua ICE trên mạng Tron.
- **7. Conclusion & Limitations:** Kết luận và nêu rõ giới hạn của nghiên cứu (do thời gian ngắn, lượng dữ liệu chưa bao phủ hết các năm).

---

## 5. Cảnh báo rủi ro & Cách phòng tránh

1. **Chìm đắm vào việc cào dữ liệu (Data Trap):** Quá trình cào API luôn xảy ra lỗi timeout hoặc bị chặn vì vượt quá giới hạn (Rate limit).
    - *Phòng tránh:* Đừng tham lam cào dữ liệu cả tháng. Hãy chọn ra đúng 1 tuần có biến động lớn (VD: tuần xảy ra vụ hack nào đó) hoặc cào khoảng 5000 giao dịch là đủ để làm PoC. Lưu ngay ra ổ cứng cục bộ.
2. **Khớp nối sai vì phí mạng lưới (Network Fee):** Trên Ethereum phí tính bằng Gas, trên Tron tính bằng Energy/Bandwidth. Nếu dùng công thức bằng nhau tuyệt đối ($V_{in}$= $V _{out}$) sẽ không tìm ra giao dịch nào.
    - *Phòng tránh:* Bắt buộc thiết lập ngưỡng sai số $\Delta V$ khoảng 1% đến 5% tùy thuộc vào biến động giá.
3. **Hội chứng "Bỏ quên báo cáo":** Sinh viên IT hay cắm đầu vào code đến ngày 17 mới bắt đầu viết chữ đầu tiên.
    - *Phòng tránh:* Viết cuốn chiếu. Ngày nào xong thuật toán, viết luôn phần Methodology của ngày đó.