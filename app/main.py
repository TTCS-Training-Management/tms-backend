from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.routers import auth
from app.routers import products
from app.api.attendance import router as attendance_router  # <--- Dòng mới thêm 1

app = FastAPI(
    title="Hệ thống Quản lý Đào tạo - Auth & Authorization API",
    description="Hệ thống Backend FastAPI bảo mật bằng JWT và phân quyền người dùng (USER / ADMIN).",
    version="1.0.0"
)

# Cấu hình CORS để Frontend (React, Vue, Vite, ...) có thể gọi API dễ dàng
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Đăng ký Router Xác thực
app.include_router(
    auth.router,
    prefix="/api/auth",
    tags=["Authentication"]
)

# Đăng ký Router Sản phẩm / Khóa học
app.include_router(
    products.router,
    prefix="/api",
    tags=["Products"]
)

# Đăng ký Router Điểm danh & Xuất báo cáo Excel (SCRUM-87)
app.include_router(
    attendance_router,
    tags=["Attendance"]
)  # <--- Dòng mới thêm 2


@app.get("/", tags=["Health Check"])
def root():
    return {
        "status": "online",
        "message": "Backend FastAPI + JWT đang hoạt động",
        "docs_url": "/docs",
        "test_dashboard_url": "/dashboard"
    }


@app.get("/dashboard", response_class=HTMLResponse, tags=["Test Dashboard"])
def test_dashboard():
    return """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Minh Chứng Kiểm Thử Xác Thực & Phân Quyền JWT</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f0f2f5; margin: 0; padding: 25px; color: #1c1e21; }
        .container { max-width: 900px; margin: 0 auto; }
        .header { background: white; border-radius: 12px; padding: 25px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); margin-bottom: 25px; text-align: center; }
        .header h1 { margin: 0 0 10px 0; color: #0d6efd; font-size: 24px; }
        .header p { margin: 0; color: #65676b; font-size: 14px; }
        .card { background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); margin-bottom: 20px; border-left: 6px solid #0d6efd; }
        .card.test-401 { border-left-color: #dc3545; }
        .card.test-403 { border-left-color: #fd7e14; }
        .card.test-201 { border-left-color: #198754; }
        .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .card-title { font-weight: 700; font-size: 16px; }
        .badge { padding: 4px 10px; border-radius: 6px; font-weight: 600; font-size: 13px; }
        .badge-red { background: #ffebee; color: #dc3545; }
        .badge-orange { background: #fff3cd; color: #fd7e14; }
        .badge-green { background: #e8f5e9; color: #198754; }
        .btn { background: #0d6efd; color: white; border: none; padding: 8px 18px; border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: 600; }
        .btn:hover { background: #0b5ed7; }
        .btn-all { background: #198754; padding: 12px 24px; font-size: 16px; margin-bottom: 20px; }
        .result-box { background: #1e1e1e; color: #d4d4d4; padding: 12px; border-radius: 8px; font-family: Consolas, monospace; font-size: 13px; margin-top: 12px; overflow-x: auto; white-space: pre-wrap; display: none; }
        .meta-info { font-size: 13px; color: #555; margin-bottom: 8px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>BẢNG MINH CHỨNG KẾT QUẢ KIỂM THỬ BẢO MẬT & PHÂN QUYỀN JWT</h1>
            <p>Hệ thống Backend FastAPI - Xác thực Token Bearer & Phân quyền Role-based (USER / ADMIN)</p>
            <div style="margin-top: 15px;">
                <button class="btn btn-all" onclick="runAllTests()">⚡ CHẠY TẤT CẢ 3 BÀI TEST & HIỆN KẾT QUẢ MINH CHỨNG</button>
            </div>
        </div>

        <!-- Test 1: 401 Unauthorized -->
        <div class="card test-401" id="card1">
            <div class="card-header">
                <div class="card-title">1. Chưa đăng nhập → Bị chặn (401 Unauthorized)</div>
                <span class="badge badge-red" id="badge1">Chờ kiểm thử</span>
            </div>
            <div class="meta-info"><strong>API:</strong> <code>GET /api/products</code> (Không gửi Header <code>Authorization</code>)</div>
            <button class="btn" onclick="test1()">Chạy Test 1</button>
            <div class="result-box" id="res1"></div>
        </div>

        <!-- Test 2: 403 Forbidden -->
        <div class="card test-403" id="card2">
            <div class="card-header">
                <div class="card-title">2. USER không có quyền ADMIN → Bị chặn (403 Forbidden)</div>
                <span class="badge badge-orange" id="badge2">Chờ kiểm thử</span>
            </div>
            <div class="meta-info"><strong>API:</strong> <code>POST /api/products</code> (Đăng nhập vai trò <code>USER</code> kèm Bearer Token)</div>
            <button class="btn" onclick="test2()">Chạy Test 2</button>
            <div class="result-box" id="res2"></div>
        </div>

        <!-- Test 3: 201 Created -->
        <div class="card test-201" id="card3">
            <div class="card-header">
                <div class="card-title">3. ADMIN có quyền → Thực hiện thành công (201 Created)</div>
                <span class="badge badge-green" id="badge3">Chờ kiểm thử</span>
            </div>
            <div class="meta-info"><strong>API:</strong> <code>POST /api/products</code> (Đăng nhập vai trò <code>ADMIN</code> kèm Bearer Token)</div>
            <button class="btn" onclick="test3()">Chạy Test 3</button>
            <div class="result-box" id="res3"></div>
        </div>
    </div>

    <script>
        async function test1() {
            const resBox = document.getElementById('res1');
            const badge = document.getElementById('badge1');
            resBox.style.display = 'block';
            resBox.textContent = 'Đang gửi request GET /api/products (No Token)...';

            const resp = await fetch('/api/products');
            const data = await resp.json();
            badge.textContent = 'HTTP ' + resp.status + ' Unauthorized';
            resBox.textContent = 'HTTP Status: ' + resp.status + ' Unauthorized\n'
                               + 'Request Header: Không có Authorization\n'
                               + 'Response Body:\n' + JSON.stringify(data, null, 2);
        }

        async function test2() {
            const resBox = document.getElementById('res2');
            const badge = document.getElementById('badge2');
            resBox.style.display = 'block';
            resBox.textContent = 'Đang login USER (user1) lấy Token...';

            const loginRes = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: 'user1', password: '123456' })
            });
            const loginData = await loginRes.json();
            const token = loginData.access_token;

            const resp = await fetch('/api/products', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + token
                },
                body: JSON.stringify({ name: 'Khóa học React cho USER', price: 1500000 })
            });
            const data = await resp.json();
            badge.textContent = 'HTTP ' + resp.status + ' Forbidden';
            resBox.textContent = 'HTTP Status: ' + resp.status + ' Forbidden\n'
                               + 'User Role: USER (user1)\n'
                               + 'Request Header: Authorization: Bearer ' + token.substring(0, 25) + '...\n'
                               + 'Response Body:\n' + JSON.stringify(data, null, 2);
        }

        async function test3() {
            const resBox = document.getElementById('res3');
            const badge = document.getElementById('badge3');
            resBox.style.display = 'block';
            resBox.textContent = 'Đang login ADMIN (admin) lấy Token...';

            const loginRes = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: 'admin', password: '123456' })
            });
            const loginData = await loginRes.json();
            const token = loginData.access_token;

            const resp = await fetch('/api/products', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + token
                },
                body: JSON.stringify({ name: 'Khóa học Quản trị Hệ thống (Admin)', price: 3500000 })
            });
            const data = await resp.json();
            badge.textContent = 'HTTP ' + resp.status + ' Created';
            resBox.textContent = 'HTTP Status: ' + resp.status + ' Created\n'
                               + 'User Role: ADMIN (admin)\n'
                               + 'Request Header: Authorization: Bearer ' + token.substring(0, 25) + '...\n'
                               + 'Response Body:\n' + JSON.stringify(data, null, 2);
        }

        async function runAllTests() {
            await test1();
            await test2();
            await test3();
        }

        // Tự động chạy ngay khi mở trang để có ngay kết quả minh chứng
        window.onload = runAllTests;
    </script>
</body>
</html>
    """