# SCRUM-76 - Sinh thời khóa biểu tự động theo mẫu lặp

## Chạy trên Windows / VS Code

1. Giải nén thư mục dự án.
2. Mở thư mục `scrum76_auto_schedule` bằng VS Code.
3. Mở Terminal và chạy:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

4. Mở http://127.0.0.1:5000

## Chức năng
- Khai báo ngày nghỉ và mô tả.
- Chọn ngày bắt đầu, thứ học, ca học, số buổi.
- Tạo lịch lặp, bỏ qua ngày nghỉ đã khai báo.
- Xem trước rồi mới xác nhận lưu.
- Gắn một bài học vào từng buổi (nhập đúng số dòng bằng tổng số buổi).
- Lưu lịch trong SQLite `schedule.db`.

## Lưu ý
Đây là bản demo độc lập để minh họa SCRUM-76. Trước khi tích hợp vào TMS thật, cần nối với mô hình môn học/bài học/lớp học sẵn có của nhóm và xác nhận quy tắc lịch/ca học với trưởng nhóm.
