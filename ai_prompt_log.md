# Nhật Ký Tương Tác AI (AI Prompt Log)

## Question 1:
"Cho tôi hỏi tại sao trong MySQL nên dùng kiểu DECIMAL(12, 2) cho các cột tài chính như tiền cọc hay phí phạt thay vì dùng FLOAT hoặc DOUBLE?"

**AI Response:**
Tiền tệ yêu cầu độ chính xác tuyệt đối. Kiểu `FLOAT` và `DOUBLE` là kiểu số thực dấu phẩy động (Floating-point) dựa trên chuẩn IEEE 754, dễ gây sai số làm tròn. Kiểu `DECIMAL(M, D)` lưu trữ số liệu dưới dạng chuỗi chuẩn xác, tránh tuyệt đối tình trạng sai số tiền tệ khi thực hiện các phép tính hoàn tiền.

---

## Question 2:
"Sự khác biệt giữa việc nhồi cột damage_description vào bảng Rentals so with việc tách riêng ra bảng Inspections là gì?"

**AI Response:**
Tách ra bảng `Inspections` mang lại các lợi ích chuẩn hóa CSDL:
1. **Quan hệ 1-N:** Một lượt thuê (`Rental`) có thể phát sinh nhiều lần kiểm tra (lúc nhận xe, sự cố giữa chừng, lúc trả xe).
2. **Tránh nhiễu dữ liệu:** Nếu không có sự cố, cột mô tả trong `Rentals` sẽ bị `NULL`.
3. **Phân định trách nhiệm:** Bảng `Inspections` cho phép lưu thêm ngày kiểm tra (`inspection_date`) và tên nhân viên kiểm tra (`inspector_name`), đảm bảo tính minh bạch.