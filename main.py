from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import Boolean, DateTime, Integer, String, create_engine, inspect, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tms.db")
TOKEN_SECRET = os.getenv("TOKEN_SECRET", "tms-local-development-secret")
TOKEN_TTL_HOURS = 8
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
ALLOWED_ORIGINS = list({FRONTEND_URL, "http://localhost:5173", "http://localhost:5174", "http://127.0.0.1:5173", "http://127.0.0.1:5174"})

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(30), default="lecturer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


def validate_password_strength(password: str) -> str:
    if len(password) < 8:
        raise ValueError("Mật khẩu phải có ít nhất 8 ký tự")
    if not re.search(r"[a-z]", password):
        raise ValueError("Mật khẩu phải chứa ít nhất 1 chữ thường")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Mật khẩu phải chứa ít nhất 1 chữ hoa")
    if not re.search(r"\d", password):
        raise ValueError("Mật khẩu phải chứa ít nhất 1 chữ số")
    if not re.search(r"[^A-Za-z0-9]", password):
        raise ValueError("Mật khẩu phải chứa ít nhất 1 ký tự đặc biệt")
    return password


class LoginRequest(BaseModel):
    email: str
    password: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return validate_password_strength(value)


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return validate_password_strength(value)


class UserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: str
    password: str = Field(min_length=8)
    role: str = "lecturer"

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_strength(value)


class UserRoleUpdate(BaseModel):
    role: str


class UserUpdate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: str


reset_tokens: dict[str, tuple[str, datetime]] = {}
revoked_tokens: set[str] = set()
class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    role: str
    is_active: bool
    created_at: datetime


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, expected = stored_hash.split("$", 1)
    except ValueError:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000).hex()
    return hmac.compare_digest(actual, expected)


def encode_token(user: User) -> str:
    payload = {
        "sub": user.id,
        "role": user.role,
        "jti": secrets.token_urlsafe(18),
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS)).timestamp()),
    }
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
    signature = hmac.new(TOKEN_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{signature}"


def decode_token(token: str) -> dict:
    try:
        body, signature = token.split(".", 1)
        if token in revoked_tokens:
            raise ValueError
        expected = hmac.new(TOKEN_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        payload = json.loads(base64.urlsafe_b64decode(body.encode()))
        if payload["exp"] < datetime.now(timezone.utc).timestamp():
            raise ValueError
        return payload
    except (ValueError, KeyError, json.JSONDecodeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Phiên đăng nhập không hợp lệ")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


bearer = HTTPBearer(auto_error=False)
DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: DbSession,
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Vui lòng đăng nhập")
    payload = decode_token(credentials.credentials)
    user = db.get(User, payload["sub"])
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Tài khoản không hoạt động")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn không có quyền thực hiện thao tác này")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


def seed_database() -> None:
    Base.metadata.create_all(engine)
    existing_columns = {column["name"] for column in inspect(engine).get_columns("users")}
    with engine.begin() as connection:
        if "failed_login_attempts" not in existing_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER NOT NULL DEFAULT 0"))
        if "locked_until" not in existing_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN locked_until DATETIME NULL"))
    with SessionLocal() as db:
        if db.scalar(select(User).limit(1)) is not None:
            return
        db.add_all(
            [
                User(full_name="Quản trị viên TMS", email="admin@tms.local", password_hash=hash_password("Admin@123"), role="admin"),
                User(full_name="Nguyễn Văn Giảng", email="lecturer@tms.local", password_hash=hash_password("Lecturer@123"), role="lecturer"),
                User(full_name="Kế toán TMS", email="accountant@tms.local", password_hash=hash_password("Accountant@123"), role="accountant"),
            ]
        )
        db.commit()


def send_reset_email(email: str, token: str) -> bool:
    if not all((SMTP_HOST, SMTP_USER, SMTP_PASSWORD, SMTP_FROM)):
        return False
    message = EmailMessage()
    message["Subject"] = "Khôi phục mật khẩu TMS"
    message["From"] = SMTP_FROM
    message["To"] = email
    message.set_content(
        "Bạn vừa yêu cầu khôi phục mật khẩu TMS. "
        f"Mã khôi phục của bạn là: {token}\n"
        "Mã có hiệu lực trong 15 phút. Nếu không phải bạn, hãy bỏ qua email này."
    )
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(message)
    return True


app = FastAPI(title="TMS Training Management API", version="1.0.0", on_startup=[seed_database])
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "TMS Backend is running", "docs": "/docs"}


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/login", response_model=LoginResponse)
def login(request: LoginRequest, db: DbSession) -> LoginResponse:
    user = db.scalar(select(User).where(User.email == request.email.lower().strip()))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email hoặc mật khẩu không đúng")
    now = datetime.now(timezone.utc)
    locked_until = user.locked_until
    if locked_until is not None and locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    if locked_until is not None and locked_until > now:
        remaining_minutes = max(1, int((locked_until - now).total_seconds() // 60) + 1)
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=f"Tài khoản tạm khóa. Vui lòng thử lại sau {remaining_minutes} phút")
    if locked_until is not None and locked_until <= now:
        user.locked_until = None
        user.failed_login_attempts = 0
    if not verify_password(request.password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= 5:
            user.locked_until = now + timedelta(minutes=15)
            db.commit()
            raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="Tài khoản tạm khóa 15 phút sau 5 lần đăng nhập sai")
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email hoặc mật khẩu không đúng")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tài khoản đã bị khóa")
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()
    return LoginResponse(access_token=encode_token(user), user=user)


@app.get("/auth/me", response_model=UserResponse)
def me(user: CurrentUser) -> UserResponse:
    return user


@app.post("/auth/change-password")
def change_password(request: PasswordChangeRequest, user: CurrentUser, db: DbSession) -> dict[str, str]:
    if not verify_password(request.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mật khẩu hiện tại không đúng")
    user.password_hash = hash_password(request.new_password)
    db.commit()
    return {"message": "Đổi mật khẩu thành công"}


@app.post("/auth/forgot-password")
def forgot_password(request: ForgotPasswordRequest, db: DbSession) -> dict[str, str]:
    user = db.scalar(select(User).where(User.email == request.email.lower().strip()))
    if user is None:
        return {"message": "Nếu email tồn tại, hướng dẫn khôi phục đã được tạo"}
    token = secrets.token_urlsafe(32)
    reset_tokens[token] = (user.email, datetime.now(timezone.utc) + timedelta(minutes=30))
    if send_reset_email(user.email, token):
        return {"message": "Nếu email tồn tại, hướng dẫn khôi phục đã được gửi"}
    print(f"[DEV RESET TOKEN] email={user.email} token={token}")
    return {"message": "Nếu email tồn tại, hướng dẫn khôi phục đã được gửi. Chế độ demo: mã khôi phục đã được ghi log ở máy chủ."}


@app.post("/auth/reset-password")
def reset_password(request: ResetPasswordRequest, db: DbSession) -> dict[str, str]:
    record = reset_tokens.pop(request.token, None)
    if record is None or record[1] < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mã khôi phục không hợp lệ hoặc đã hết hạn")
    user = db.scalar(select(User).where(User.email == record[0]))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tài khoản")
    user.password_hash = hash_password(request.new_password)
    db.commit()
    return {"message": "Đặt lại mật khẩu thành công"}


@app.post("/auth/logout")
def logout(
    user: CurrentUser,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> dict[str, str]:
    if credentials is not None:
        revoked_tokens.add(credentials.credentials)
    return {"message": "Đã đăng xuất", "user": user.email}


@app.post("/auth/refresh", response_model=LoginResponse)
def refresh_session(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: DbSession,
) -> LoginResponse:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Phiên đăng nhập đã hết hạn")
    payload = decode_token(credentials.credentials)
    user = db.get(User, payload["sub"])
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Tài khoản không hoạt động")
    revoked_tokens.add(credentials.credentials)
    return LoginResponse(access_token=encode_token(user), user=user)


@app.get("/dashboard/summary")
def dashboard_summary(user: CurrentUser, db: DbSession) -> dict[str, int | str]:
    users = db.scalars(select(User)).all()
    return {
        "greeting": user.full_name,
        "total_users": len(users),
        "active_users": sum(item.is_active for item in users),
        "locked_users": sum(not item.is_active for item in users),
    }


@app.get("/users", response_model=list[UserResponse])
def list_users(_: AdminUser, db: DbSession, q: str | None = None, role: str | None = None, active: bool | None = None) -> list[UserResponse]:
    statement = select(User).order_by(User.created_at.desc())
    if q:
        statement = statement.where((User.full_name.ilike(f"%{q}%")) | (User.email.ilike(f"%{q}%")))
    if role:
        statement = statement.where(User.role == role)
    if active is not None:
        statement = statement.where(User.is_active == active)
    return list(db.scalars(statement).all())


@app.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(request: UserCreate, _: AdminUser, db: DbSession) -> UserResponse:
    email = request.email.lower().strip()
    if db.scalar(select(User).where(User.email == email)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email đã tồn tại")
    if request.role not in {"admin", "lecturer", "accountant"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Vai trò không hợp lệ")
    user = User(full_name=request.full_name, email=email, password_hash=hash_password(request.password), role=request.role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.patch("/users/{user_id}", response_model=UserResponse)
def update_user(user_id: int, request: UserUpdate, _: AdminUser, db: DbSession) -> UserResponse:
    user = db.get(User, user_id)
    email = request.email.lower().strip()
    duplicate = db.scalar(select(User).where(User.email == email, User.id != user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tài khoản")
    if duplicate is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email đã tồn tại")
    user.full_name = request.full_name
    user.email = email
    db.commit()
    db.refresh(user)
    return user


@app.patch("/users/{user_id}/status", response_model=UserResponse)
def update_user_status(user_id: int, _: AdminUser, db: DbSession) -> UserResponse:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tài khoản")
    user.is_active = not user.is_active
    db.commit()
    db.refresh(user)
    return user


@app.patch("/users/{user_id}/role", response_model=UserResponse)
def update_user_role(user_id: int, request: UserRoleUpdate, _: AdminUser, db: DbSession) -> UserResponse:
    if request.role not in {"admin", "lecturer", "accountant"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Vai trò không hợp lệ")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tài khoản")
    user.role = request.role
    db.commit()
    db.refresh(user)
    return user