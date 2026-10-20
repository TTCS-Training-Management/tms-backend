from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from datetime import datetime
from app.database import Base # Hoặc đường dẫn import Base tương ứng với các model khác như user.py trong project của bạn

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="ID người thực hiện thao tác")
    action = Column(String(50), nullable=False, comment="Hành động: UPDATE, DELETE,...")
    target_type = Column(String(50), nullable=False, comment="Loại dữ liệu nhạy cảm: score, tuition, role")
    target_id = Column(Integer, nullable=False, comment="ID của bản ghi bị thay đổi")
    old_value = Column(Text, nullable=True, comment="Giá trị trước khi sửa")
    new_value = Column(Text, nullable=True, comment="Giá trị sau khi sửa")
    timestamp = Column(DateTime, default=datetime.utcnow, comment="Thời điểm thực hiện")