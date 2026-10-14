# Phân Tích Thiết Kế Cơ Sở Dữ Liệu AutoRide

## Tại sao cột `damage_fee` là bắt buộc phải có để đảm bảo tính toàn vẹn hệ thống?

Trong quy trình thực tế (UML Activity Diagram), việc trả xe phát sinh các nhánh rẽ kiểm tra hư hỏng và tính phí đền bù. Nếu cơ sở dữ liệu vắng mặt cột `damage_fee` (và `late_fee`), hệ thống bị hổng logic tài chính trầm trọng:

1. **Thất thoát tài chính:** Hệ thống không thể ghi nhận khoản thu từ tiền đền bù của khách, dẫn đến việc tiền hoàn cọc (`security_deposit`) bị hoàn trả 100% hoặc phải ghi sổ tay ngoài hệ thống.
2. **Không thể truy vết tự động:** Không thể thực hiện các câu lệnh truy vấn tài chính tự động (`security_deposit - late_fee - damage_fee`) ngay trên ứng dụng.
3. **Đảm bảo tính chuẩn hóa (Normalization):** Lưu trữ `damage_fee` dưới dạng số `DECIMAL(12, 2)` giúp bảo đảm tính chính xác tuyệt đối trong tính toán tiền tệ, đồng bộ trọn vẹn với quy trình nghiệp vụ thực tế.