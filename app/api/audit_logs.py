from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from app.api.deps import get_db, get_current_user
from app.models.audit_log import AuditLog
from app.models.user import User

router = APIRouter(prefix="/api/audit-logs", tags=["Audit Logs"])

@router.get("/")
def get_audit_logs(
    user_id: Optional[int] = Query(None, description="Lọc theo ID người thực hiện"),
    target_type: Optional[str] = Query(None, description="Lọc theo loại đối tượng: score, tuition, role"),
    start_date: Optional[datetime] = Query(None, description="Từ thời điểm (YYYY-MM-DD HH:MM:SS)"),
    end_date: Optional[datetime] = Query(None, description="Đến thời điểm (YYYY-MM-DD HH:MM:SS)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(AuditLog)

    # Áp dụng các bộ lọc tra cứu theo yêu cầu
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if target_type:
        query = query.filter(AuditLog.target_type == target_type)
    if start_date:
        query = query.filter(AuditLog.timestamp >= start_date)
    if end_date:
        query = query.filter(AuditLog.timestamp <= end_date)

    logs = query.order_by(AuditLog.timestamp.desc()).all()
    return {
        "total": len(logs),
        "data": logs
    }