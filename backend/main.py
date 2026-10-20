import math
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from backend.database import get_db, Base, engine
from backend.models import ClassEntity, Program, Instructor
from backend.seed import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi tạo bảng và dữ liệu mẫu nếu chưa có
    init_db()
    yield


app = FastAPI(title="Training Management API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/meta")
def get_metadata(db: Session = Depends(get_db)):
    """Trả về danh sách chương trình và giảng viên từ database"""
    programs = db.query(Program).order_by(Program.id).all()
    instructors = db.query(Instructor).order_by(Instructor.id).all()
    return {
        "programs": [{"id": p.id, "name": p.name} for p in programs],
        "instructors": [{"id": i.id, "name": i.name} for i in instructors],
    }


@app.get("/api/classes/stats")
def get_stats(db: Session = Depends(get_db)):
    """Thống kê chỉ số nhanh từ database thật"""
    total_classes = db.query(func.count(ClassEntity.id)).scalar() or 0
    active_classes = (
        db.query(func.count(ClassEntity.id))
        .filter(ClassEntity.status == "Đang học")
        .scalar()
        or 0
    )
    upcoming_classes = (
        db.query(func.count(ClassEntity.id))
        .filter(ClassEntity.status == "Sắp khai giảng")
        .scalar()
        or 0
    )
    total_students = (
        db.query(func.sum(ClassEntity.current_students)).scalar() or 0
    )

    return {
        "total_classes": total_classes,
        "active_classes": active_classes,
        "total_students": total_students,
        "upcoming_classes": upcoming_classes,
    }


@app.get("/api/classes")
def get_classes(
    status: Optional[str] = Query(None, description="Trạng thái lớp"),
    program_id: Optional[int] = Query(None, description="ID chương trình"),
    instructor_id: Optional[int] = Query(None, description="ID giảng viên"),
    start_date: Optional[str] = Query(None, description="Từ ngày (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Đến ngày (YYYY-MM-DD)"),
    page: int = Query(1, ge=1, description="Số trang hiện tại (bắt đầu từ 1)"),
    page_size: int = Query(5, ge=1, le=100, description="Số dòng trên mỗi trang"),
    db: Session = Depends(get_db),
):
    """
    Truy vấn danh sách lớp từ database hỗ trợ:
    - Kết hợp nhiều bộ lọc (status, program_id, instructor_id, khoảng thời gian)
    - Xóa bộ lọc (khi không truyền query params)
    - Phân trang (page, page_size, total, total_pages)
    """
    query = (
        db.query(ClassEntity)
        .options(
            joinedload(ClassEntity.program),
            joinedload(ClassEntity.instructor),
        )
    )

    # 1. Bộ lọc trạng thái
    if status:
        query = query.filter(ClassEntity.status == status)

    # 2. Bộ lọc chương trình
    if program_id is not None:
        query = query.filter(ClassEntity.program_id == program_id)

    # 3. Bộ lọc giảng viên
    if instructor_id is not None:
        query = query.filter(ClassEntity.instructor_id == instructor_id)

    # 4. Bộ lọc thời gian: Lớp bắt đầu từ start_date và kết thúc trước end_date
    if start_date:
        query = query.filter(ClassEntity.start_date >= start_date)
    if end_date:
        query = query.filter(ClassEntity.end_date <= end_date)

    # Tổng số bản ghi thỏa mãn điều kiện lọc
    total = query.count()

    # Tính tổng số trang
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    # Phân trang
    offset = (page - 1) * page_size
    records = query.order_by(ClassEntity.id).offset(offset).limit(page_size).all()

    items = []
    for r in records:
        progress = (
            round((r.completed_sessions / r.total_sessions) * 100)
            if r.total_sessions > 0
            else 0
        )
        items.append({
            "id": r.id,
            "name": r.name,
            "program_id": r.program_id,
            "program": r.program.name if r.program else "",
            "instructor_id": r.instructor_id,
            "instructor": r.instructor.name if r.instructor else "",
            "status": r.status,
            "start_date": r.start_date,
            "end_date": r.end_date,
            "current_students": r.current_students,
            "max_students": r.max_students,
            "completed_sessions": r.completed_sessions,
            "total_sessions": r.total_sessions,
            "progress": progress,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }
