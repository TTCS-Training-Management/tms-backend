from fastapi import APIRouter, HTTPException, status
from app.models.user import LoginRequest, TokenResponse
from app.security.jwt import create_access_token
from app.services.auth_service import authenticate_user

router = APIRouter()


@router.post("/login", response_model=TokenResponse, summary="Đăng nhập lấy JWT Bearer token")
def login(data: LoginRequest):
    """
    API Đăng nhập:
    - Nhận username và password
    - Kiểm tra thông tin đăng nhập
    - Trả về access_token định dạng Bearer và vai trò (USER / ADMIN)
    """
    user = authenticate_user(data.username, data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sai username hoặc password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Đưa username và role vào JWT claims
    token = create_access_token({
        "sub": user["username"],
        "role": user["role"]
    })

    return {
        "access_token": token,
        "token_type": "bearer"
    }
