import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.seed import init_db


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    init_db()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# --- 1. KIỂM THỬ DỮ LIỆU TỪ DATABASE THẬT ---
def test_database_persistence_and_stats(client):
    """Kiểm tra dữ liệu được nạp từ database và tính đúng các chỉ số thống kê"""
    res = client.get("/api/classes/stats")
    assert res.status_code == 200
    stats = res.json()
    assert stats["total_classes"] == 12
    assert stats["active_classes"] == 6
    assert stats["upcoming_classes"] == 4
    assert stats["total_students"] > 0


def test_metadata_endpoint(client):
    """Kiểm tra API metadata trả về đúng danh mục programs và instructors từ database"""
    res = client.get("/api/meta")
    assert res.status_code == 200
    meta = res.json()
    assert len(meta["programs"]) >= 3
    assert len(meta["instructors"]) >= 3


# --- 2. KIỂM THỬ PHÂN TRANG (PAGINATION) ---
def test_pagination_default(client):
    """Kiểm tra phân trang mặc định (page=1, page_size=5)"""
    res = client.get("/api/classes?page=1&page_size=5")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 12
    assert data["page"] == 1
    assert data["page_size"] == 5
    assert data["total_pages"] == 3
    assert len(data["items"]) == 5
    assert data["items"][0]["id"] == 1


def test_pagination_page_2(client):
    """Kiểm tra trang 2 lấy đúng bản ghi tiếp theo"""
    res = client.get("/api/classes?page=2&page_size=5")
    assert res.status_code == 200
    data = res.json()
    assert data["page"] == 2
    assert len(data["items"]) == 5
    assert data["items"][0]["id"] == 6


def test_pagination_page_3(client):
    """Kiểm tra trang cuối cùng chỉ có 2 bản ghi còn lại (12 - 5*2 = 2)"""
    res = client.get("/api/classes?page=3&page_size=5")
    assert res.status_code == 200
    data = res.json()
    assert data["page"] == 3
    assert len(data["items"]) == 2


# --- 3. KIỂM THỬ KẾT HỢP NHIỀU BỘ LỌC (COMBINED FILTERS) ---
def test_filter_by_status_and_program(client):
    """Kết hợp bộ lọc: Trạng thái 'Đang học' VÀ Chương trình Python (id=2)"""
    res = client.get("/api/classes?status=Đang học&program_id=2")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] > 0
    for item in data["items"]:
        assert item["status"] == "Đang học"
        assert item["program_id"] == 2


def test_filter_by_instructor_and_date(client):
    """Kết hợp bộ lọc: Giảng viên 'Nguyễn Văn An' (id=1) VÀ bắt đầu từ 2026-08-01"""
    res = client.get("/api/classes?instructor_id=1&start_date=2026-08-01")
    assert res.status_code == 200
    data = res.json()
    for item in data["items"]:
        assert item["instructor_id"] == 1
        assert item["start_date"] >= "2026-08-01"


def test_filter_combined_four_criteria(client):
    """Kết hợp 4 bộ lọc cùng lúc: Status + Program + Instructor + Date range"""
    res = client.get(
        "/api/classes?status=Đang học&program_id=1&instructor_id=1&start_date=2026-07-01&end_date=2026-12-31"
    )
    assert res.status_code == 200
    data = res.json()
    for item in data["items"]:
        assert item["status"] == "Đang học"
        assert item["program_id"] == 1
        assert item["instructor_id"] == 1
        assert item["start_date"] >= "2026-07-01"
        assert item["end_date"] <= "2026-12-31"


def test_filter_no_results(client):
    """Kết hợp bộ lọc không có dữ liệu phù hợp"""
    res = client.get("/api/classes?status=Đã kết thúc&program_id=3")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 0
    assert len(data["items"]) == 0
    assert data["total_pages"] == 1


# --- 4. KIỂM THỬ XÓA BỘ LỌC (RESET FILTERS) ---
def test_reset_filters(client):
    """Sau khi lọc, gửi request không kèm filter params phải trả về toàn bộ 12 lớp"""
    # Bước 1: Gửi request lọc
    filtered_res = client.get("/api/classes?status=Đã kết thúc")
    assert filtered_res.json()["total"] == 2

    # Bước 2: Xóa bộ lọc (request rỗng)
    reset_res = client.get("/api/classes?page_size=20")
    reset_data = reset_res.json()
    assert reset_data["total"] == 12
    assert len(reset_data["items"]) == 12
