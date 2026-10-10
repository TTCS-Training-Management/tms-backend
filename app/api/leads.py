from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.models.lead import Lead, LeadStatus, LeadActivityLog
from app.schemas.lead import UpdateLeadStatusRequest

router = APIRouter(prefix="/api/leads", tags=["Leads Kanban"])

# Giả lập hàm get_db lấy session database tùy theo cấu trúc dự án của bạn 
# (Nếu dự án của bạn đã có file dependency db riêng, hãy thay thế dòng import cho phù hợp)
from app.db.session import get_db 

@router.get("/kanban")
def get_kanban_board(db: Session = Depends(get_db)):
    """
    API lấy danh sách lead phân theo 6 cột phễu kèm theo số lượng lead (count) của từng cột.
    """
    kanban_data = {}
    for s in LeadStatus:
        leads = db.query(Lead).filter(Lead.status == s).all()
        kanban_data[s.value] = {
            "count": len(leads),
            "leads": leads
        }
    return kanban_data

@router.patch("/{lead_id}/status")
def update_lead_status(
    lead_id: int, 
    payload: UpdateLeadStatusRequest, 
    db: Session = Depends(get_db)
):
    """
    API kéo thả đổi trạng thái Lead:
    - Ghi nhận lịch sử vào bảng audit log (LeadActivityLog).
    - Bắt buộc chọn lý do (reject_reason) nếu chuyển sang trạng thái REJECTED (Từ chối).
    """
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Không tìm thấy Lead trong hệ thống"
        )

    # Ràng buộc: Chuyển sang Từ chối bắt buộc phải chọn lý do
    if payload.status == LeadStatus.REJECTED and not payload.reject_reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bắt buộc phải chọn lý do khi chuyển sang trạng thái Từ chối."
        )

    old_status = lead.status.value if hasattr(lead.status, 'value') else lead.status
    new_status = payload.status.value

    # Cập nhật trạng thái mới
    lead.status = payload.status
    if payload.status == LeadStatus.REJECTED:
        lead.reject_reason = payload.reject_reason
    else:
        # Nếu chuyển đi trạng thái khác thì có thể reset hoặc giữ nguyên tùy ý
        pass

    # Ghi nhật ký hệ thống (Audit Log) cho mỗi lần đổi trạng thái
    activity_log = LeadActivityLog(
        lead_id=lead.id,
        user_id=1, # Tạm gán ID user hiện tại, có thể lấy từ current_user trong hệ thống auth
        from_status=old_status,
        to_status=new_status,
        note=f"Chuyển trạng thái từ {old_status} sang {new_status}" + (f" (Lý do: {payload.reject_reason})" if payload.reject_reason else "")
    )
    
    db.add(activity_log)
    db.commit()
    db.refresh(lead)

    return {
        "message": "Cập nhật trạng thái Lead thành công",
        "lead_id": lead.id,
        "new_status": lead.status,
        "reject_reason": lead.reject_reason
    }