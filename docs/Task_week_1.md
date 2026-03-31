Chào bạn, đồng môn UIT! Năm 3 ngành An toàn thông tin chắc hẳn bạn đã quen với áp lực chạy deadline đồ án rồi đúng không? Đồ án môn Blockchain này có độ khó từ Trung bình đến Khó. Tuy nhiên, nếu áp dụng đúng chiến lược cuốn chiếu, các bạn hoàn toàn có thể hoàn thành tốt trong 19 ngày.

Dưới đây là hướng dẫn chi tiết cách thực thi **Giai đoạn 1 (Ngày 1-3)** dành cho từng thành viên:

### Mục tiêu chung của Giai đoạn 1
Mục tiêu cốt lõi của 3 ngày đầu là thu thập, làm sạch dữ liệu, cào dữ liệu từ mạng Tron và xác định rõ "Gap" (Khoảng trống nghiên cứu). 

---

### Nhiệm vụ của Sinh viên B (Main Research)
Trọng trách của bạn là tạo bộ khung học thuật vững chắc để "bán" ý tưởng của nhóm.

* **Nghiên cứu tài liệu:** Áp dụng chiến lược **"3-Pass Approach"** để đọc hiểu sâu bài báo gốc. Sau đó, sử dụng kỹ thuật **"Snowballing"** trên Google Scholar để tìm kiếm các bài Related Work liên quan.
* **Viết nháp Introduction:** Tiến hành viết phần Introduction đi theo cấu trúc dẫn dắt 6 bước: Bối cảnh (Context) -> Vấn đề (Problem) -> Giải pháp hiện tại -> "Gap" -> Đóng góp của nhóm (Contribution). 
* **Nhấn mạnh Research Gap:** Khi viết, hãy đặc biệt làm nổi bật "Gap" ở đây là thuật toán cũ còn cứng nhắc và chưa được thực hiện trên mạng Tron. Cần nêu rõ lý do chọn Tron vì đây là mạng lưới được tội phạm sử dụng nhiều nhất để chuyển USDT qua các sàn ICE nhờ lợi thế phí rẻ.

---

### Nhiệm vụ của Sinh viên A (Main Dev)
Bạn là người chịu trách nhiệm về nguyên liệu thô (dữ liệu). Hãy làm việc này thật cẩn thận vì nó ảnh hưởng đến toàn bộ thuật toán phía sau.

* **Xác định mục tiêu cào dữ liệu:** Tìm và xác định các ví nóng (Hot Wallet) của 2 sàn ICE (ví dụ: FixedFloat, ChangeNOW) hoạt động trên mạng Tron.
* **Viết script thu thập:** Sử dụng Python cùng với thư viện `tronpy` hoặc `requests` để viết script. Dùng script này gọi TronGrid API để cào dữ liệu của các ví trên trong khoảng 3-5 ngày gần nhất.
* **Xuất dữ liệu:** Output cuối cùng phải trả ra một file CSV chứa dữ liệu giao dịch đã được quy đổi tỷ giá sang USD.
* **Phòng tránh rủi ro (Data Trap):** Quá trình cào API rất dễ gặp lỗi timeout hoặc bị chặn do giới hạn Rate limit. Đừng tham lam cào dữ liệu của cả tháng, chỉ nên chọn ra đúng 1 tuần có biến động lớn hoặc cào khoảng 5000 giao dịch để làm PoC (Proof of Concept) là đủ, và nhớ lưu ngay ra ổ cứng cục bộ.

---

### Điểm chạm chung (Collaboration)
Đừng ai làm việc của riêng người nấy, ở giai đoạn này hai bạn cần có một bước "Sub Research" giao nhau:
* Sinh viên A cần đọc kỹ phần thuật toán ở Pass 2 và Pass 3 của bài báo gốc để hiểu logic hệ thống.
* Sau đó, cả hai phải ngồi lại thảo luận để chốt xem hướng "Đóng góp (Contribution)" sắp tới (như dùng Machine Learning hay thêm trọng số linh hoạt) có thực sự khả thi để code kịp trong thời gian 19 ngày hay không.

