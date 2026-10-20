from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException, status, Depends
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship

# --- DATABASE SETUP ---
DATABASE_URL = "sqlite:///./crm_leads.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- DATABASE MODELS ---
class Lead(Base):
    __tablename__ = "leads"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    phone = Column(String)
    assigned_to = Column(Integer, nullable=True) # ID của tư vấn viên được phân công

    assignments = relationship("AssignmentHistory", back_populates="lead")

class AssignmentHistory(Base):
    __tablename__ = "assignment_history"
    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"))
    assigned_by = Column(Integer) # ID của Quản lý đào tạo
    assigned_to = Column(Integer) # ID của Tư vấn viên nhận lead
    timestamp = Column(DateTime, default=datetime.utcnow)

    lead = relationship("Lead", back_populates="assignments")

Base.metadata.create_all(bind=engine)

# --- SCHEMAS (Pydantic) ---
class AssignLeadsRequest(BaseModel):
    lead_ids: List[int]        # Yêu cầu 1: Phân công một hoặc nhiều lead cùng lúc
    counselor_id: int          # ID tư vấn viên nhận lead
    manager_id: int            # ID quản lý thực hiện phân công

class LeadResponse(BaseModel):
    id: int
    name: str
    phone: str
    assigned_to: Optional[int]

    class Config:
        from_attributes = True

# --- DEPENDENCY ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI(title="Lead Management Module")

# --- API ENDPOINTS ---

# 1. Phân công 1 hoặc nhiều Lead & Ghi lại lịch sử chuyển giao
@app.post("/leads/assign", status_code=status.HTTP_200_OK)
def assign_leads(req: AssignLeadsRequest, db: Session = Depends(get_db)):
    leads = db.query(Lead).filter(Lead.id.in_(req.lead_ids)).all()
    
    if not leads:
        raise HTTPException(status_code=404, detail="Không tìm thấy lead nào phù hợp.")
    
    for lead in leads:
        # Cập nhật phân công mới
        lead.assigned_to = req.counselor_id
        
        # Yêu cầu 3: Ghi lịch sử chuyển giao
        history_entry = AssignmentHistory(
            lead_id=lead.id,
            assigned_by=req.manager_id,
            assigned_to=req.counselor_id
        )
        db.add(history_entry)
        
    db.commit()
    return {"message": f"Đã phân công thành công {len(leads)} lead cho tư vấn viên {req.counselor_id}."}


# 2. Yêu cầu 2: Tư vấn viên chỉ nhìn thấy lead được giao cho mình
@app.get("/leads/my-assigned", response_model=List[LeadResponse])
def get_my_leads(counselor_id: int, db: Session = Depends(get_db)):
    leads = db.query(Lead).filter(Lead.assigned_to == counselor_id).all()
    return leads


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000)
    from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

app = FastAPI(title="Course Document Management API")


# --- Database Models (Mô phỏng cơ sở dữ liệu) ---
class Document(BaseModel):
    id: int
    title: str
    file_url: str
    subject_id: str
    subject_name: str
    lesson_id: int
    lesson_name: str
    lesson_date: datetime  # Ngày giờ diễn ra buổi học
    is_unlocked_early: bool = False  # Cờ đánh dấu giảng viên mở sớm hay chưa


# Dữ liệu giả lập (Mock Data)
MOCK_DOCUMENTS: List[Document] = [
    # Môn: Python Cơ Bản
    Document(
        id=1,
        title="Slide Buổi 1: Giới thiệu Python",
        file_url="https://storage.example.com/docs/python_b1.pdf",
        subject_id="PY101",
        subject_name="Python Cơ Bản",
        lesson_id=1,
        lesson_name="Buổi 1: Tổng quan & Cú pháp",
        lesson_date=datetime(2023, 10, 1, 18, 30),
        is_unlocked_early=False,
    ),
    Document(
        id=2,
        title="Bài tập Buổi 2: Cấu trúc điều kiện",
        file_url="https://storage.example.com/docs/python_b2.pdf",
        subject_id="PY101",
        subject_name="Python Cơ Bản",
        lesson_id=2,
        lesson_name="Buổi 2: Điều kiện & Vòng lặp",
        lesson_date=datetime(2023, 10, 5, 18, 30),
        is_unlocked_early=False,
    ),
    # Buổi học trong tương lai nhưng ĐÃ ĐƯỢC GIẢNG VIÊN MỞ SỚM
    Document(
        id=3,
        title="Tài liệu đọc trước Buổi 3: Hàm & Module",
        file_url="https://storage.example.com/docs/python_b3_preview.pdf",
        subject_id="PY101",
        subject_name="Python Cơ Bản",
        lesson_id=3,
        lesson_name="Buổi 3: Hàm trong Python",
        lesson_date=datetime(2030, 1, 1, 18, 30),  # Tương lai
        is_unlocked_early=True,  # Giảng viên cho phép xem trước
    ),
    # Buổi học trong tương lai và CHƯA ĐƯỢC MỞ (Sẽ không hiển thị)
    Document(
        id=4,
        title="Đề thi giữa kỳ",
        file_url="https://storage.example.com/docs/python_exam.pdf",
        subject_id="PY101",
        subject_name="Python Cơ Bản",
        lesson_id=4,
        lesson_name="Buổi 4: Kiểm tra",
        lesson_date=datetime(2030, 1, 10, 18, 30),  # Tương lai
        is_unlocked_early=False,  # Chưa mở -> Ẩn
    ),
]


# --- Helper Function Check Điều Kiện Hiển Thị ---
def is_document_accessible(doc: Document) -> bool:
    """Kiểm tra tài liệu có được phép hiển thị/tải hay không.

    Điều kiện: Buổi học đã diễn ra (lesson_date <= hiện tại) OR được mở sớm
    (is_unlocked_early == True)
    """
    now = datetime.now()
    return doc.lesson_date <= now or doc.is_unlocked_early


# --- API Endpoints ---


@app.get("/api/v1/documents", summary="Lấy danh sách tài liệu gom nhóm theo môn & buổi học")
def get_student_documents(subject_id: Optional[str] = Query(None, description="Lọc theo mã môn học")):
    """Lấy toàn bộ tài liệu hợp lệ mà học viên được phép xem/tải, nhóm theo Môn học và Buổi học."""
    now = datetime.now()

    # 1. Lọc tài liệu theo điều kiện nghiệp vụ
    accessible_docs = [doc for doc in MOCK_DOCUMENTS if is_document_accessible(doc)]

    # Lọc theo subject_id nếu có truyền tham số
    if subject_id:
        accessible_docs = [doc for doc in accessible_docs if doc.subject_id == subject_id]

    # 2. Nhóm tài liệu theo Môn học -> Buổi học
    grouped_data = {}
    for doc in accessible_docs:
        s_id = doc.subject_id
        l_id = doc.lesson_id

        if s_id not in grouped_data:
            grouped_data[s_id] = {"subject_id": doc.subject_id, "subject_name": doc.subject_name, "lessons": {}}

        if l_id not in grouped_data[s_id]["lessons"]:
            grouped_data[s_id]["lessons"][l_id] = {
                "lesson_id": doc.lesson_id,
                "lesson_name": doc.lesson_name,
                "lesson_date": doc.lesson_date,
                "documents": [],
            }

        grouped_data[s_id]["lessons"][l_id]["documents"].append(
            {"id": doc.id, "title": doc.title, "file_url": doc.file_url}
        )

    # Chuyển đổi cấu trúc dict thành list để trả về JSON sạch sẽ
    result = []
    for s_data in grouped_data.values():
        s_data["lessons"] = list(s_data["lessons"].values())
        result.append(s_data)

    return {"status": "success", "data": result}


@app.get("/api/v1/documents/{document_id}/download", summary="Tải tài liệu buổi học")
def download_document(document_id: int):
    """API hỗ trợ xem/tải tài liệu dựa trên ID."""
    doc = next((d for d in MOCK_DOCUMENTS if d.id == document_id), None)

    if not doc:
        raise HTTPException(status_code=404, detail="Tài liệu không tồn tại.")

    if not is_document_accessible(doc):
        raise HTTPException(
            status_code=403, detail="Tài liệu chưa được mở. Vui lòng đợi buổi học diễn ra hoặc giảng viên mở sớm."
        )

    return {"status": "success", "download_url": doc.file_url, "title": doc.title}