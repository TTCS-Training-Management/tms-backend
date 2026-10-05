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