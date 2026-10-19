import math
import os
import re
import shutil
import sqlite3
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Header, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
try:
    from sqlalchemy import func
    from sqlalchemy.orm import Session, joinedload
    from backend.database import get_db, Base, engine
    from backend.models import ClassEntity, Program, Instructor
    from backend.seed import init_db as init_sqlalchemy_db
    HAS_SQLALCHEMY = True
except Exception:
    HAS_SQLALCHEMY = False

# Đường dẫn lưu trữ SQLite và tệp bài nộp
DATABASE_FILE = Path(__file__).resolve().parent / "submissions.db"
UPLOAD_DIR = Path(__file__).resolve().parent / "submissions"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def get_sqlite_conn():
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_sqlite_db():
    with get_sqlite_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                assignment_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                submitted_at TEXT NOT NULL,
                status TEXT NOT NULL
            )
        """)


init_sqlite_db()


def get_latest_submission(conn, student_id: str, assignment_id: str):
    row = conn.execute("""
        SELECT * FROM submissions
        WHERE student_id = ? AND assignment_id = ?
        ORDER BY version DESC LIMIT 1
    """, (student_id, assignment_id)).fetchone()
    return dict(row) if row else None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi tạo SQLite cho SCRUM-91
    init_sqlite_db()
    # Khởi tạo SQLAlchemy cho SCRUM-65 (nếu có cấu hình)
    if HAS_SQLALCHEMY:
        try:
            init_sqlalchemy_db()
        except Exception:
            pass
    yield


app = FastAPI(title="TMS Backend API & SCRUM-91 Quản Lý Bài Nộp", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {
        "message": "TMS Backend API dang hoat dong!",
        "module": "SCRUM-91 - Quan Ly Lich Su Nop Bai",
        "status": "online"
    }


# ==============================================================================
# SCRUM-91: NỘP BÀI, QUẢN LÝ PHIÊN BẢN, KHÓA BÀI ĐÃ CHẤM & PHÂN QUYỀN GIẢNG VIÊN
# ==============================================================================

@app.post("/api/submissions", status_code=201)
async def submit_assignment(
    student_id: str = Query(...),
    assignment_id: str = Query(...),
    file: UploadFile = File(...),
    x_user_role: Optional[str] = Header(default="student")
):
    """
    Học viên nộp bài lần đầu hoặc nộp lại:
    - Lưu từng lần nộp thành một bản ghi riêng biệt.
    - Lưu tệp vật lý độc lập kèm mã phiên bản và timestamp, không ghi đè bài cũ.
    - Chặn nộp lại nếu bài đã chấm (trừ khi được giảng viên mở lại).
    - Phân quyền: Chỉ học viên mới được nộp bài.
    """
    if x_user_role == "teacher":
        raise HTTPException(
            status_code=403,
            detail="Tài khoản Giảng viên không thể nộp bài. Vui lòng chuyển sang vai trò Học viên."
        )

    with get_sqlite_conn() as conn:
        latest = get_latest_submission(conn, student_id, assignment_id)

        # Khóa nộp bài sau khi chấm
        if latest and latest["status"] == "graded":
            raise HTTPException(
                status_code=403,
                detail=f"Bài nộp (Phiên bản {latest['version']}) đã được chấm và đang bị KHÓA. Bạn không thể tự ý nộp lại trừ khi Giảng viên bấm 'Mở lại bài'."
            )

        # Tự động tính số phiên bản kế tiếp
        version = (latest["version"] + 1) if latest else 1

        # Lưu tệp vật lý độc lập không ghi đè
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{student_id}_{assignment_id}_v{version}_{timestamp_str}_{file.filename}"
        saved_path = UPLOAD_DIR / safe_filename

        with saved_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        submitted_at = datetime.now().isoformat()
        status = "submitted"

        conn.execute("""
            INSERT INTO submissions (student_id, assignment_id, version, filename, file_path, submitted_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (student_id, assignment_id, version, file.filename, str(saved_path), submitted_at, status))

        return {
            "message": f"Nộp bài thành công! Đã tạo Phiên bản {version}.",
            "version": version,
            "filename": file.filename,
            "submitted_at": submitted_at,
            "status": status
        }


@app.get("/api/submissions")
def get_submission_history(student_id: str = Query(...), assignment_id: str = Query(...)):
    """
    Xem lịch sử các phiên bản nộp bài:
    - Trả về danh sách tất cả các phiên bản đã nộp.
    - Sắp xếp theo phiên bản mới nhất ở trên cùng.
    """
    with get_sqlite_conn() as conn:
        rows = conn.execute("""
            SELECT id, student_id, assignment_id, version, filename, submitted_at, status
            FROM submissions
            WHERE student_id = ? AND assignment_id = ?
            ORDER BY version DESC
        """, (student_id, assignment_id)).fetchall()
        return [dict(row) for row in rows]


@app.get("/api/submissions/{submission_id}/download")
def download_submission(submission_id: int):
    """
    Tải về tệp bài làm của từng phiên bản cụ thể
    """
    with get_sqlite_conn() as conn:
        row = conn.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Không tìm thấy bài nộp")
        file_path = Path(row["file_path"])
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Tệp bài nộp không tồn tại trên máy chủ")
        return FileResponse(
            path=str(file_path),
            filename=row["filename"],
            media_type="application/octet-stream"
        )


class GradeRequest(BaseModel):
    student_id: str
    assignment_id: str


@app.post("/api/submissions/grade")
def grade_assignment(
    data: GradeRequest,
    x_user_role: Optional[str] = Header(default="student")
):
    """
    Giảng viên đánh dấu phiên bản mới nhất là đã chấm (khóa nộp lại)
    """
    if x_user_role != "teacher":
        raise HTTPException(
            status_code=403,
            detail="Từ chối truy cập: Chỉ tài khoản GIẢNG VIÊN mới có quyền đánh dấu đã chấm bài!"
        )

    with get_sqlite_conn() as conn:
        latest = get_latest_submission(conn, data.student_id, data.assignment_id)
        if not latest:
            raise HTTPException(status_code=404, detail="Học viên này chưa nộp bài nào")
        if latest["status"] == "graded":
            raise HTTPException(status_code=400, detail="Phiên bản mới nhất đã ở trạng thái đã chấm")

        conn.execute(
            "UPDATE submissions SET status = 'graded' WHERE id = ?",
            (latest["id"],)
        )
        return {
            "message": f"Đã đánh dấu ĐÃ CHẤM cho Phiên bản {latest['version']}. Học viên sẽ bị khóa nộp lại.",
            "version": latest["version"]
        }


@app.post("/api/submissions/reopen")
def reopen_assignment(
    data: GradeRequest,
    x_user_role: Optional[str] = Header(default="student")
):
    """
    Giảng viên mở lại bài đã chấm để học viên sửa và nộp lại phiên bản mới
    """
    if x_user_role != "teacher":
        raise HTTPException(
            status_code=403,
            detail="Từ chối truy cập: Chỉ tài khoản GIẢNG VIÊN mới có quyền mở lại bài nộp!"
        )

    with get_sqlite_conn() as conn:
        latest = get_latest_submission(conn, data.student_id, data.assignment_id)
        if not latest:
            raise HTTPException(status_code=404, detail="Học viên này chưa nộp bài nào")
        if latest["status"] != "graded":
            raise HTTPException(
                status_code=400,
                detail=f"Chỉ có thể mở lại bài đã được chấm (Hiện tại trạng thái là: {latest['status']})"
            )

        conn.execute(
            "UPDATE submissions SET status = 'reopened' WHERE id = ?",
            (latest["id"],)
        )
        return {
            "message": f"Đã MỞ LẠI Phiên bản {latest['version']}. Học viên hiện có thể nộp phiên bản tiếp theo.",
            "version": latest["version"]
        }


# ==============================================================================
# SCRUM-65: CÁC API QUẢN LÝ LỚP HỌC (NẾU DÙNG THÊM VỚI SQLALCHEMY)
# ==============================================================================

if HAS_SQLALCHEMY:
    @app.get("/api/meta")
    def get_metadata(db: Session = Depends(get_db)):
        programs = db.query(Program).order_by(Program.id).all()
        instructors = db.query(Instructor).order_by(Instructor.id).all()
        return {
            "programs": [{"id": p.id, "name": p.name} for p in programs],
            "instructors": [{"id": i.id, "name": i.name} for i in instructors],
        }

    @app.get("/api/classes/stats")
    def get_stats(db: Session = Depends(get_db)):
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
        status: Optional[str] = Query(None),
        program_id: Optional[int] = Query(None),
        instructor_id: Optional[int] = Query(None),
        start_date: Optional[str] = Query(None),
        end_date: Optional[str] = Query(None),
        page: int = Query(1, ge=1),
        page_size: int = Query(5, ge=1, le=100),
        db: Session = Depends(get_db),
    ):
        query = db.query(ClassEntity).options(
            joinedload(ClassEntity.program),
            joinedload(ClassEntity.instructor),
        )
        if status:
            query = query.filter(ClassEntity.status == status)
        if program_id is not None:
            query = query.filter(ClassEntity.program_id == program_id)
        if instructor_id is not None:
            query = query.filter(ClassEntity.instructor_id == instructor_id)
        if start_date:
            query = query.filter(ClassEntity.start_date >= start_date)
        if end_date:
            query = query.filter(ClassEntity.end_date <= end_date)

        total = query.count()
        total_pages = math.ceil(total / page_size) if total > 0 else 1
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
