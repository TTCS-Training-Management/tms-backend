import pytest
from fastapi.testclient import TestClient
from main import app, seed_database

# Khởi tạo database và dữ liệu mẫu trước khi test
seed_database()
client = TestClient(app)


def test_login_failed_wrong_credentials():
    """1. Đăng nhập sai email hoặc mật khẩu -> 401 Unauthorized"""
    response = client.post(
        "/auth/login",
        json={"email": "admin@tms.local", "password": "WrongPassword123"}
    )
    assert response.status_code == 401
    assert "Email hoặc mật khẩu không đúng" in response.json()["detail"]


def test_login_success_admin():
    """2. Đăng nhập tài khoản admin thành công -> 200 OK & nhận token"""
    response = client.post(
        "/auth/login",
        json={"email": "admin@tms.local", "password": "Admin@123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["role"] == "admin"


def test_login_success_lecturer():
    """3. Đăng nhập tài khoản giảng viên thành công -> 200 OK & nhận token role lecturer"""
    response = client.post(
        "/auth/login",
        json={"email": "lecturer@tms.local", "password": "Lecturer@123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["role"] == "lecturer"


def test_auth_me_without_token_rejected():
    """4. Chưa đăng nhập truy cập API bảo vệ -> 401 Unauthorized"""
    response = client.get("/auth/me")
    assert response.status_code == 401
    assert "Vui lòng đăng nhập" in response.json()["detail"]


def test_auth_me_with_invalid_token_rejected():
    """5. Token không hợp lệ / giả mạo -> 401 Unauthorized"""
    headers = {"Authorization": "Bearer invalid_fake_token_12345"}
    response = client.get("/auth/me", headers=headers)
    assert response.status_code == 401
    assert "Phiên đăng nhập không hợp lệ" in response.json()["detail"]


def test_auth_me_with_valid_token_allowed():
    """6. Có token hợp lệ truy cập thành công -> 200 OK"""
    login_res = client.post(
        "/auth/login",
        json={"email": "lecturer@tms.local", "password": "Lecturer@123"}
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["email"] == "lecturer@tms.local"


def test_lecturer_cannot_access_admin_api():
    """7. Tài khoản thường (giảng viên) truy cập API quản trị -> 403 Forbidden"""
    login_res = client.post(
        "/auth/login",
        json={"email": "lecturer@tms.local", "password": "Lecturer@123"}
    )
    lecturer_token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {lecturer_token}"}

    # Giảng viên cố gắng lấy danh sách users quản trị
    response = client.get("/users", headers=headers)
    assert response.status_code == 403
    assert "Bạn không có quyền thực hiện thao tác này" in response.json()["detail"]


def test_admin_can_access_admin_api():
    """8. Tài khoản ADMIN có quyền truy cập API quản trị -> 200 OK"""
    login_res = client.post(
        "/auth/login",
        json={"email": "admin@tms.local", "password": "Admin@123"}
    )
    admin_token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    response = client.get("/users", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) > 0


def test_logout_revokes_token():
    """9. Đăng xuất thu hồi token -> token không thể sử dụng lại (401)"""
    login_res = client.post(
        "/auth/login",
        json={"email": "lecturer@tms.local", "password": "Lecturer@123"}
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Đăng xuất
    logout_res = client.post("/auth/logout", headers=headers)
    assert logout_res.status_code == 200

    # Dùng lại token vừa đăng xuất
    check_res = client.get("/auth/me", headers=headers)
    assert check_res.status_code == 401
