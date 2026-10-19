try:
    import pytest
    fixture_decorator = pytest.fixture(autouse=True)
except ImportError:
    def fixture_decorator(fn):
        return fn

from fastapi.testclient import TestClient
from backend.main import app, get_sqlite_conn


@fixture_decorator
def clean_db():

    with get_sqlite_conn() as conn:
        conn.execute("DELETE FROM submissions WHERE student_id LIKE 'TEST_%'")
        conn.commit()
    yield
    with get_sqlite_conn() as conn:
        conn.execute("DELETE FROM submissions WHERE student_id LIKE 'TEST_%'")
        conn.commit()


client = TestClient(app)


def test_root():
    res = client.get("/")
    assert res.status_code == 200
    assert res.json()["status"] == "online"


def test_submission_lifecycle():
    # 1. Nộp bài lần đầu (Phiên bản 1)
    files = {"file": ("bai1.txt", b"Noi dung lan 1", "text/plain")}
    res = client.post(
        "/api/submissions?student_id=TEST_HV01&assignment_id=TEST_BT01",
        headers={"X-User-Role": "student"},
        files=files
    )
    assert res.status_code == 201
    assert res.json()["version"] == 1

    # 2. Nộp lại (Phiên bản 2 không ghi đè bài cũ)
    files2 = {"file": ("bai1_v2.txt", b"Noi dung lan 2", "text/plain")}
    res2 = client.post(
        "/api/submissions?student_id=TEST_HV01&assignment_id=TEST_BT01",
        headers={"X-User-Role": "student"},
        files=files2
    )
    assert res2.status_code == 201
    assert res2.json()["version"] == 2

    # 3. Xem lịch sử (có đủ 2 phiên bản)
    hist = client.get("/api/submissions?student_id=TEST_HV01&assignment_id=TEST_BT01")
    assert hist.status_code == 200
    items = hist.json()
    assert len(items) == 2
    assert items[0]["version"] == 2
    assert items[1]["version"] == 1

    # 4. Học viên không được phép tự chấm bài
    grade_by_student = client.post(
        "/api/submissions/grade",
        headers={"X-User-Role": "student"},
        json={"student_id": "TEST_HV01", "assignment_id": "TEST_BT01"}
    )
    assert grade_by_student.status_code == 403

    # 5. Giảng viên chấm bài -> thành công
    grade_by_teacher = client.post(
        "/api/submissions/grade",
        headers={"X-User-Role": "teacher"},
        json={"student_id": "TEST_HV01", "assignment_id": "TEST_BT01"}
    )
    assert grade_by_teacher.status_code == 200

    # 6. Khóa nộp bài sau khi chấm -> nộp lại bị chặn 403
    res_blocked = client.post(
        "/api/submissions?student_id=TEST_HV01&assignment_id=TEST_BT01",
        headers={"X-User-Role": "student"},
        files=files2
    )
    assert res_blocked.status_code == 403

    # 7. Giảng viên mở lại bài
    reopen = client.post(
        "/api/submissions/reopen",
        headers={"X-User-Role": "teacher"},
        json={"student_id": "TEST_HV01", "assignment_id": "TEST_BT01"}
    )
    assert reopen.status_code == 200

    # 8. Học viên nộp lại phiên bản 3 thành công
    files3 = {"file": ("bai1_v3.txt", b"Noi dung lan 3", "text/plain")}
    res3 = client.post(
        "/api/submissions?student_id=TEST_HV01&assignment_id=TEST_BT01",
        headers={"X-User-Role": "student"},
        files=files3
    )
    assert res3.status_code == 201
    assert res3.json()["version"] == 3
