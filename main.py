from fastapi import FastAPI, APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Hello TMS Backend"}

# --- Phần phân bổ vai trò (UserRole) ---
router = APIRouter(
    prefix="/api/UserRole",
    tags=["UserRole"]
)

class AssignRoleRequest(BaseModel):
    user_id: str
    role_name: str

def verify_admin_role():
    pass

@router.post("/assign-role", dependencies=[Depends(verify_admin_role)])
async def assign_role(payload: AssignRoleRequest):
    return {"message": f"Đã gán vai trò {payload.role_name} cho người dùng {payload.user_id}"}

# Đăng ký router vào ứng dụng FastAPI
app.include_router(router)
