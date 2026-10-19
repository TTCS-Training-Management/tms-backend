import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, Text
from app.db.base import Base

class LeadStatus(str, enum.Enum):
    NEW = "NEW"                 # Mới
    CONTACTED = "CONTACTED"     # Đã liên hệ
    CONSULTING = "CONSULTING"   # Đang tư vấn
    TRIAL = "TRIAL"             # Hẹn học thử
    CLOSED = "CLOSED"           # Chốt
    REJECTED = "REJECTED"       # Từ chối

class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(255), nullable=False)
    phone_number = Column(String(20), nullable=False)
    course_interest = Column(String(255), nullable=True)
    status = Column(Enum(LeadStatus), default=LeadStatus.NEW)
    reject_reason = Column(String(255), nullable=True) # Lý do từ chối (bắt buộc khi status = REJECTED)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class LeadActivityLog(Base):
    __tablename__ = "lead_activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    user_id = Column(Integer, nullable=True) # ID Tư vấn viên thực hiện
    from_status = Column(String(50), nullable=False)
    to_status = Column(String(50), nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)