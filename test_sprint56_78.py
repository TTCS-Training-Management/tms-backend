import os
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

_database_path = Path(__file__).resolve().parent / ".sprint56-78-tests.sqlite"
_database_path.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{_database_path.as_posix()}"

import main
import sprint34


class Sprint56And78BillingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app)
        cls.client.__enter__()
        response = cls.client.post(
            "/auth/login",
            json={"email": "admin@tms.local", "password": "Admin@123"},
        )
        if response.status_code != 200:
            raise AssertionError(response.text)
        cls.admin_headers = {
            "Authorization": f"Bearer {response.json()['access_token']}"
        }

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        active_database_path = Path(main.engine.url.database)
        main.engine.dispose()
        active_database_path.unlink(missing_ok=True)
        _database_path.unlink(missing_ok=True)

    def _student_and_class(self, suffix):
        with main.SessionLocal() as db:
            program = main.TrainingProgram(
                code=f"TEST-{suffix}",
                name=f"Test program {suffix}",
            )
            db.add(program)
            db.flush()

            training_class = main.TrainingClass(
                program_id=program.id,
                name=f"Test class {suffix}",
            )
            lead = main.Lead(
                full_name=f"Billing student {suffix}",
                phone=f"090000{suffix:04d}",
                email=f"billing-{suffix}@example.test",
            )
            user = main.User(
                full_name=f"Billing student {suffix}",
                email=f"billing-user-{suffix}@example.test",
                password_hash=main.hash_password("Student123"),
                role="student",
            )
            db.add_all([training_class, lead, user])
            db.flush()
            student = sprint34.StudentProfile(
                student_code=f"TEST-STU-{suffix}",
                user_id=user.id,
                lead_id=lead.id,
                full_name=lead.full_name,
                phone=lead.phone,
                email=lead.email,
            )
            db.add(student)
            db.flush()
            db.add(
                sprint34.StudentEnrollment(
                    student_id=student.id,
                    class_id=training_class.id,
                    status="active",
                    effective_from=date.today(),
                )
            )
            db.commit()
            return student.id, training_class.id

    def _create_plan(self, suffix):
        student_id, class_id = self._student_and_class(suffix)
        response = self.client.post(
            "/billing/plans",
            headers=self.admin_headers,
            json={
                "student_id": student_id,
                "class_id": class_id,
                "tuition_amount": 1000,
                "installments": [
                    {
                        "sequence": 1,
                        "amount": 600,
                        "due_date": (date.today() + timedelta(days=10)).isoformat(),
                    },
                    {
                        "sequence": 2,
                        "amount": 400,
                        "due_date": (date.today() + timedelta(days=30)).isoformat(),
                    },
                ],
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_discount_rebalances_installments_and_blocks_duplicate_approval(self):
        plan = self._create_plan(101)
        response = self.client.post(
            f"/billing/plans/{plan['id']}/discount",
            headers=self.admin_headers,
            json={"percent": 20, "reason": "Test discount"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "approved")

        refreshed = self.client.get(
            f"/billing/plans/{plan['id']}",
            headers=self.admin_headers,
        )
        self.assertEqual(refreshed.status_code, 200, refreshed.text)
        self.assertEqual(refreshed.json()["amount_due"], 800)
        self.assertEqual(
            [item["amount"] for item in refreshed.json()["installments"]],
            [480, 320],
        )

        duplicate = self.client.post(
            f"/billing/plans/{plan['id']}/discount",
            headers=self.admin_headers,
            json={"amount": 100, "reason": "Duplicate discount"},
        )
        self.assertEqual(duplicate.status_code, 409, duplicate.text)

    def test_payment_rejects_overpayment_and_returns_receipt(self):
        plan = self._create_plan(102)
        installment_id = plan["installments"][0]["id"]
        overpayment = self.client.post(
            f"/billing/installments/{installment_id}/payments",
            headers=self.admin_headers,
            json={
                "amount": 601,
                "method": "cash",
                "paid_at": datetime.now().isoformat(),
            },
        )
        self.assertEqual(overpayment.status_code, 409, overpayment.text)

        payment = self.client.post(
            f"/billing/installments/{installment_id}/payments",
            headers=self.admin_headers,
            json={
                "amount": 600,
                "method": "bank_transfer",
                "paid_at": datetime.now().isoformat(),
            },
        )
        self.assertEqual(payment.status_code, 201, payment.text)
        self.assertEqual(payment.json()["installment"]["remaining"], 0)
        receipt = self.client.get(
            f"/billing/payments/{payment.json()['id']}/receipt",
            headers=self.admin_headers,
        )
        self.assertEqual(receipt.status_code, 200, receipt.text)
        self.assertEqual(receipt.json()["receipt_code"], payment.json()["receipt_code"])

    def test_attendance_policy_flags_student_at_configured_absence_threshold(self):
        student_id, class_id = self._student_and_class(103)
        with main.SessionLocal() as db:
            training_class = db.get(main.TrainingClass, class_id)
            admin = db.query(main.User).filter_by(email="admin@tms.local").one()
            lesson_ids = []
            for sequence in range(2):
                lesson = sprint34.TrainingLesson(
                    class_id=class_id,
                    title=f"Past lesson {sequence}",
                    starts_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=sequence + 2),
                    ends_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=sequence + 2, minutes=-60),
                    created_by=admin.id,
                )
                db.add(lesson)
                db.flush()
                lesson_ids.append(lesson.id)
            db.add_all([
                sprint34.Attendance(
                    lesson_id=lesson_ids[0],
                    student_id=student_id,
                    status="unexcused",
                    marked_by=admin.id,
                ),
                sprint34.Attendance(
                    lesson_id=lesson_ids[1],
                    student_id=student_id,
                    status="present",
                    marked_by=admin.id,
                ),
            ])
            db.commit()
            program_id = training_class.program_id

        configured = self.client.put(
            f"/attendance/policies/{program_id}",
            headers=self.admin_headers,
            json={"absence_threshold_percent": 40},
        )
        self.assertEqual(configured.status_code, 200, configured.text)
        summary = self.client.get(
            f"/attendance/classes/{class_id}/summary",
            headers=self.admin_headers,
        )
        self.assertEqual(summary.status_code, 200, summary.text)
        item = next(row for row in summary.json()["items"] if row["student_id"] == student_id)
        self.assertEqual(item["absence_percent"], 50)
        self.assertTrue(item["at_risk"])

    def test_announcement_email_and_survey_single_anonymous_response(self):
        student_id, class_id = self._student_and_class(104)
        with patch.object(main, "smtp_configured", return_value=True), patch.object(
            main, "send_email", return_value=True
        ) as send_email:
            announcement = self.client.post(
                "/announcements",
                headers=self.admin_headers,
                json={
                    "class_ids": [class_id],
                    "title": "Test announcement",
                    "body": "Class update",
                },
            )
        self.assertEqual(announcement.status_code, 201, announcement.text)
        self.assertEqual(announcement.json()["emails_sent"], 1)
        send_email.assert_called_once()

        survey = self.client.post(
            "/surveys",
            headers=self.admin_headers,
            json={
                "class_id": class_id,
                "title": "Course feedback",
                "due_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
                "questions": [{"type": "rating", "text": "How was the course?"}],
            },
        )
        self.assertEqual(survey.status_code, 201, survey.text)
        student_login = self.client.post(
            "/auth/login",
            json={
                "email": "billing-user-104@example.test",
                "password": "Student123",
            },
        )
        self.assertEqual(student_login.status_code, 200, student_login.text)
        student_headers = {
            "Authorization": f"Bearer {student_login.json()['access_token']}"
        }
        response_url = f"/surveys/{survey.json()['id']}/responses"
        response = self.client.post(
            response_url,
            headers=student_headers,
            json={"answers": [{"value": 5}]},
        )
        self.assertEqual(response.status_code, 201, response.text)
        duplicate = self.client.post(
            response_url,
            headers=student_headers,
            json={"answers": [{"value": 4}]},
        )
        self.assertEqual(duplicate.status_code, 409, duplicate.text)
        results = self.client.get(
            f"/surveys/{survey.json()['id']}/results",
            headers=self.admin_headers,
        )
        self.assertEqual(results.status_code, 200, results.text)
        self.assertEqual(results.json()["response_count"], 1)
        self.assertEqual(results.json()["results"][0]["average"], 5)
        self.assertNotIn("student_id", results.json())


if __name__ == "__main__":
    unittest.main()
