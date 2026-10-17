from app.routers import auth
from app.routers import products
from app.api.attendance import router as attendance_router
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from openpyxl import Workbook
import io
from datetime import datetime
from app.api.deps import get_db

router = APIRouter(prefix="/api/attendance", tags=["Attendance Export"])

@router.get("/classes/{class_id}/export-excel")
def export_class_attendance_excel(class_id: int, db: Session = Depends(get_db)):
    # 1. Khởi tạo Workbook của openpyxl
    wb = Workbook()
    ws = wb.active
    ws.title = "Bảng Chuyên Cần"

    # 2. Xây dựng tiêu đề bảng (Cấu trúc ma trận: Mã HV, Họ tên, Các buổi học, Tổng kết)
    # (Bạn có thể tùy chỉnh query lấy danh sách buổi học thực tế của lớp từ database)
    headers = ["Mã Học Viên", "Họ và Tên", "Buổi 1", "Buổi 2", "Buổi 3", "Tổng Có Mặt", "Tổng Vắng"]
    ws.append(headers)

    # Dữ liệu mẫu minh họa (sau này bạn thay bằng query từ bảng điểm danh thực tế)
    sample_data = [
        ["HV001", "Nguyễn Văn A", "Có", "Có", "Vắng", 2, 1],
        ["HV002", "Trần Thị B", "Có", "Vắng", "Có", 2, 1],
    ]
    for row in sample_data:
        ws.append(row)

    # 3. Lưu file vào BytesIO stream để trả về cho client download trực tiếp
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    # 4. Đặt tên tệp chứa mã lớp và ngày xuất theo yêu cầu (Ví dụ: attendance_CLASS01_2026-10-17.xlsx)
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"attendance_class_{class_id}_{date_str}.xlsx"

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )