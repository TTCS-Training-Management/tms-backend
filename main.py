from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from enum import Enum

app = FastAPI(
    title="TMS Backend API",
    description="API hệ thống Quản lý Đào tạo - Task SCRUM-66",
    version="1.0.0"
)

# --- 1. ENUMS & MODELS ---

class RoleEnum(str, Enum):
    MANAGER = "MANAGER"      # Quản lý đào tạo
    LECTURER = "LECTURER"    # Giảng viên
    TA = "TA"                # Trợ giảng
    STUDENT = "STUDENT"      # Học viên

class User(BaseModel):
    id: int
    name: str
    email: str
    role: RoleEnum

class SubjectAssignmentRequest(BaseModel):
    class_id: int
    subject_id: int
    lecturer_id: int              # 1 Giảng viên chính
    ta_ids: List[int] = []        # Danh sách nhiều Trợ giảng

class SubjectAssignmentResponse(BaseModel):
    class_id: int
    subject_id: int
    lecturer: User
    assistants: List[User]

# --- 2. GIẢ LẬP CƠ SỞ DỮ LIỆU (MOCK DATA) ---

fake_users_db = [
    User(id=1, name="Nguyễn Văn Quản Lý", email="quanly@tms.edu.vn", role=RoleEnum.MANAGER),
    User(id=2, name="Trần Thị Giảng Viên A", email="gva@tms.edu.vn", role=RoleEnum.LECTURER),
    User(id=3, name="Lê Văn Giảng Viên B", email="gvb@tms.edu.vn", role=RoleEnum.LECTURER),
    User(id=4, name="Phạm Văn Trợ Giảng 1", email="ta1@tms.edu.vn", role=RoleEnum.TA),
    User(id=5, name="Hoàng Thị Trợ Giảng 2", email="ta2@tms.edu.vn", role=RoleEnum.TA),
]

fake_assignments_db = {}


# --- 3. API ENDPOINTS CHO SCRUM-66 ---

@app.get("/")
def read_root():
    return {"message": "TMS Backend API - SCRUM-66 Assignment Module Operational"}


@app.get("/api/v1/users/eligible", response_model=List[User])
def get_eligible_instructors(role: RoleEnum):
    """
    Yêu cầu Jira: Chỉ tài khoản có vai trò tương ứng mới hiện trong danh sách chọn.
    """
    if role not in [RoleEnum.LECTURER, RoleEnum.TA]:
        raise HTTPException(
            status_code=400, 
            detail="Chỉ có thể lấy danh sách Giảng viên (LECTURER) hoặc Trợ giảng (TA)"
        )
    return [user for user in fake_users_db if user.role == role]


@app.post("/api/v1/assignments", response_model=SubjectAssignmentResponse, status_code=status.HTTP_201_CREATED)
def assign_instructors_to_subject(payload: SubjectAssignmentRequest):
    """
    Yêu cầu Jira: Mỗi môn trong lớp có 1 giảng viên chính và nhiều trợ giảng.
    """
    lecturer = next((u for u in fake_users_db if u.id == payload.lecturer_id), None)
    if not lecturer or lecturer.role != RoleEnum.LECTURER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Giảng viên chính không hợp lệ hoặc không có vai trò LECTURER"
        )

    assistants = []
    for ta_id in payload.ta_ids:
        ta = next((u for u in fake_users_db if u.id == ta_id), None)
        if not ta or ta.role != RoleEnum.TA:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail=f"Trợ giảng ID {ta_id} không hợp lệ hoặc không có vai trò TA"
            )
        assistants.append(ta)

    key = f"{payload.class_id}_{payload.subject_id}"
    assignment_data = {
        "class_id": payload.class_id,
        "subject_id": payload.subject_id,
        "lecturer": lecturer,
        "assistants": assistants
    }
    fake_assignments_db[key] = assignment_data

    return assignment_data


@app.get("/api/v1/instructors/{instructor_id}/classes", response_model=List[SubjectAssignmentResponse])
def get_assigned_classes_for_instructor(instructor_id: int):
    """
    Yêu cầu Jira: Phân công xong, giảng viên thấy lớp trong danh sách lớp của mình.
    """
    result = []
    for assignment in fake_assignments_db.values():
        is_lecturer = assignment["lecturer"].id == instructor_id
        is_ta = any(ta.id == instructor_id for ta in assignment["assistants"])
        if is_lecturer or is_ta:
            result.append(assignment)
    return result