import sys
import json

# Dam bao in tieng Viet va ky tu dac biet tren Windows console
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def print_step(title):
    print("\n" + "=" * 60)
    print(f">> {title}")
    print("=" * 60)


def run_demo():
    # Bước 1 — Login ADMIN
    print_step("Bước 1: Login tài khoản ADMIN (POST /api/auth/login)")
    payload = {"username": "admin", "password": "123456"}
    res = client.post("/api/auth/login", json=payload)
    print(f"Status Code: {res.status_code}")
    print("Response JSON:")
    print(json.dumps(res.json(), indent=2, ensure_ascii=False))
    admin_token = res.json()["access_token"]

    # Bước 2 — Login USER
    print_step("Bước 2: Login tài khoản USER thường (POST /api/auth/login)")
    res_user = client.post("/api/auth/login", json={"username": "user1", "password": "123456"})
    user_token = res_user.json()["access_token"]
    print(f"User Token rút gọn: {user_token[:30]}...")

    # Bước 3 — Gọi API cần đăng nhập có kèm Bearer Token
    print_step("Bước 3: Gọi API GET /api/products với Bearer Token của USER")
    res = client.get("/api/products", headers={"Authorization": f"Bearer {user_token}"})
    print(f"Status Code: {res.status_code}")
    print(json.dumps(res.json(), indent=2, ensure_ascii=False))

    # Bước 4 — Test không có token
    print_step("Bước 4: Test gọi API GET /api/products KHÔNG có Header Authorization")
    res = client.get("/api/products")
    print(f"Status Code: {res.status_code} (Mong đợi 401 hoặc 403)")
    print(json.dumps(res.json(), indent=2, ensure_ascii=False))

    # Bước 5 — Test sai quyền (USER cố xóa sản phẩm)
    print_step("Bước 5: Test sai quyền - USER gọi DELETE /api/products/1")
    res = client.delete("/api/products/1", headers={"Authorization": f"Bearer {user_token}"})
    print(f"Status Code: {res.status_code} (Mong đợi 403 Forbidden)")
    print(json.dumps(res.json(), indent=2, ensure_ascii=False))

    # Bước 6 — Test ADMIN xóa sản phẩm
    print_step("Bước 6: Test ADMIN gọi DELETE /api/products/1")
    res = client.delete("/api/products/1", headers={"Authorization": f"Bearer {admin_token}"})
    print(f"Status Code: {res.status_code} (Mong đợi 200 OK)")
    print(json.dumps(res.json(), indent=2, ensure_ascii=False))

    print("\n" + "=" * 60)
    print(">> HOAN TAT: TAT CA CAC BUOC TEST DEU THANH CONG!")
    print("=" * 60)


if __name__ == "__main__":
    run_demo()
