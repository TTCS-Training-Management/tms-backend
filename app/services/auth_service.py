from passlib.context import CryptContext
from typing import Optional, Dict

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Danh sách người dùng mẫu (Database mô phỏng cho bước 1 - 8)
# Sau này sẽ thay thế bằng bảng users trong Database (SQLAlchemy)
MOCK_USERS_DB: Dict[str, dict] = {
    "admin": {
        "username": "admin",
        "password": "123456",  # Có thể dùng bcrypt hoặc so sánh plaintext demo
        "role": "ADMIN"
    },
    "user1": {
        "username": "user1",
        "password": "123456",
        "role": "USER"
    }
}


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def authenticate_user(username: str, password: str) -> Optional[dict]:
    user = MOCK_USERS_DB.get(username)
    if not user:
        return None
    # Hỗ trợ mật khẩu demo (hoặc bcrypt khi nâng cấp)
    if user["password"] != password:
        return None
    return user
