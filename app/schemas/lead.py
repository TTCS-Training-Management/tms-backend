from pydantic import BaseModel, Field
from typing import Optional
from app.models.lead import LeadStatus

class UpdateLeadStatusRequest(BaseModel):
    status: LeadStatus = Field(..., description="Trạng thái mới của lead")
    reject_reason: Optional[str] = Field(None, description="Lý do từ chối (bắt buộc nếu status là REJECTED)")