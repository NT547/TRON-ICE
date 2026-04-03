
### Tổng quan Giai đoạn 2: Tái hiện Baseline & Viết Related Work
[cite_start]Mục tiêu của giai đoạn này là chạy thuật toán cũ trên dữ liệu mới và hoàn thiện phần tổng quan[cite: 17].

---

### 👨‍💻 Dành cho Sinh viên A (Main Dev / Sub Research)
Nhiệm vụ trọng tâm của bạn là chứng minh thuật toán gốc có thể chạy được (và có thể chạy chưa tốt) trên mạng Tron để làm tiền đề cho bản nâng cấp sau này.

* [cite_start]**Code thuật toán Baseline:** Bạn cần code thuật toán Baseline của bài báo gốc[cite: 25]. Cụ thể là code lại thuật toán khớp nối theo giá trị và thời gian của bài báo gốc ở Section 5.
* [cite_start]**Chạy thử nghiệm:** Sau đó, bạn chạy thử trên dữ liệu Tron và xuất kết quả[cite: 25]. Mục đích là chạy thử trên tập dữ liệu đã cào và ghi nhận độ chính xác cơ bản.
* **⚠️ Chú ý bẫy dữ liệu (Khớp nối sai vì phí mạng lưới):** Không giống Ethereum tính phí bằng Gas, trên mạng Tron phí được tính bằng Energy/Bandwidth. 
* Nếu bạn sử dụng công thức bằng nhau tuyệt đối ($V_{in} = V_{out}$), bạn sẽ không tìm ra giao dịch nào.
* **Cách giải quyết:** Bắt buộc phải thiết lập ngưỡng sai số $\Delta V$ khoảng 1% đến 5% tùy thuộc vào biến động giá.
* [cite_start]**Phác thảo Phương pháp (Sub Research):** Bạn bắt đầu phác thảo phần Method (Phương pháp)[cite: 26]. [cite_start]Hãy nhớ nguyên tắc vàng là "Tính tái tạo" (Reproducibility): viết sao cho người khác đọc xong có thể tái tạo lại thí nghiệm của mình[cite: 27].

### 📝 Dành cho Sinh viên B (Main Research / Sub Dev)
Nhiệm vụ của bạn là xây dựng lớp nền học thuật vững chắc để bảo vệ tính cấp thiết cho bài báo, đồng thời phụ giúp Dev chuẩn hóa dữ liệu.

* [cite_start]**Viết mục Related Work:** Nhiệm vụ chính là viết mục Related Work[cite: 21].
* [cite_start]**Chiến lược viết:** Lưu ý phải "phân nhóm" và so sánh các bài báo với nhau, không liệt kê rời rạc từng bài[cite: 21]. [cite_start]Mục tiêu là để "Bán" giải pháp của nhóm mình[cite: 22].
* [cite_start]**Xử lý API tỷ giá (Sub Dev):** Hỗ trợ A gọi CoinGecko API để quy đổi tỷ giá token sang USD[cite: 23].

---

### 💡 Lời khuyên chung cho tiến độ nhóm
* **Tránh hội chứng "Bỏ quên báo cáo":** Sinh viên IT hay cắm đầu vào code đến ngày 17 mới bắt đầu viết chữ đầu tiên. 
* **Chiến lược viết cuốn chiếu:** Ngày nào xong thuật toán, viết luôn phần Methodology của ngày đó.

Hai bạn đã có sẵn tài khoản và API Key của TronGrid cũng như CoinGecko chưa để mình hướng dẫn thêm cách gọi API tối ưu, tránh bị dính lỗi Rate Limit?
