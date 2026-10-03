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
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, create_engine, inspect, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

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


# =========================================================
# SCRUM-41: QUẢN LÝ CHƯƠNG TRÌNH ĐÀO TẠO & LỚP HỌC (MODELS)
# =========================================================

class ChuongTrinhDaoTao(Base):
    __tablename__ = "chuong_trinh_dao_tao"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    ma_chuong_trinh: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    ten_chuong_trinh: Mapped[str] = mapped_column(String(200))
    mo_ta: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tong_thoi_luong: Mapped[int] = mapped_column(Integer)
    hoc_phi_chuan: Mapped[float] = mapped_column(Float)
    trang_thai: Mapped[str] = mapped_column(String(50), default="DANG_AP_DUNG")


class LopHoc(Base):
    __tablename__ = "lop_hoc"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    ten_lop: Mapped[str] = mapped_column(String(200))
    chuong_trinh_id: Mapped[int] = mapped_column(ForeignKey("chuong_trinh_dao_tao.id"))
    trang_thai: Mapped[str] = mapped_column(String(50), default="DANG_CHAY")

    chuong_trinh: Mapped[ChuongTrinhDaoTao] = relationship("ChuongTrinhDaoTao")


# =========================================================
# SCRUM-41: SCHEMAS
# =========================================================

class ChuongTrinhBase(BaseModel):
    ma_chuong_trinh: str
    ten_chuong_trinh: str
    mo_ta: str | None = None
    tong_thoi_luong: int
    hoc_phi_chuan: float
    trang_thai: str = "DANG_AP_DUNG"


class ChuongTrinhCreate(ChuongTrinhBase):
    pass


class ChuongTrinhResponse(ChuongTrinhBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class ChuongTrinhUpdate(BaseModel):
    ma_chuong_trinh: str | None = None
    ten_chuong_trinh: str | None = None
    mo_ta: str | None = None
    tong_thoi_luong: int | None = None
    hoc_phi_chuan: float | None = None
    trang_thai: str | None = None


class LopHocBase(BaseModel):
    ten_lop: str
    chuong_trinh_id: int
    trang_thai: str = "DANG_CHAY"


class LopHocCreate(LopHocBase):
    pass


class LopHocResponse(LopHocBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    chuong_trinh: ChuongTrinhResponse | None = None


Base.metadata.create_all(engine)
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


# =========================================================
# SCRUM-41: QUẢN LÝ CHƯƠNG TRÌNH ĐÀO TẠO & LỚP HỌC (ENDPOINTS)
# =========================================================

@app.post("/chuong-trinh", response_model=ChuongTrinhResponse, tags=["Quản lý đào tạo (SCRUM-41)"])
@app.post("/training-programs", response_model=ChuongTrinhResponse, tags=["Quản lý đào tạo (SCRUM-41)"])
def them_chuong_trinh(chuong_trinh: ChuongTrinhCreate, db: DbSession) -> ChuongTrinhResponse:
    # Kiểm tra mã chương trình duy nhất
    chuong_trinh_cu = db.scalar(select(ChuongTrinhDaoTao).where(ChuongTrinhDaoTao.ma_chuong_trinh == chuong_trinh.ma_chuong_trinh.strip()))
    if chuong_trinh_cu:
        raise HTTPException(status_code=400, detail="Mã chương trình đã tồn tại")

    chuong_trinh_moi = ChuongTrinhDaoTao(
        ma_chuong_trinh=chuong_trinh.ma_chuong_trinh.strip(),
        ten_chuong_trinh=chuong_trinh.ten_chuong_trinh.strip(),
        mo_ta=chuong_trinh.mo_ta,
        tong_thoi_luong=chuong_trinh.tong_thoi_luong,
        hoc_phi_chuan=chuong_trinh.hoc_phi_chuan,
        trang_thai=chuong_trinh.trang_thai,
    )
    db.add(chuong_trinh_moi)
    db.commit()
    db.refresh(chuong_trinh_moi)
    return chuong_trinh_moi


@app.get("/chuong-trinh", response_model=list[ChuongTrinhResponse], tags=["Quản lý đào tạo (SCRUM-41)"])
@app.get("/training-programs", response_model=list[ChuongTrinhResponse], tags=["Quản lý đào tạo (SCRUM-41)"])
def danh_sach_chuong_trinh(db: DbSession) -> list[ChuongTrinhResponse]:
    return list(db.scalars(select(ChuongTrinhDaoTao)).all())


@app.get("/chuong-trinh/{program_id}", response_model=ChuongTrinhResponse, tags=["Quản lý đào tạo (SCRUM-41)"])
@app.get("/training-programs/{program_id}", response_model=ChuongTrinhResponse, tags=["Quản lý đào tạo (SCRUM-41)"])
def xem_chuong_trinh(program_id: int, db: DbSession) -> ChuongTrinhResponse:
    chuong_trinh = db.get(ChuongTrinhDaoTao, program_id)
    if not chuong_trinh:
        raise HTTPException(status_code=404, detail="Không tìm thấy chương trình")
    return chuong_trinh


@app.put("/chuong-trinh/{program_id}", response_model=ChuongTrinhResponse, tags=["Quản lý đào tạo (SCRUM-41)"])
@app.put("/training-programs/{program_id}", response_model=ChuongTrinhResponse, tags=["Quản lý đào tạo (SCRUM-41)"])
def sua_chuong_trinh(program_id: int, du_lieu: ChuongTrinhCreate, db: DbSession) -> ChuongTrinhResponse:
    chuong_trinh = db.get(ChuongTrinhDaoTao, program_id)
    if not chuong_trinh:
        raise HTTPException(status_code=404, detail="Không tìm thấy chương trình")

    # Kiểm tra mã trùng
    ma_trung = db.scalar(
        select(ChuongTrinhDaoTao).where(
            ChuongTrinhDaoTao.ma_chuong_trinh == du_lieu.ma_chuong_trinh.strip(),
            ChuongTrinhDaoTao.id != program_id,
        )
    )
    if ma_trung:
        raise HTTPException(status_code=400, detail="Mã chương trình đã tồn tại")

    chuong_trinh.ma_chuong_trinh = du_lieu.ma_chuong_trinh.strip()
    chuong_trinh.ten_chuong_trinh = du_lieu.ten_chuong_trinh.strip()
    chuong_trinh.mo_ta = du_lieu.mo_ta
    chuong_trinh.tong_thoi_luong = du_lieu.tong_thoi_luong
    chuong_trinh.hoc_phi_chuan = du_lieu.hoc_phi_chuan
    chuong_trinh.trang_thai = du_lieu.trang_thai

    db.commit()
    db.refresh(chuong_trinh)
    return chuong_trinh


@app.delete("/chuong-trinh/{program_id}", tags=["Quản lý đào tạo (SCRUM-41)"])
@app.delete("/training-programs/{program_id}", tags=["Quản lý đào tạo (SCRUM-41)"])
def xoa_chuong_trinh(program_id: int, db: DbSession) -> dict[str, str]:
    chuong_trinh = db.get(ChuongTrinhDaoTao, program_id)
    if not chuong_trinh:
        raise HTTPException(status_code=404, detail="Không tìm thấy chương trình")

    # Quy tắc: Chương trình đang có lớp chạy không được xoá, chỉ được ngừng áp dụng
    lop_dang_chay = db.scalar(
        select(LopHoc).where(
            LopHoc.chuong_trinh_id == program_id,
            LopHoc.trang_thai == "DANG_CHAY",
        )
    )
    if lop_dang_chay:
        raise HTTPException(
            status_code=400,
            detail="Chương trình đang có lớp chạy, không được xóa. Chỉ được ngừng áp dụng.",
        )

    db.delete(chuong_trinh)
    db.commit()
    return {"message": "Xóa chương trình thành công"}


@app.patch("/chuong-trinh/{program_id}/ngung-ap-dung", tags=["Quản lý đào tạo (SCRUM-41)"])
@app.patch("/training-programs/{program_id}/deactivate", tags=["Quản lý đào tạo (SCRUM-41)"])
def ngung_ap_dung(program_id: int, db: DbSession) -> dict[str, str]:
    chuong_trinh = db.get(ChuongTrinhDaoTao, program_id)
    if not chuong_trinh:
        raise HTTPException(status_code=404, detail="Không tìm thấy chương trình")

    chuong_trinh.trang_thai = "NGUNG_AP_DUNG"
    db.commit()
    db.refresh(chuong_trinh)
    return {
        "message": "Đã ngừng áp dụng chương trình",
        "ma_chuong_trinh": chuong_trinh.ma_chuong_trinh,
        "trang_thai": chuong_trinh.trang_thai,
    }


@app.patch("/chuong-trinh/{program_id}/kich-hoat", tags=["Quản lý đào tạo (SCRUM-41)"])
@app.patch("/training-programs/{program_id}/activate", tags=["Quản lý đào tạo (SCRUM-41)"])
def kich_hoat_chuong_trinh(program_id: int, db: DbSession) -> dict[str, str]:
    chuong_trinh = db.get(ChuongTrinhDaoTao, program_id)
    if not chuong_trinh:
        raise HTTPException(status_code=404, detail="Không tìm thấy chương trình")

    chuong_trinh.trang_thai = "DANG_AP_DUNG"
    db.commit()
    db.refresh(chuong_trinh)
    return {
        "message": "Đã kích hoạt áp dụng chương trình",
        "ma_chuong_trinh": chuong_trinh.ma_chuong_trinh,
        "trang_thai": chuong_trinh.trang_thai,
    }


@app.post("/lop-hoc", response_model=LopHocResponse, tags=["Quản lý đào tạo (SCRUM-41)"])
@app.post("/classes", response_model=LopHocResponse, tags=["Quản lý đào tạo (SCRUM-41)"])
def tao_lop_hoc(lop_hoc: LopHocCreate, db: DbSession) -> LopHocResponse:
    # Mở lớp mới chỉ bằng cách chọn chương trình có sẵn
    chuong_trinh = db.get(ChuongTrinhDaoTao, lop_hoc.chuong_trinh_id)
    if not chuong_trinh:
        raise HTTPException(status_code=404, detail="Chương trình đào tạo không tồn tại")

    if chuong_trinh.trang_thai == "NGUNG_AP_DUNG":
        raise HTTPException(
            status_code=400,
            detail="Chương trình đã ngừng áp dụng, không thể mở lớp mới",
        )

    lop_moi = LopHoc(
        ten_lop=lop_hoc.ten_lop.strip(),
        chuong_trinh_id=lop_hoc.chuong_trinh_id,
        trang_thai=lop_hoc.trang_thai,
    )
    db.add(lop_moi)
    db.commit()
    db.refresh(lop_moi)
    return lop_moi


@app.get("/lop-hoc", response_model=list[LopHocResponse], tags=["Quản lý đào tạo (SCRUM-41)"])
@app.get("/classes", response_model=list[LopHocResponse], tags=["Quản lý đào tạo (SCRUM-41)"])
def danh_sach_lop_hoc(db: DbSession) -> list[LopHocResponse]:
    return list(db.scalars(select(LopHoc)).all())


@app.patch("/lop-hoc/{class_id}/ket-thuc", tags=["Quản lý đào tạo (SCRUM-41)"])
def ket_thuc_lop_hoc(class_id: int, db: DbSession) -> dict[str, str | int]:
    lop = db.get(LopHoc, class_id)
    if not lop:
        raise HTTPException(status_code=404, detail="Không tìm thấy lớp học")
    lop.trang_thai = "DA_KET_THUC"
    db.commit()
    db.refresh(lop)
    return {"message": "Lớp học đã kết thúc", "id": lop.id, "trang_thai": lop.trang_thai}


@app.delete("/lop-hoc/{class_id}", tags=["Quản lý đào tạo (SCRUM-41)"])
def xoa_lop_hoc(class_id: int, db: DbSession) -> dict[str, str]:
    lop = db.get(LopHoc, class_id)
    if not lop:
        raise HTTPException(status_code=404, detail="Không tìm thấy lớp học")
    db.delete(lop)
    db.commit()
    return {"message": "Đã xóa lớp học thành công"}


# =========================================================
# GIAO DIỆN WEB DEMO TRỰC QUAN (SCRUM-41)
# =========================================================

@app.get("/ui", response_class=HTMLResponse, tags=["Giao diện Web (SCRUM-41)"])
def giao_dien_quan_ly():
    return """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hệ Thống Quản Lý Đào Tạo - SCRUM-41</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css">
    <style>
        body { background-color: #f4f6f9; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .card { border-radius: 12px; border: none; box-shadow: 0 4px 12px rgba(0,0,0,0.06); margin-bottom: 24px; }
        .badge-active { background-color: #198754; color: white; padding: 6px 10px; border-radius: 6px; }
        .badge-inactive { background-color: #6c757d; color: white; padding: 6px 10px; border-radius: 6px; }
        .badge-running { background-color: #0d6efd; color: white; padding: 6px 10px; border-radius: 6px; }
        .badge-ended { background-color: #adb5bd; color: #212529; padding: 6px 10px; border-radius: 6px; }
        .table th { background-color: #e9ecef; color: #495057; font-weight: 600; }
        .preview-box { background: #e8f4fd; border: 1px dashed #0d6efd; border-radius: 8px; padding: 12px; }
    </style>
</head>
<body class="p-4">
    <div class="container-fluid max-w-1400">
        <header class="d-flex justify-content-between align-items-center mb-4 pb-3 border-bottom bg-white p-3 rounded-3 shadow-sm">
            <div>
                <h3 class="text-primary fw-bold mb-1"><i class="bi bi-mortarboard-fill me-2"></i>Quản Lý Chương Trình Đào Tạo & Mở Lớp Học (SCRUM-41)</h3>
                <small class="text-muted">Dành cho Quản lý đào tạo: Định nghĩa chương trình một lần, mở lớp nhanh bằng cách chọn chương trình có sẵn.</small>
            </div>
            <div>
                <a href="/docs" target="_blank" class="btn btn-outline-primary btn-sm"><i class="bi bi-code-slash me-1"></i>Swagger API Docs (/docs)</a>
            </div>
        </header>

        <div id="alertBox" class="alert d-none shadow-sm" role="alert"></div>

        <div class="row">
            <!-- CỘT 1: KHAI BÁO & QUẢN LÝ CHƯƠNG TRÌNH ĐÀO TẠO -->
            <div class="col-lg-7">
                <div class="card p-3">
                    <h5 class="fw-bold text-dark border-bottom pb-2">
                        <i class="bi bi-journal-plus text-primary me-2"></i>1. Khai báo Chương trình Đào tạo
                    </h5>
                    <form id="formCT" class="row g-2 mb-2">
                        <div class="col-md-4">
                            <label class="form-label small fw-bold">Mã chương trình *</label>
                            <input type="text" class="form-control form-control-sm" id="ma_ct" placeholder="VD: CT_PYTHON_01" required>
                        </div>
                        <div class="col-md-8">
                            <label class="form-label small fw-bold">Tên chương trình *</label>
                            <input type="text" class="form-control form-control-sm" id="ten_ct" placeholder="VD: Lập trình Python từ cơ bản đến nâng cao" required>
                        </div>
                        <div class="col-12">
                            <label class="form-label small fw-bold">Mô tả</label>
                            <input type="text" class="form-control form-control-sm" id="mo_ta" placeholder="Mô tả mục tiêu, đối tượng đào tạo...">
                        </div>
                        <div class="col-md-4">
                            <label class="form-label small fw-bold">Tổng thời lượng (giờ) *</label>
                            <input type="number" class="form-control form-control-sm" id="thoi_luong" value="40" min="1" required>
                        </div>
                        <div class="col-md-4">
                            <label class="form-label small fw-bold">Học phí chuẩn (VNĐ) *</label>
                            <input type="number" class="form-control form-control-sm" id="hoc_phi" value="5000000" min="0" step="100000" required>
                        </div>
                        <div class="col-md-4">
                            <label class="form-label small fw-bold">Trạng thái *</label>
                            <select class="form-select form-select-sm" id="trang_thai_ct" required>
                                <option value="DANG_AP_DUNG" selected>Đang áp dụng</option>
                                <option value="NGUNG_AP_DUNG">Ngừng áp dụng</option>
                            </select>
                        </div>
                        <div class="col-12 text-end mt-3">
                            <button type="submit" class="btn btn-primary btn-sm px-4 fw-bold">
                                <i class="bi bi-plus-circle me-1"></i>+ Khai báo mới
                            </button>
                        </div>
                    </form>
                </div>

                <div class="card p-3">
                    <div class="d-flex justify-content-between align-items-center border-bottom pb-2 mb-2">
                        <h5 class="fw-bold text-dark mb-0">
                            <i class="bi bi-list-ul text-primary me-2"></i>Danh mục Chương trình Đào tạo
                        </h5>
                        <button class="btn btn-outline-secondary btn-sm" onclick="loadData()"><i class="bi bi-arrow-clockwise"></i> Làm mới</button>
                    </div>

                    <div class="table-responsive">
                        <table class="table table-bordered table-hover table-sm align-middle mb-0">
                            <thead>
                                <tr>
                                    <th style="width: 50px;">ID</th>
                                    <th>Mã CT</th>
                                    <th>Tên chương trình</th>
                                    <th>Thời lượng</th>
                                    <th>Học phí chuẩn</th>
                                    <th>Trạng thái</th>
                                    <th>Lớp đang chạy</th>
                                    <th style="width: 175px;">Hành động</th>
                                </tr>
                            </thead>
                            <tbody id="tblChuongTrinh"></tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- CỘT 2: MỞ LỚP HỌC MỚI & QUẢN LÝ LỚP -->
            <div class="col-lg-5">
                <div class="card p-3">
                    <h5 class="fw-bold text-dark border-bottom pb-2">
                        <i class="bi bi-people-fill text-success me-2"></i>2. Mở Lớp Học Mới
                    </h5>
                    <p class="text-muted small mb-2">
                        <i class="bi bi-info-circle text-primary me-1"></i>
                        <strong>Kế thừa chương trình có sẵn:</strong> Chỉ cần chọn chương trình từ danh sách, không phải khai báo lại từ đầu.
                    </p>
                    <form id="formLop">
                        <div class="mb-2">
                            <label class="form-label small fw-bold">Tên lớp học *</label>
                            <input type="text" class="form-control form-control-sm" id="ten_lop" placeholder="VD: Python K23M - Tối T2,T4" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label small fw-bold">Chọn Chương trình đào tạo có sẵn *</label>
                            <select class="form-select form-select-sm" id="select_ct" required onchange="onSelectProgramChange()">
                                <option value="">-- Chọn chương trình có sẵn --</option>
                            </select>
                            <div class="form-text small text-muted">Chỉ các chương trình <strong>Đang áp dụng</strong> mới có thể mở lớp.</div>
                        </div>

                        <div id="programPreview" class="preview-box mb-3 d-none">
                            <div class="fw-bold text-primary small mb-1"><i class="bi bi-check2-circle me-1"></i>Thông tin kế thừa tự động:</div>
                            <div class="small">
                                <div>• Tên CT: <strong id="pvTen">-</strong></div>
                                <div>• Thời lượng: <span id="pvThoiLuong" class="badge bg-secondary">-</span> | Học phí chuẩn: <span id="pvHocPhi" class="fw-bold text-success">-</span></div>
                                <div id="pvMoTa" class="text-muted fst-italic mt-1">-</div>
                            </div>
                        </div>

                        <button type="submit" class="btn btn-success btn-sm w-100 fw-bold py-2">
                            <i class="bi bi-door-open-fill me-1"></i>+ Mở lớp học này
                        </button>
                    </form>
                </div>

                <div class="card p-3">
                    <div class="d-flex justify-content-between align-items-center border-bottom pb-2 mb-2">
                        <h5 class="fw-bold text-dark mb-0">
                            <i class="bi bi-card-checklist text-success me-2"></i>Danh sách Lớp học đã mở
                        </h5>
                    </div>
                    <div class="table-responsive">
                        <table class="table table-bordered table-sm align-middle mb-0">
                            <thead>
                                <tr>
                                    <th>ID</th>
                                    <th>Tên lớp</th>
                                    <th>Chương trình liên kết</th>
                                    <th>Trạng thái lớp</th>
                                    <th>Thao tác</th>
                                </tr>
                            </thead>
                            <tbody id="tblLopHoc"></tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- MODAL CHỈNH SỬA CHƯƠNG TRÌNH -->
    <div class="modal fade" id="modalEditCT" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title fw-bold"><i class="bi bi-pencil-square text-primary me-2"></i>Sửa Chương Trình Đào Tạo</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <form id="formEditCT" class="row g-2">
                        <input type="hidden" id="edit_id">
                        <div class="col-md-5">
                            <label class="form-label small fw-bold">Mã chương trình *</label>
                            <input type="text" class="form-control form-control-sm" id="edit_ma" required>
                        </div>
                        <div class="col-md-7">
                            <label class="form-label small fw-bold">Tên chương trình *</label>
                            <input type="text" class="form-control form-control-sm" id="edit_ten" required>
                        </div>
                        <div class="col-12">
                            <label class="form-label small fw-bold">Mô tả</label>
                            <input type="text" class="form-control form-control-sm" id="edit_mota">
                        </div>
                        <div class="col-md-4">
                            <label class="form-label small fw-bold">Thời lượng (giờ) *</label>
                            <input type="number" class="form-control form-control-sm" id="edit_thoiluong" required min="1">
                        </div>
                        <div class="col-md-4">
                            <label class="form-label small fw-bold">Học phí (VNĐ) *</label>
                            <input type="number" class="form-control form-control-sm" id="edit_hocphi" required min="0">
                        </div>
                        <div class="col-md-4">
                            <label class="form-label small fw-bold">Trạng thái *</label>
                            <select class="form-select form-select-sm" id="edit_trangthai" required>
                                <option value="DANG_AP_DUNG">Đang áp dụng</option>
                                <option value="NGUNG_AP_DUNG">Ngừng áp dụng</option>
                            </select>
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">Đóng</button>
                    <button type="button" class="btn btn-primary btn-sm" onclick="submitEditCT()">Lưu thay đổi</button>
                </div>
            </div>
        </div>
    </div>

    <!-- MODAL CẢNH BÁO KHÔNG ĐƯỢC XÓA -->
    <div class="modal fade" id="modalBlockDelete" tabindex="-1">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content border-danger border-2">
                <div class="modal-header bg-danger text-white">
                    <h5 class="modal-title fw-bold"><i class="bi bi-x-octagon-fill me-2"></i>Quy tắc hệ thống: Không thể xóa!</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body py-4 text-center">
                    <div class="display-5 text-danger mb-3"><i class="bi bi-exclamation-triangle-fill"></i></div>
                    <h5 class="fw-bold text-danger">Chương trình đang có lớp học đang chạy!</h5>
                    <p class="text-muted mb-3" id="blockDeleteMessage">
                        Theo yêu cầu nghiệp vụ: <strong>Chương trình đang có lớp chạy không được xoá, chỉ được ngừng áp dụng.</strong>
                    </p>
                    <div class="p-3 bg-light rounded text-start small">
                        <strong>Gợi ý thao tác:</strong>
                        <ul class="mb-0 mt-1">
                            <li>Bấm nút <strong>[Ngừng áp dụng]</strong> để chương trình không còn nhận mở lớp mới.</li>
                            <li>Nếu muốn xóa hoàn toàn: Phải kết thúc các lớp đang chạy của chương trình này trước.</li>
                        </ul>
                    </div>
                </div>
                <div class="modal-footer justify-content-between">
                    <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">Đã hiểu</button>
                    <button type="button" class="btn btn-warning btn-sm" id="btnChuyenNgungApDung">
                        <i class="bi bi-slash-circle me-1"></i>Ngừng áp dụng chương trình này ngay
                    </button>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        let programsCache = [];
        let classesCache = [];
        let modalEditInstance = null;
        let modalBlockInstance = null;
        let pendingProgramIdToStop = null;

        document.addEventListener('DOMContentLoaded', () => {
            modalEditInstance = new bootstrap.Modal(document.getElementById('modalEditCT'));
            modalBlockInstance = new bootstrap.Modal(document.getElementById('modalBlockDelete'));
            
            document.getElementById('btnChuyenNgungApDung').onclick = async () => {
                modalBlockInstance.hide();
                if (pendingProgramIdToStop) {
                    await ngungApDung(pendingProgramIdToStop);
                }
            };
            
            loadData();
        });

        function showAlert(msg, isSuccess = true) {
            const el = document.getElementById('alertBox');
            el.className = `alert alert-${isSuccess ? 'success' : 'danger'} alert-dismissible fade show`;
            el.innerHTML = `
                <div class="d-flex align-items-center">
                    <i class="bi ${isSuccess ? 'bi-check-circle-fill text-success' : 'bi-exclamation-triangle-fill text-danger'} fs-5 me-2"></i>
                    <div>${msg}</div>
                </div>
            `;
            el.classList.remove('d-none');
            setTimeout(() => el.classList.add('d-none'), 6000);
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }

        async function loadData() {
            try {
                const [resCT, resLop] = await Promise.all([
                    fetch('/chuong-trinh'),
                    fetch('/lop-hoc')
                ]);
                programsCache = await resCT.json();
                classesCache = await resLop.json();

                renderPrograms();
                renderClasses();
            } catch (err) {
                showAlert('Không thể tải dữ liệu: ' + err.message, false);
            }
        }

        function renderPrograms() {
            const tblCT = document.getElementById('tblChuongTrinh');
            const selectCT = document.getElementById('select_ct');
            tblCT.innerHTML = '';
            selectCT.innerHTML = '<option value="">-- Chọn chương trình có sẵn --</option>';

            programsCache.forEach(item => {
                const runningClasses = classesCache.filter(c => c.chuong_trinh_id === item.id && c.trang_thai === 'DANG_CHAY');
                const runningCount = runningClasses.length;

                const tr = document.createElement('tr');
                const badgeStatus = item.trang_thai === 'DANG_AP_DUNG' 
                    ? '<span class="badge badge-active"><i class="bi bi-check-circle me-1"></i>Đang áp dụng</span>' 
                    : '<span class="badge badge-inactive"><i class="bi bi-slash-circle me-1"></i>Ngừng áp dụng</span>';
                
                const badgeRunning = runningCount > 0 
                    ? `<span class="badge bg-danger"><i class="bi bi-play-circle-fill me-1"></i>${runningCount} lớp chạy</span>`
                    : `<span class="text-muted small">0 lớp</span>`;

                let btns = `
                    <button class="btn btn-outline-primary btn-sm py-0 px-2 me-1" title="Sửa" onclick="openEditModal(${item.id})">
                        <i class="bi bi-pencil"></i> Sửa
                    </button>
                `;

                if (item.trang_thai === 'DANG_AP_DUNG') {
                    btns += `
                        <button class="btn btn-outline-warning btn-sm py-0 px-2 me-1 text-dark" title="Ngừng áp dụng" onclick="ngungApDung(${item.id})">
                            <i class="bi bi-slash-circle"></i> Ngừng
                        </button>
                    `;
                } else {
                    btns += `
                        <button class="btn btn-outline-success btn-sm py-0 px-2 me-1" title="Kích hoạt lại" onclick="kichHoatCT(${item.id})">
                            <i class="bi bi-play-fill"></i> Dùng lại
                        </button>
                    `;
                }

                btns += `
                    <button class="btn btn-outline-danger btn-sm py-0 px-2" title="Xóa" onclick="xoaCT(${item.id})">
                        <i class="bi bi-trash"></i> Xóa
                    </button>
                `;

                tr.innerHTML = `
                    <td><strong>#${item.id}</strong></td>
                    <td><span class="badge bg-light text-dark border">${item.ma_chuong_trinh}</span></td>
                    <td>
                        <div class="fw-bold">${item.ten_chuong_trinh}</div>
                        <div class="text-muted small">${item.mo_ta || '<em>(Chưa có mô tả)</em>'}</div>
                    </td>
                    <td>${item.tong_thoi_luong} giờ</td>
                    <td class="fw-bold text-dark">${Number(item.hoc_phi_chuan).toLocaleString('vi-VN')} đ</td>
                    <td>${badgeStatus}</td>
                    <td>${badgeRunning}</td>
                    <td><div class="d-flex">${btns}</div></td>
                `;
                tblCT.appendChild(tr);

                if (item.trang_thai === 'DANG_AP_DUNG') {
                    const opt = document.createElement('option');
                    opt.value = item.id;
                    opt.innerText = `[${item.ma_chuong_trinh}] ${item.ten_chuong_trinh} (${item.tong_thoi_luong}h - ${Number(item.hoc_phi_chuan).toLocaleString('vi-VN')}đ)`;
                    selectCT.appendChild(opt);
                }
            });

            onSelectProgramChange();
        }

        function renderClasses() {
            const tblLop = document.getElementById('tblLopHoc');
            tblLop.innerHTML = '';

            if (classesCache.length === 0) {
                tblLop.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-3">Chưa có lớp học nào được mở</td></tr>';
                return;
            }

            classesCache.forEach(item => {
                const tr = document.createElement('tr');
                const ct = programsCache.find(p => p.id === item.chuong_trinh_id);
                const ctInfo = ct 
                    ? `<strong>${ct.ma_chuong_trinh}</strong> - ${ct.ten_chuong_trinh}` 
                    : `ID: ${item.chuong_trinh_id}`;

                const badgeStatus = item.trang_thai === 'DANG_CHAY'
                    ? '<span class="badge badge-running">ĐANG CHẠY</span>'
                    : '<span class="badge badge-ended">ĐÃ KẾT THÚC</span>';

                let actionBtns = '';
                if (item.trang_thai === 'DANG_CHAY') {
                    actionBtns += `<button class="btn btn-outline-secondary btn-sm py-0 me-1" onclick="ketThucLop(${item.id})">Kết thúc</button>`;
                }
                actionBtns += `<button class="btn btn-outline-danger btn-sm py-0" onclick="xoaLop(${item.id})"><i class="bi bi-trash"></i></button>`;

                tr.innerHTML = `
                    <td><strong>#${item.id}</strong></td>
                    <td><strong>${item.ten_lop}</strong></td>
                    <td><small>${ctInfo}</small></td>
                    <td>${badgeStatus}</td>
                    <td><div class="d-flex">${actionBtns}</div></td>
                `;
                tblLop.appendChild(tr);
            });
        }

        function onSelectProgramChange() {
            const selectCT = document.getElementById('select_ct');
            const previewBox = document.getElementById('programPreview');
            const ctId = parseInt(selectCT.value);
            if (!ctId) {
                previewBox.classList.add('d-none');
                return;
            }
            const prog = programsCache.find(p => p.id === ctId);
            if (prog) {
                document.getElementById('pvTen').innerText = prog.ten_chuong_trinh;
                document.getElementById('pvThoiLuong').innerText = prog.tong_thoi_luong + ' giờ';
                document.getElementById('pvHocPhi').innerText = Number(prog.hoc_phi_chuan).toLocaleString('vi-VN') + ' VNĐ';
                document.getElementById('pvMoTa').innerText = prog.mo_ta ? `"${prog.mo_ta}"` : '';
                previewBox.classList.remove('d-none');
            }
        }

        document.getElementById('formCT').onsubmit = async (e) => {
            e.preventDefault();
            const body = {
                ma_chuong_trinh: document.getElementById('ma_ct').value.trim(),
                ten_chuong_trinh: document.getElementById('ten_ct').value.trim(),
                mo_ta: document.getElementById('mo_ta').value.trim(),
                tong_thoi_luong: parseInt(document.getElementById('thoi_luong').value),
                hoc_phi_chuan: parseFloat(document.getElementById('hoc_phi').value),
                trang_thai: document.getElementById('trang_thai_ct').value
            };
            const res = await fetch('/chuong-trinh', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            const data = await res.json();
            if (res.ok) {
                showAlert(`Thêm thành công chương trình [${data.ma_chuong_trinh}] - ${data.ten_chuong_trinh}!`);
                document.getElementById('formCT').reset();
                document.getElementById('thoi_luong').value = 40;
                document.getElementById('hoc_phi').value = 5000000;
                document.getElementById('trang_thai_ct').value = 'DANG_AP_DUNG';
                loadData();
            } else {
                showAlert(`Lỗi khi tạo chương trình: ${data.detail}`, false);
            }
        };

        document.getElementById('formLop').onsubmit = async (e) => {
            e.preventDefault();
            const ctId = document.getElementById('select_ct').value;
            if (!ctId) {
                showAlert('Vui lòng chọn một chương trình đào tạo có sẵn từ danh sách!', false);
                return;
            }
            const body = {
                ten_lop: document.getElementById('ten_lop').value.trim(),
                chuong_trinh_id: parseInt(ctId),
                trang_thai: "DANG_CHAY"
            };
            const res = await fetch('/lop-hoc', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            const data = await res.json();
            if (res.ok) {
                showAlert(`Mở lớp học [${data.ten_lop}] thành công! Lớp được tự động liên kết với chương trình đã chọn.`);
                document.getElementById('ten_lop').value = '';
                document.getElementById('select_ct').value = '';
                onSelectProgramChange();
                loadData();
            } else {
                showAlert(`Lỗi khi mở lớp: ${data.detail}`, false);
            }
        };

        function openEditModal(id) {
            const item = programsCache.find(p => p.id === id);
            if (!item) return;
            document.getElementById('edit_id').value = item.id;
            document.getElementById('edit_ma').value = item.ma_chuong_trinh;
            document.getElementById('edit_ten').value = item.ten_chuong_trinh;
            document.getElementById('edit_mota').value = item.mo_ta || '';
            document.getElementById('edit_thoiluong').value = item.tong_thoi_luong;
            document.getElementById('edit_hocphi').value = item.hoc_phi_chuan;
            document.getElementById('edit_trangthai').value = item.trang_thai;
            modalEditInstance.show();
        }

        async function submitEditCT() {
            const id = document.getElementById('edit_id').value;
            const body = {
                ma_chuong_trinh: document.getElementById('edit_ma').value.trim(),
                ten_chuong_trinh: document.getElementById('edit_ten').value.trim(),
                mo_ta: document.getElementById('edit_mota').value.trim(),
                tong_thoi_luong: parseInt(document.getElementById('edit_thoiluong').value),
                hoc_phi_chuan: parseFloat(document.getElementById('edit_hocphi').value),
                trang_thai: document.getElementById('edit_trangthai').value
            };
            const res = await fetch(`/chuong-trinh/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            const data = await res.json();
            if (res.ok) {
                modalEditInstance.hide();
                showAlert(`Cập nhật chương trình [${data.ma_chuong_trinh}] thành công!`);
                loadData();
            } else {
                alert(`Lỗi khi cập nhật: ${data.detail}`);
            }
        }

        async function ngungApDung(id) {
            const res = await fetch(`/chuong-trinh/${id}/ngung-ap-dung`, { method: 'PATCH' });
            const data = await res.json();
            if (res.ok) {
                showAlert(`Đã ngừng áp dụng chương trình [${data.ma_chuong_trinh}].`);
                loadData();
            } else {
                showAlert(data.detail || 'Lỗi thao tác', false);
            }
        }

        async function kichHoatCT(id) {
            const res = await fetch(`/chuong-trinh/${id}/kich-hoat`, { method: 'PATCH' });
            const data = await res.json();
            if (res.ok) {
                showAlert(`Đã kích hoạt lại chương trình [${data.ma_chuong_trinh}] sang trạng thái Đang áp dụng.`);
                loadData();
            } else {
                showAlert(data.detail || 'Lỗi thao tác', false);
            }
        }

        async function xoaCT(id) {
            const prog = programsCache.find(p => p.id === id);
            if (!confirm(`Bạn có chắc chắn muốn xóa chương trình: [${prog ? prog.ma_chuong_trinh : id}]?`)) return;

            const res = await fetch(`/chuong-trinh/${id}`, { method: 'DELETE' });
            const data = await res.json();
            if (res.ok) {
                showAlert('Xóa chương trình đào tạo thành công!');
                loadData();
            } else {
                pendingProgramIdToStop = id;
                document.getElementById('blockDeleteMessage').innerHTML = `
                    Backend trả về: <strong class="text-danger">${data.detail}</strong><br>
                    Chương trình <strong>[${prog ? prog.ma_chuong_trinh : id}]</strong> hiện đang có lớp học trạng thái <strong>DANG_CHAY</strong>, do đó không được phép xóa!
                `;
                modalBlockInstance.show();
            }
        }

        async function ketThucLop(id) {
            const res = await fetch(`/lop-hoc/${id}/ket-thuc`, { method: 'PATCH' });
            if (res.ok) {
                showAlert('Đã chuyển lớp học sang trạng thái ĐÃ KẾT THÚC.');
                loadData();
            }
        }

        async function xoaLop(id) {
            if (!confirm('Bạn có chắc muốn xóa lớp học này?')) return;
            const res = await fetch(`/lop-hoc/${id}`, { method: 'DELETE' });
            if (res.ok) {
                showAlert('Đã xóa lớp học thành công.');
                loadData();
            }
        }
    </script>
</body>
</html>
    """