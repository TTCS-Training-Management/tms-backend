from pydantic import BaseModel, Field
from typing import List

class EnrollmentCreate(BaseModel):
    student_ids: List[int] = Field(..., description="Danh sách ID học viên cần ghi danh vào lớp")