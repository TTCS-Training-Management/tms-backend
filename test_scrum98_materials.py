import io
import json
import os
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

_database_path = Path(__file__).resolve().parent / ".scrum98-tests.sqlite"
_database_path.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{_database_path.as_posix()}"

import main
import sprint34
import sprint56


class Scrum98LearningMaterialsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app)
        cls.client.__enter__()

        # Login Admin
        resp = cls.client.post("/auth/login", json={"email": "admin@tms.local", "password": "Admin@123"})
        if resp.status_code != 200:
            raise AssertionError(f"Admin login failed: {resp.text}")
        cls.admin_token = resp.json()["access_token"]
        cls.admin_headers = {"Authorization": f"Bearer {cls.admin_token}"}

        # Setup test data: Instructors, Students, Classes, Lessons
        with main.SessionLocal() as db:
            # 1. Program & Subjects
            program = main.TrainingProgram(code="PROG-SCRUM98", name="Scrum 98 Program")
            db.add(program)
            db.flush()

            subject = main.TrainingSubject(code="SUBJ-98", name="Scrum 98 Subject")
            db.add(subject)
            db.flush()

            # 2. Instructors
            inst1_user = main.User(
                full_name="Thầy Nguyễn Văn A (Giảng viên Lớp 1)",
                email="teacher1@tms.local",
                password_hash=main.hash_password("Teacher@123"),
                role="instructor",
            )
            inst2_user = main.User(
                full_name="Cô Trần Thị B (Giảng viên Khác)",
                email="teacher2@tms.local",
                password_hash=main.hash_password("Teacher@123"),
                role="instructor",
            )
            db.add_all([inst1_user, inst2_user])
            db.flush()

            db.add_all([
                main.UserRoleAssignment(user_id=inst1_user.id, role="instructor"),
                main.UserRoleAssignment(user_id=inst2_user.id, role="instructor"),
            ])
            db.flush()

            cls.inst1_id = inst1_user.id
            cls.inst2_id = inst2_user.id

            # 3. Classes
            class1 = main.TrainingClass(program_id=program.id, name="Lớp Web Fullstack CS301")
            class2 = main.TrainingClass(program_id=program.id, name="Lớp Khác CS202")
            db.add_all([class1, class2])
            db.flush()
            cls.class1_id = class1.id
            cls.class2_id = class2.id

            # Assign inst1 to class1 via ClassSubject
            cs1 = sprint34.ClassSubject(class_id=class1.id, subject_id=subject.id, sequence_order=1, instructor_id=inst1_user.id)
            # Assign inst2 to class2
            cs2 = sprint34.ClassSubject(class_id=class2.id, subject_id=subject.id, sequence_order=1, instructor_id=inst2_user.id)
            db.add_all([cs1, cs2])
            db.flush()

            # 4. Lessons for Class 1 (Lesson 1 is past, available for student download)
            now = datetime.now()
            lesson1 = sprint34.TrainingLesson(
                class_id=class1.id,
                instructor_id=inst1_user.id,
                title="Buổi 1: Giới thiệu RESTful API & Prisma",
                starts_at=now - timedelta(hours=3),
                ends_at=now - timedelta(hours=1),
                status="completed",
                created_by=inst1_user.id,
            )
            lesson2 = sprint34.TrainingLesson(
                class_id=class2.id,
                instructor_id=inst2_user.id,
                title="Buổi 1 của Lớp 2",
                starts_at=now - timedelta(hours=3),
                ends_at=now - timedelta(hours=1),
                status="completed",
                created_by=inst2_user.id,
            )
            db.add_all([lesson1, lesson2])
            db.flush()
            cls.lesson1_id = lesson1.id
            cls.lesson2_id = lesson2.id

            # 5. Students
            # Student 1 enrolled in Class 1
            stu1_user = main.User(
                full_name="Học viên Lê Văn C (Lớp 1)",
                email="student1@tms.local",
                password_hash=main.hash_password("Student@123"),
                role="student",
            )
            # Student 2 enrolled in Class 2 (not Class 1)
            stu2_user = main.User(
                full_name="Học viên Phạm Thị D (Lớp 2 - Ngoài lớp 1)",
                email="student2@tms.local",
                password_hash=main.hash_password("Student@123"),
                role="student",
            )
            db.add_all([stu1_user, stu2_user])
            db.flush()

            db.add_all([
                main.UserRoleAssignment(user_id=stu1_user.id, role="student"),
                main.UserRoleAssignment(user_id=stu2_user.id, role="student"),
            ])
            db.flush()

            lead1 = main.Lead(full_name=stu1_user.full_name, phone="0911000001", email=stu1_user.email)
            lead2 = main.Lead(full_name=stu2_user.full_name, phone="0911000002", email=stu2_user.email)
            db.add_all([lead1, lead2])
            db.flush()

            stu1_prof = sprint34.StudentProfile(
                student_code="STU-001",
                user_id=stu1_user.id,
                lead_id=lead1.id,
                full_name=stu1_user.full_name,
                email=stu1_user.email,
                phone="0911000001",
            )
            stu2_prof = sprint34.StudentProfile(
                student_code="STU-002",
                user_id=stu2_user.id,
                lead_id=lead2.id,
                full_name=stu2_user.full_name,
                email=stu2_user.email,
                phone="0911000002",
            )
            db.add_all([stu1_prof, stu2_prof])
            db.flush()

            # Enrol student 1 into class 1
            enr1 = sprint34.StudentEnrollment(
                class_id=class1.id,
                student_id=stu1_prof.id,
                status="active",
                effective_from=date.today() - timedelta(days=10),
            )
            # Enrol student 2 into class 2
            enr2 = sprint34.StudentEnrollment(
                class_id=class2.id,
                student_id=stu2_prof.id,
                status="active",
                effective_from=date.today() - timedelta(days=10),
            )
            db.add_all([enr1, enr2])
            db.commit()

        # Login Instructor 1
        r = cls.client.post("/auth/login", json={"email": "teacher1@tms.local", "password": "Teacher@123"})
        cls.teacher1_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

        # Login Instructor 2
        r = cls.client.post("/auth/login", json={"email": "teacher2@tms.local", "password": "Teacher@123"})
        cls.teacher2_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

        # Login Student 1
        r = cls.client.post("/auth/login", json={"email": "student1@tms.local", "password": "Student@123"})
        cls.student1_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

        # Login Student 2
        r = cls.client.post("/auth/login", json={"email": "student2@tms.local", "password": "Student@123"})
        cls.student2_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        main.engine.dispose()
        _database_path.unlink(missing_ok=True)

    def test_01_unauthenticated_requests_are_rejected(self):
        """Yêu cầu chưa đăng nhập phải bị chặn HTTP 401."""
        resp = self.client.get(f"/sessions/{self.lesson1_id}/materials")
        self.assertEqual(resp.status_code, 401)

        resp2 = self.client.get("/materials")
        self.assertEqual(resp2.status_code, 401)

    def test_02_instructor_of_another_class_cannot_upload(self):
        """Giảng viên lớp khác cố tình tải lên học liệu buổi học bị chặn HTTP 403."""
        links = json.dumps([{"title": "Slide ngoài", "url": "https://example.com/slide"}])
        resp = self.client.post(
            f"/sessions/{self.lesson1_id}/materials",
            headers=self.teacher2_headers,
            data={"links": links},
        )
        self.assertEqual(resp.status_code, 403)
        self.assertIn("chưa được phân công", resp.json()["detail"])

    def test_03_instructor_uploads_multiple_files_and_links(self):
        """Giảng viên phụ trách lớp tải lên nhiều tệp và liên kết ngoài cùng lúc thành công (201)."""
        file1 = ("lecture_notes.pdf", io.BytesIO(b"%PDF-1.4 sample pdf content"), "application/pdf")
        file2 = ("diagram.png", io.BytesIO(b"\x89PNG\r\n\x1a\n sample png"), "image/png")
        file3 = ("exercise.docx", io.BytesIO(b"PK\x03\x04 sample docx"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

        links = json.dumps([
            {"title": "Tài liệu MDN Web Docs", "url": "https://developer.mozilla.org"},
            {"title": "Trang chủ FastAPI", "url": "https://fastapi.tiangolo.com"},
        ])

        resp = self.client.post(
            f"/sessions/{self.lesson1_id}/materials",
            headers=self.teacher1_headers,
            files=[
                ("files", file1),
                ("files", file2),
                ("files", file3),
            ],
            data={"links": links, "available_early": True},
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        created = resp.json()
        self.assertIsInstance(created, list)
        self.assertEqual(len(created), 5)  # 3 files + 2 links

        # Lưu lại id của file để test download
        file_items = [item for item in created if item["type"] == "FILE"]
        self.assertEqual(len(file_items), 3)
        Scrum98LearningMaterialsTests.uploaded_file_id = file_items[0]["id"]

    def test_04_materials_list_contains_uploader_and_timestamp(self):
        """Danh sách học liệu trả về đầy đủ tên người tải lên (uploaded_by) và thời điểm (created_at)."""
        resp = self.client.get(
            f"/sessions/{self.lesson1_id}/materials",
            headers=self.student1_headers,
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        items = resp.json()
        self.assertGreaterEqual(len(items), 5)

        for item in items:
            self.assertIn("id", item)
            self.assertIn("title", item)
            self.assertIn("type", item)
            self.assertIn("created_at", item)
            self.assertIn("uploaded_by", item)
            self.assertIn("uploaded_by_name", item)
            self.assertEqual(item["uploaded_by_name"], "Thầy Nguyễn Văn A (Giảng viên Lớp 1)")

    def test_05_enrolled_student_can_download_material(self):
        """Học viên đã ghi danh vào lớp được phép tải tệp đính kèm (200)."""
        file_id = self.uploaded_file_id
        resp = self.client.get(
            f"/materials/{file_id}/download",
            headers=self.student1_headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("attachment", resp.headers.get("content-disposition", ""))
        self.assertGreater(len(resp.content), 0)

    def test_06_student_from_another_class_cannot_download_material(self):
        """Học viên lớp khác (dù biết file ID) không được phép tải tệp (403)."""
        file_id = self.uploaded_file_id
        resp = self.client.get(
            f"/materials/{file_id}/download",
            headers=self.student2_headers,
        )
        self.assertEqual(resp.status_code, 403)
        self.assertIn("Học liệu không thuộc lớp của bạn", resp.json()["detail"])

    def test_07_invalid_file_type_is_rejected(self):
        """Tải lên định dạng không an toàn (.exe) bị từ chối HTTP 415."""
        bad_file = ("virus.exe", io.BytesIO(b"MZ executable"), "application/x-msdownload")
        resp = self.client.post(
            f"/sessions/{self.lesson1_id}/materials",
            headers=self.teacher1_headers,
            files=[("files", bad_file)],
        )
        self.assertEqual(resp.status_code, 415)
        self.assertIn("chưa được hỗ trợ", resp.json()["detail"])

    def test_08_invalid_url_scheme_is_rejected(self):
        """Đính kèm URL không an toàn (javascript:...) bị từ chối HTTP 422."""
        bad_links = json.dumps([{"title": "Malicious", "url": "javascript:alert('xss')"}])
        resp = self.client.post(
            f"/sessions/{self.lesson1_id}/materials",
            headers=self.teacher1_headers,
            data={"links": bad_links},
        )
        self.assertEqual(resp.status_code, 422)
        self.assertIn("không hợp lệ", resp.json()["detail"])

    def test_09_delete_material_by_instructor_and_unauthorized_block(self):
        """Giảng viên có quyền xóa học liệu, người không có quyền bị chặn 403."""
        # Student 1 tries to delete material -> 403
        resp = self.client.delete(f"/materials/{self.uploaded_file_id}", headers=self.student1_headers)
        self.assertEqual(resp.status_code, 403)

        # Teacher 1 deletes material -> 200
        del_resp = self.client.delete(f"/materials/{self.uploaded_file_id}", headers=self.teacher1_headers)
        self.assertEqual(del_resp.status_code, 200)
        self.assertIn("thành công", del_resp.json()["message"])


if __name__ == "__main__":
    unittest.main()
