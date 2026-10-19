# TMS Backend API - Module Quản Lý Nộp Bài (SCRUM-91)

Backend FastAPI phục vụ quản lý bài nộp, lịch sử phiên bản, chấm bài và mở lại bài.

## Các chức năng chính (SCRUM-91)
1. **POST `/api/submissions`**: Học viên nộp bài / nộp lại bài. Tự động đánh số phiên bản (v1, v2, v3...), lưu trữ tệp vật lý độc lập không ghi đè, chặn nộp lại khi bài đã chấm (`403 Forbidden`).
2. **GET `/api/submissions`**: Xem danh sách toàn bộ các phiên bản đã nộp của học viên theo thứ tự mới nhất -> cũ nhất.
3. **GET `/api/submissions/{id}/download`**: Tải về tệp bài làm của phiên bản tương ứng.
4. **POST `/api/submissions/grade`**: Giảng viên đánh dấu đã chấm (khóa quyền nộp lại của học viên).
5. **POST `/api/submissions/reopen`**: Giảng viên mở lại bài đã chấm để học viên sửa và nộp lại phiên bản mới.

## Cài đặt & Chạy
```powershell
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000
```
Swagger UI: `http://127.0.0.1:8000/docs`
