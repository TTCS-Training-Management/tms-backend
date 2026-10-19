import sys
from pathlib import Path

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from sqlalchemy.orm import Session
from backend.database import SessionLocal, engine, Base
from backend.models import Program, Instructor, ClassEntity


def init_db(db: Session = None):
    Base.metadata.create_all(bind=engine)

    close_session = False
    if db is None:
        db = SessionLocal()
        close_session = True

    try:
        # Nếu đã có dữ liệu thì không seed lại
        if db.query(ClassEntity).count() > 0:
            return

        # Seed Programs
        p_java = Program(id=1, name="Java")
        p_python = Program(id=2, name="Python")
        p_frontend = Program(id=3, name="Frontend")
        db.add_all([p_java, p_python, p_frontend])
        db.flush()

        # Seed Instructors
        ins_an = Instructor(id=1, name="Nguyễn Văn An")
        ins_binh = Instructor(id=2, name="Trần Văn Bình")
        ins_mai = Instructor(id=3, name="Lê Thị Mai")
        db.add_all([ins_an, ins_binh, ins_mai])
        db.flush()

        # Seed Classes đa dạng để test mọi bộ lọc và phân trang
        sample_classes = [
            ClassEntity(
                id=1,
                name="Lớp Java cơ bản",
                program_id=1,
                instructor_id=1,
                status="Đang học",
                start_date="2026-09-01",
                end_date="2026-12-01",
                current_students=20,
                max_students=30,
                completed_sessions=8,
                total_sessions=20,
            ),
            ClassEntity(
                id=2,
                name="Lớp Python cho AI",
                program_id=2,
                instructor_id=2,
                status="Đang học",
                start_date="2026-08-15",
                end_date="2026-11-30",
                current_students=25,
                max_students=25,
                completed_sessions=15,
                total_sessions=30,
            ),
            ClassEntity(
                id=3,
                name="Lớp React & Frontend nâng cao",
                program_id=3,
                instructor_id=1,
                status="Sắp khai giảng",
                start_date="2026-11-01",
                end_date="2027-01-15",
                current_students=12,
                max_students=25,
                completed_sessions=0,
                total_sessions=16,
            ),
            ClassEntity(
                id=4,
                name="Lớp Java nâng cao & Spring Boot",
                program_id=1,
                instructor_id=2,
                status="Đã kết thúc",
                start_date="2026-05-01",
                end_date="2026-08-01",
                current_students=28,
                max_students=30,
                completed_sessions=24,
                total_sessions=24,
            ),
            ClassEntity(
                id=5,
                name="Lớp Python cơ bản",
                program_id=2,
                instructor_id=1,
                status="Đang học",
                start_date="2026-09-15",
                end_date="2026-11-15",
                current_students=18,
                max_students=20,
                completed_sessions=5,
                total_sessions=15,
            ),
            ClassEntity(
                id=6,
                name="Lớp Frontend căn bản HTML/CSS/JS",
                program_id=3,
                instructor_id=2,
                status="Sắp khai giảng",
                start_date="2026-10-25",
                end_date="2026-12-25",
                current_students=8,
                max_students=20,
                completed_sessions=0,
                total_sessions=12,
            ),
            ClassEntity(
                id=7,
                name="Lớp Phân tích dữ liệu với Python",
                program_id=2,
                instructor_id=3,
                status="Đang học",
                start_date="2026-08-01",
                end_date="2026-11-01",
                current_students=22,
                max_students=25,
                completed_sessions=18,
                total_sessions=24,
            ),
            ClassEntity(
                id=8,
                name="Lớp Vue.js & Nuxt.js Thực chiến",
                program_id=3,
                instructor_id=3,
                status="Sắp khai giảng",
                start_date="2026-11-10",
                end_date="2027-01-20",
                current_students=15,
                max_students=25,
                completed_sessions=0,
                total_sessions=18,
            ),
            ClassEntity(
                id=9,
                name="Lớp Lập trình Web Fullstack Java",
                program_id=1,
                instructor_id=1,
                status="Đang học",
                start_date="2026-07-01",
                end_date="2026-11-01",
                current_students=30,
                max_students=30,
                completed_sessions=26,
                total_sessions=32,
            ),
            ClassEntity(
                id=10,
                name="Lớp Machine Learning chuyên sâu",
                program_id=2,
                instructor_id=3,
                status="Đã kết thúc",
                start_date="2026-04-10",
                end_date="2026-07-10",
                current_students=20,
                max_students=20,
                completed_sessions=20,
                total_sessions=20,
            ),
            ClassEntity(
                id=11,
                name="Lớp Microservices & Cloud với Java Spring",
                program_id=1,
                instructor_id=2,
                status="Sắp khai giảng",
                start_date="2026-10-15",
                end_date="2027-01-15",
                current_students=14,
                max_students=25,
                completed_sessions=0,
                total_sessions=18,
            ),
            ClassEntity(
                id=12,
                name="Lớp Cấu trúc dữ liệu & Thuật toán Java",
                program_id=1,
                instructor_id=2,
                status="Đang học",
                start_date="2026-08-20",
                end_date="2026-11-20",
                current_students=24,
                max_students=25,
                completed_sessions=12,
                total_sessions=20,
            ),
        ]
        db.add_all(sample_classes)
        db.commit()
    finally:
        if close_session:
            db.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
