### 1. Về Nội dung và Phương pháp luận

* **Vấn đề rò rỉ dữ liệu (Data Leakage) và Overfitting:** Bảng V báo cáo kết quả XGBoost đạt F1-score 100.0% trên tập SideShift. Trong môi trường blockchain thực tế với độ nhiễu cao, con số tuyệt đối này là phi thực tế và sẽ khiến các phản biện đánh trượt bài ngay lập tức vì nghi ngờ data leakage. => Các em phải thiết lập lại cơ chế chia tập Train/Test theo thời gian (Temporal Split) thay vì chia ngẫu nhiên (ví dụ: dùng dữ liệu Q1-Q3 để train, Q4 để test). Đánh giá lại mô hình trên một tập dữ liệu mất cân bằng sát thực tế hơn (ví dụ tỷ lệ positive:negative là 1:1000) thay vì tỷ lệ 1:3 đã được gọt giũa. Báo cáo thêm chỉ số PR-AUC (Precision-Recall Area Under Curve).


* **Lỗi logic vòng lặp trong tập Ground Truth (Circularity):** Các em sử dụng một rule cứng (Delta V < 0.01 và Delta T < 120s) để tự động gán nhãn cho tập positive. Việc đem tập nhãn này đi huấn luyện mô hình học có giám sát sẽ khiến XGBoost chỉ đóng vai trò "học vẹt" lại chính cái heuristic mà các bạn đang chê ở phần mở đầu. => Cần có cơ chế gán nhãn chéo (cross-validation) bằng tay cho một tập mẫu đủ lớn, hoặc sử dụng phương pháp un-supervised/semi-supervised clustering trước. Ở phần đánh giá, phải có một thí nghiệm chứng minh mô hình bắt được những giao dịch mà rule cơ bản bỏ sót (ngoại trừ các ca delay đã nêu).


* **Thiếu các Baseline hiện đại (SOTA):** Mô hình hiện tại chỉ đang so sánh với Heuristic, Random Forest và LightGBM. Những kỹ thuật này đã cũ.
* *Cách sửa:* Yêu cầu bắt buộc là phải đưa các thuật toán về đồ thị (Graph Neural Networks - GCN/GAT) vào làm baseline, vì bài toán theo vết dòng tiền bản chất là bài toán trên đồ thị. Nếu không dùng GNN, phải viết một đoạn lập luận thật chặt chẽ lý do vì sao GNN không khả thi với cấu trúc phí của Tron.


* **Tính tái lập và xác minh thực nghiệm (Reproducibility):** Bài báo khoa học chuẩn mực cần có tính minh bạch. => Đóng gói lại toàn bộ source code của framework TRON-ICE và các tập dataset (đã ẩn danh hóa các địa chỉ nhạy cảm) đẩy lên một repo mã nguồn mở (như GitHub). Cần trích dẫn link repo này trực tiếp vào bài báo (dưới dạng footnote) để hội đồng phản biện có thể tin cậy được.



### 2. Về Trình bày và Hình thức (Presentation & Formatting)

* **Sơ đồ kiến trúc hệ thống và luồng giao dịch:** Sơ đồ minh họa hệ thống matching và kiến trúc liên chuỗi (nếu có) phải đạt độ sắc nét tuyệt đối.
* *Cách sửa:* Không sử dụng ảnh chụp màn hình hay các công cụ vẽ vector kéo thả cơ bản sinh ra ảnh bitmap. Chuyển toàn bộ các hình vẽ kiến trúc sang hình vector là tốt nhất hoặc gấp 3 độ phân giải thông thường của hình. Điều này đảm bảo khi in ấn hoặc phóng to trên file PDF, các block và text vẫn sắc nét, đồng bộ font chữ với toàn bài và thể hiện sự chuyên nghiệp.


* **Định dạng Bảng biểu (Tables):** Các Bảng V, VI, VII đang được trình bày ở dạng default.
* *Cách sửa:* Xóa bỏ các đường kẻ sọc dọc trong toàn bộ bảng biểu. Sử dụng package `booktabs` trong LaTeX (với các lệnh `\toprule`, `\midrule`, `\bottomrule`) để bảng biểu nhìn thoáng và đúng chuẩn học thuật nhất. In đậm (`\textbf{}`) các chỉ số kết quả tốt nhất ở từng hàng.

 Rà soát và biên dịch lại toàn bộ các công thức toán học, bảng biểu, đảm bảo hiển thị đẹp vào không có lỗi hiển thị như chồng chéo, lố bề rộng... Đảm bảo thống nhất các ký hiệu (notation) từ Bảng II xuống các phần công thức bên dưới một cách chặt chẽ.

 - Vẽ sơ đồ kiến trúc hệ thống.
 - Bổ sung tên các tác giả và email.