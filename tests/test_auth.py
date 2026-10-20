import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root_endpoint():
    """Kiểm tra API root health check"""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "online"


def test_login_failed_wrong_credentials():
    """Bước 1: Login sai tài khoản/mật khẩu -> 401"""
    response = client.post(
        "/api/auth/login",
        json={"username": "wronguser", "password": "wrongpassword"}
    )
    assert response.status_code == 401
    assert "Sai username hoặc password" in response.json()["detail"]


def test_login_success_admin():
    """Bước 1 & 2: Login admin thành công và nhận token"""
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "123456"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert len(data["access_token"]) > 20


def test_login_success_user():
    """Bước 1 & 2: Login user1 thành công và nhận token"""
    response = client.post(
        "/api/auth/login",
        json={"username": "user1", "password": "123456"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_get_products_without_token():
    """Bước 4: Gọi API cần đăng nhập mà KHÔNG gửi token -> 401/403"""
    response = client.get("/api/products")
    # FastAPI HTTPBearer mặc định trả về 401 hoặc 403 khi thiếu header
    assert response.status_code in [401, 403]


def test_get_products_with_invalid_token():
    """Bước 4: Gọi API với token sai/rác -> 401"""
    headers = {"Authorization": "Bearer token_khong_hop_le_12345"}
    response = client.get("/api/products", headers=headers)
    assert response.status_code == 401
    assert "Token không hợp lệ" in response.json()["detail"]


def test_get_products_with_valid_token():
    """Bước 3: Gọi API cần đăng nhập với Bearer token hợp lệ -> 200"""
    # 1. Đăng nhập lấy token
    login_res = client.post(
        "/api/auth/login",
        json={"username": "user1", "password": "123456"}
    )
    token = login_res.json()["access_token"]

    # 2. Gọi GET /api/products kèm Header Bearer token
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/products", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Bạn đã đăng nhập"
    assert data["user"]["sub"] == "user1"
    assert data["user"]["role"] == "USER"
    assert len(data["products"]) > 0


def test_delete_product_forbidden_for_user():
    """Bước 5: Tài khoản vai trò USER cố gắng xóa sản phẩm -> 403 Forbidden"""
    # 1. Đăng nhập USER
    login_res = client.post(
        "/api/auth/login",
        json={"username": "user1", "password": "123456"}
    )
    user_token = login_res.json()["access_token"]

    # 2. Gọi DELETE /api/products/1
    headers = {"Authorization": f"Bearer {user_token}"}
    response = client.delete("/api/products/1", headers=headers)
    assert response.status_code == 403
    assert "Bạn không có quyền thực hiện chức năng này" in response.json()["detail"]


def test_delete_product_allowed_for_admin():
    """Bước 6: Tài khoản vai trò ADMIN xóa sản phẩm -> 200 OK"""
    # 1. Đăng nhập ADMIN
    login_res = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "123456"}
    )
    admin_token = login_res.json()["access_token"]

    # 2. Gọi DELETE /api/products/1
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = client.delete("/api/products/1", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "Xóa sản phẩm 1 thành công" in data["message"]
    assert data["deleted_by"] == "admin"


def test_create_product_forbidden_for_user():
    """Tài khoản vai trò USER gọi POST /api/products -> 403 Forbidden"""
    login_res = client.post(
        "/api/auth/login",
        json={"username": "user1", "password": "123456"}
    )
    user_token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {user_token}"}
    response = client.post(
        "/api/products",
        json={"name": "Khóa học AI", "price": 3000000},
        headers=headers
    )
    assert response.status_code == 403
    assert "Bạn không có quyền thực hiện chức năng này" in response.json()["detail"]


def test_create_product_allowed_for_admin():
    """Tài khoản vai trò ADMIN gọi POST /api/products -> 201 Created"""
    login_res = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "123456"}
    )
    admin_token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = client.post(
        "/api/products",
        json={"name": "Khóa học AI Nâng Cao", "price": 3000000},
        headers=headers
    )
    assert response.status_code == 201
    data = response.json()
    assert "Thêm sản phẩm mới thành công" in data["message"]
    assert data["created_by"] == "admin"
