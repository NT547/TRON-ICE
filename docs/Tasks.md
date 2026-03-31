# KẾ HOẠCH THỰC HIỆN ĐỀ TÀI: REPLICATE & EXTEND "TOWARDS UNDERSTANDING AND ANALYZING INSTANT CRYPTOCURRENCY EXCHANGES"

**Môn học:** Blockchain: Nền tảng, ứng dụng và bảo mật (NT547.Q21.ANTT)
**Thời gian thực hiện:** 8 Tuần
**Nhóm:** 2 Sinh viên (Gia Bảo - DSE & Anh Khôi - AAE)

## 🛠 CÔNG NGHỆ & CÔNG CỤ SỬ DỤNG
* **Ngôn ngữ lập trình chính:** Python 3.9+
* **Thư viện xử lý dữ liệu:** `pandas`, `numpy`, `datetime`
* **Tương tác Blockchain & API:** `web3.py`, `requests`
* **Nguồn dữ liệu (APIs):** Etherscan API (Ethereum), BscScan API (BSC), CoinGecko API (Historical Price)
* **Trực quan hóa (Visualization):** `matplotlib`, `seaborn` (vẽ biểu đồ báo cáo) và **Gephi** hoặc **Maltego** (vẽ đồ thị mạng lưới dòng tiền cho Case Study).
* **Học máy (Nếu làm Extension theo hướng ML):** `scikit-learn` (DBSCAN, K-Means để phân cụm giao dịch).
* **Quản lý source code:** GitHub (Private repo).

---

## 📅 CHI TIẾT CÔNG VIỆC THEO TUẦN

### Tuần 1: Khởi động & Thu thập dữ liệu (Data Collection)
*Mục tiêu: Cào được tập dữ liệu thô (raw data) các giao dịch Nạp (In) và Rút (Out) của 2-3 sàn ICE (vd: FixedFloat, ChangeNOW).*

* **Gia Bảo (DSE):**
    * Đăng ký tài khoản Etherscan/BscScan để lấy API Keys (Free tier).
    * Viết script Python dùng `requests` gọi API để lấy lịch sử giao dịch (Normal Transactions & ERC20 Token Transfers) từ các địa chỉ ví nóng (Hot Wallets) của sàn ICE.
    * Lưu dữ liệu trả về dưới dạng file `.csv` hoặc `.json`. *Lưu ý: Thêm hàm `time.sleep()` để tránh bị API chặn do rate limit.*
* **Anh Khôi (AAE):**
    * Đọc kỹ Section 3 & 4 của bài báo gốc. Trích xuất danh sách các địa chỉ ví (Hot Wallets) của các ICE mà bài báo đã đề cập (hoặc tìm trên Etherscan nhãn "FixedFloat", "ChangeNOW").
    * Thiết kế cấu trúc dữ liệu chuẩn (Schema) cần lưu: `TxHash`, `BlockNumber`, `TimeStamp`, `From`, `To`, `Token_Symbol`, `Amount`.

### Tuần 2: Tiền xử lý & Tính toán giá trị (Data Preprocessing)
*Mục tiêu: Làm sạch dữ liệu và quy đổi mọi token (ETH, USDT, USDC...) sang đồng USD tại đúng thời điểm giao dịch.*

* **Gia Bảo (DSE):**
    * Đăng ký CoinGecko API. Viết script lấy giá trị lịch sử (Historical Price) của các token theo từng mốc thời gian (TimeStamp) của giao dịch.
    * Viết hàm hợp nhất (Merge) giá USD vào file CSV dữ liệu thô. (Tạo cột mới: `Amount_USD`).
* **Anh Khôi (AAE):**
    * Sử dụng `pandas` để làm sạch dữ liệu: Xóa các dòng lỗi (Null/NaN), lọc bỏ các giao dịch nội bộ của sàn (sàn tự chuyển tiền qua lại giữa các ví của nó).
    * Tách tập dữ liệu thành 2 tập: Tập giao dịch Nạp ($Tx_{in}$) và Tập giao dịch Rút ($Tx_{out}$).

### Tuần 3: Tái hiện thuật toán gốc (Baseline Replication)
*Mục tiêu: Code lại thuật toán khớp nối heuristic bằng quy tắc thời gian ($\Delta T$) và giá trị ($\Delta V$).*

* **Gia Bảo (DSE):**
    * Hỗ trợ tối ưu hóa vòng lặp bằng `pandas` (Vectorization) hoặc dùng cấu trúc dữ liệu phù hợp (Hash map / Dictionary) để thuật toán chạy không bị quá tải (tránh độ phức tạp $O(n^2)$ khi so sánh chéo 2 tập dữ liệu).
* **Anh Khôi (AAE):**
    * Code lõi thuật toán khớp nối:
        * Điều kiện 1: Thời gian $Tx_{out}$ phải xảy ra sau $Tx_{in}$ trong khoảng thời gian cho phép ($0 < T_{out} - T_{in} \le \Delta T_{max}$).
        * Điều kiện 2: Giá trị chênh lệch (đã trừ phí/trượt giá) phải nằm trong biên độ ($|V_{in} - V_{out}| \le \epsilon$).
    * Chạy thử nghiệm trên tập dữ liệu và xuất ra danh sách các cặp (pairs) nghi ngờ là 1 lượt chuyển đổi.

### Tuần 4: Thiết kế điểm mới (Extension Design)
*Mục tiêu: Brainstorm và chốt phương pháp mở rộng (Ví dụ: Thêm thuật toán Machine Learning để nhóm các giao dịch bị cố tình chẻ nhỏ - Amount Splitting).*

* **Gia Bảo (DSE):**
    * Nghiên cứu cách lấy dữ liệu thêm (nếu Extension yêu cầu). Ví dụ: cào thêm dữ liệu từ mạng Layer 2 (Arbitrum) hoặc cầu nối (Cross-chain Bridge).
    * Chuẩn bị môi trường thư viện (`scikit-learn` v.v.).
* **Anh Khôi (AAE):**
    * Nghiên cứu và chốt logic cho Extension. (Gợi ý: Nếu sàn chẻ 1 lệnh rút 100$ thành 2 lệnh 50$ và 50$, thuật toán gốc sẽ thất bại. Hãy dùng thuật toán gom cụm (Clustering) theo khung thời gian trước, sau đó tính tổng giá trị cụm để so sánh với $V_{in}$).
    * Viết mã giả (Pseudocode) cho phương pháp mới.

### Tuần 5: Triển khai Điểm mới (Extension Implementation)
*Mục tiêu: Hoàn thiện code cho thuật toán mở rộng.*

* **Gia Bảo (DSE):**
    * Đảm bảo dữ liệu đầu vào cho model mới đã sẵn sàng.
    * Viết các hàm đánh giá tự động (Evaluation metrics functions) và log kết quả ra file.
* **Anh Khôi (AAE):**
    * Lập trình thuật toán Extension bằng Python.
    * Fine-tune các tham số (Hyperparameters) như: $\Delta T$, $\epsilon$, hoặc số cụm $K$ để đạt hiệu quả tốt nhất.

### Tuần 6: Đánh giá & So sánh (Evaluation)
*Mục tiêu: Ra được kết quả định lượng chứng minh Extension tốt hơn Baseline.*

* **Gia Bảo (DSE):**
    * Chạy code của Tuần 3 (Baseline) và Tuần 5 (Extension) trên cùng 1 tập Dataset.
    * Xuất log kết quả, dùng `matplotlib`/`seaborn` vẽ biểu đồ so sánh: Số cặp khớp được, Thời gian chạy, Tỷ lệ phát hiện...
* **Anh Khôi (AAE):**
    * Phân tích kết quả: Tính các chỉ số Độ chính xác ước lượng, False Positive (Khớp nhầm), False Negative (Bỏ sót).
    * Tìm và phân tích 1-2 trường hợp cụ thể (Edge cases) mà Baseline sai nhưng Extension lại bắt đúng.

### Tuần 7: Case Study thực tế (Real-world Tracing)
*Mục tiêu: Chứng minh tính ứng dụng của tool bằng một vụ án thực tế.*

* **Gia Bảo (DSE):**
    * Lên mạng (Twitter, bài báo bảo mật) tìm 1 vụ hack/scam có sử dụng FixedFloat hoặc ChangeNOW để rửa tiền.
    * Lấy Hash của các giao dịch khởi điểm (dòng tiền bẩn đi vào ICE).
* **Anh Khôi (AAE):**
    * Đưa các Hash đó vào tool nhóm vừa viết để "dò" xem đầu ra ($Tx_{out}$) là những ví nào.
    * Sử dụng **Gephi** nhập dữ liệu danh sách ví để vẽ sơ đồ đồ thị mạng lưới (Network Graph) dòng tiền cực ngầu đưa vào báo cáo.

### Tuần 8: Viết báo cáo & Bảo vệ (Report & Presentation)
*Mục tiêu: Hoàn thiện báo cáo định dạng IEEE/ACM.*

* **Gia Bảo (DSE):**
    * Làm sạch source code, bổ sung comments.
    * Đẩy (Push) code hoàn chỉnh lên GitHub, viết file `README.md` hướng dẫn chi tiết cách chạy tool.
    * Viết phần Methodolgy (Data Collection) trong báo cáo.
* **Anh Khôi (AAE):**
    * Viết Abstract, Introduction, Background và phần đánh giá thuật toán (Evaluation) trong báo cáo.
* **Cả hai:**
    * Làm Slide bảo vệ (15-20 slides).
    * Tập thuyết trình và chuẩn bị trả lời các câu hỏi phản biện của giảng viên.