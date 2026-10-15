import os
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

_database_path = Path(__file__).resolve().parent / ".sprint34-tests.sqlite"
_database_path.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{_database_path.as_posix()}"

import main
import sprint34


class Sprint34ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app)
        cls.client.__enter__()
        response = cls.client.post(
            "/auth/login",
            json={"email": "admin@tms.local", "password": "Admin@123"},
        )
        cls.admin_headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        active_database_path = Path(main.engine.url.database)
        main.engine.dispose()
        active_database_path.unlink(missing_ok=True)
        _database_path.unlink(missing_ok=True)

    def _base_program_and_class(self, suffix=""):
        program = self.client.post(
            "/training/programs",
            headers=self.admin_headers,
            json={"code": f"S34-P{suffix}", "name": f"Sprint 3/4{suffix}"},
        )
        self.assertEqual(program.status_code, 200, program.text)
        subject = self.client.post(
            "/training/subjects",
            headers=self.admin_headers,
            json={"code": f"S34-S{suffix}", "name": f"Backend{suffix}", "session_count": 2},
        )
        self.assertEqual(subject.status_code, 200, subject.text)
        linked = self.client.post(
            f"/training/programs/{program.json()['id']}/subjects",
            headers=self.admin_headers,
            json={"subject_id": subject.json()["id"], "sequence_order": 1},
        )
        self.assertEqual(linked.status_code, 200, linked.text)
        for sequence in range(1, 3):
            created = self.client.post(
                f"/training/subjects/{subject.json()['id']}/sessions",
                headers=self.admin_headers,
                json={"sequence": sequence, "title": f"Lesson {sequence}"},
            )
            self.assertEqual(created.status_code, 200, created.text)
        training_class = self.client.post(
            "/training/classes",
            headers=self.admin_headers,
            json={
                "program_id": program.json()["id"],
                "code": f"S34-C{suffix}",
                "name": f"Backend class{suffix}",
                "start_date": (date.today() + timedelta(days=7)).isoformat(),
                "capacity": 20,
                "format": "in_person",
            },
        )
        self.assertEqual(training_class.status_code, 201, training_class.text)
        return subject.json()["id"], training_class.json()["id"]

    def test_lead_board_interactions_and_conversion_freezes_lead(self):
        created = self.client.post(
            "/leads",
            headers=self.admin_headers,
            json={"full_name": "Student Lead", "phone": "0907654321", "email": "student34@example.test"},
        )
        self.assertEqual(created.status_code, 201, created.text)
        lead_id = created.json()["id"]
        interaction = self.client.post(
            f"/leads/{lead_id}/interactions",
            headers=self.admin_headers,
            json={
                "interaction_type": "call",
                "content": "Called prospect",
                "follow_up_at": (date.today() - timedelta(days=1)).isoformat() + "T09:00:00",
            },
        )
        self.assertEqual(interaction.status_code, 201, interaction.text)
        self.assertTrue(self.client.get(
            "/leads/follow-ups/overdue", headers=self.admin_headers
        ).json())
        filtered_overdue = self.client.get(
            "/leads/follow-ups/overdue?q=Student%20Lead", headers=self.admin_headers
        ).json()
        self.assertTrue(filtered_overdue)
        self.assertEqual({item["lead_id"] for item in filtered_overdue}, {lead_id})
        filtered_summary = self.client.get(
            "/leads/summary?q=Student%20Lead", headers=self.admin_headers
        ).json()
        self.assertEqual(filtered_summary["total"], 1)
        self.assertEqual(filtered_summary["counts"]["new"], 1)
        won_before = self.client.get("/leads/summary", headers=self.admin_headers).json()["counts"]["won"]
        status_response = self.client.patch(
            f"/leads/{lead_id}",
            headers=self.admin_headers,
            json={"status": "won"},
        )
        self.assertEqual(status_response.status_code, 200, status_response.text)
        self.assertEqual(
            self.client.get("/leads/summary", headers=self.admin_headers).json()["counts"]["won"],
            won_before + 1,
        )
        status_history = self.client.get(
            f"/leads/{lead_id}/interactions", headers=self.admin_headers
        ).json()
        self.assertEqual(
            sum(item["action"] == "status_transition" for item in status_history),
            1,
        )
        self.assertFalse(any(
            item["action"] == "updated" and "status" in item["content"]
            for item in status_history
        ))
        converted_count_before = self.client.get(
            "/leads/summary", headers=self.admin_headers
        ).json()["counts"]["converted"]
        with patch.object(main, "send_email", return_value=True):
            converted = self.client.post(
                f"/leads/{lead_id}/convert", headers=self.admin_headers, json={"entry_level": "A1"}
            )
        self.assertEqual(converted.status_code, 200, converted.text)
        student = converted.json()["student"]
        self.assertTrue(student["student_code"].startswith("STU-"))
        self.assertEqual(student["entry_level"], "A1")
        converted_lead = self.client.get(
            f"/leads?status=converted", headers=self.admin_headers
        )
        self.assertEqual(converted_lead.status_code, 200, converted_lead.text)
        self.assertIn(lead_id, [item["id"] for item in converted_lead.json()])
        self.assertEqual(
            self.client.get("/leads/summary", headers=self.admin_headers).json()["counts"]["converted"],
            converted_count_before + 1,
        )
        overdue_after_conversion = self.client.get(
            "/leads/follow-ups/overdue?q=Student%20Lead",
            headers=self.admin_headers,
        ).json()
        self.assertNotIn(lead_id, {item["lead_id"] for item in overdue_after_conversion})
        frozen = self.client.patch(
            f"/leads/{lead_id}", headers=self.admin_headers, json={"notes": "changed"}
        )
        self.assertEqual(frozen.status_code, 409)
        duplicate_conversion = self.client.post(
            f"/leads/{lead_id}/convert", headers=self.admin_headers
        )
        self.assertEqual(duplicate_conversion.status_code, 200)
        self.assertTrue(any(item["interaction_type"] == "call" for item in self.client.get(
            f"/leads/{lead_id}/interactions", headers=self.admin_headers
        ).json()))

    def test_student_profile_search_history_and_enrollment_actor(self):
        _, class_id = self._base_program_and_class("-PROFILE")
        lead = self.client.post(
            "/leads",
            headers=self.admin_headers,
            json={
                "full_name": "Profile Student",
                "phone": "0907654381",
                "email": "profile-student@example.test",
            },
        )
        self.assertEqual(lead.status_code, 201, lead.text)
        self.assertEqual(
            self.client.patch(
                f"/leads/{lead.json()['id']}",
                headers=self.admin_headers,
                json={"status": "won"},
            ).status_code,
            200,
        )
        with patch.object(main, "send_email", return_value=True):
            converted = self.client.post(
                f"/leads/{lead.json()['id']}/convert", headers=self.admin_headers
            )
        self.assertEqual(converted.status_code, 200, converted.text)
        student = converted.json()["student"]
        update = self.client.patch(
            f"/students/{student['id']}",
            headers=self.admin_headers,
            json={"full_name": "Profile Student Updated", "entry_level": "A1", "notes": "Placement interview"},
        )
        self.assertEqual(update.status_code, 200, update.text)
        self.assertEqual(update.json()["entry_level"], "A1")
        self.assertEqual(update.json()["notes"], "Placement interview")
        by_name = self.client.get(
            "/students?q=Profile%20Student%20Updated", headers=self.admin_headers
        )
        by_phone = self.client.get(
            "/students?q=0907654381", headers=self.admin_headers
        )
        self.assertEqual(by_name.json()["total"], 1)
        self.assertEqual(by_phone.json()["items"][0]["id"], student["id"])

        enrolled = self.client.post(
            f"/training/classes/{class_id}/enrollments",
            headers=self.admin_headers,
            json={"student_ids": [student["id"]]},
        )
        self.assertEqual(enrolled.status_code, 201, enrolled.text)
        profile = self.client.get(
            f"/students/{student['id']}", headers=self.admin_headers
        ).json()
        self.assertEqual(profile["class_history"][0]["class_name"], "Backend class-PROFILE")
        roster = self.client.get(
            f"/training/classes/{class_id}/enrollments", headers=self.admin_headers
        ).json()
        self.assertEqual(roster["items"][0]["student_id"], student["id"])
        self.assertTrue(roster["items"][0]["enrolled_by"])

    def test_conversion_email_failure_does_not_create_student(self):
        lead = self.client.post(
            "/leads",
            headers=self.admin_headers,
            json={
                "full_name": "Mail Failure Lead",
                "phone": "0907654382",
                "email": "mail-failure@example.test",
            },
        )
        self.assertEqual(lead.status_code, 201, lead.text)
        lead_id = lead.json()["id"]
        self.assertEqual(
            self.client.patch(
                f"/leads/{lead_id}", headers=self.admin_headers, json={"status": "won"}
            ).status_code,
            200,
        )
        with patch.object(main, "send_email", return_value=False):
            conversion = self.client.post(
                f"/leads/{lead_id}/convert", headers=self.admin_headers
            )
        self.assertEqual(conversion.status_code, 503)
        students = self.client.get(
            "/students?q=Mail%20Failure%20Lead", headers=self.admin_headers
        ).json()
        self.assertEqual(students["total"], 0)

    def test_schedule_rejects_physical_room_smaller_than_enrollment(self):
        subject_id, class_id = self._base_program_and_class("-ROOM-CAP")
        with main.SessionLocal() as db:
            admin = db.scalar(main.select(main.User).where(main.User.email == "admin@tms.local"))
            self.assertIsNotNone(admin)
            for index in range(2):
                lead = main.Lead(
                    full_name=f"Room Capacity Student {index}",
                    phone=f"090765439{index}",
                    email=f"room-capacity-{index}@example.test",
                    status="won",
                )
                account = main.User(
                    full_name=lead.full_name,
                    email=lead.email,
                    password_hash=main.hash_password("StudentTest123"),
                    role="student",
                )
                db.add_all([lead, account])
                db.flush()
                db.add(main.UserRoleAssignment(user_id=account.id, role="student"))
                profile = sprint34.StudentProfile(
                    student_code=f"S34-ROOM-{index}",
                    user_id=account.id,
                    lead_id=lead.id,
                    full_name=lead.full_name,
                    phone=lead.phone,
                    email=lead.email,
                )
                db.add(profile)
                db.flush()
                db.add(sprint34.StudentEnrollment(
                    student_id=profile.id,
                    class_id=class_id,
                    actor_user_id=admin.id,
                    effective_from=date.today(),
                ))
            db.commit()

        room = self.client.post(
            "/training/rooms",
            headers=self.admin_headers,
            json={"code": "R-S34-SMALL", "name": "Small Room", "room_type": "physical", "capacity": 1, "location": "Floor 1"},
        )
        self.assertEqual(room.status_code, 201, room.text)
        templates = self.client.get(
            f"/training/subjects/{subject_id}/sessions", headers=self.admin_headers
        ).json()
        start_date = date.today() + timedelta(days=7)
        preview = self.client.post(
            f"/training/classes/{class_id}/schedule/preview",
            headers=self.admin_headers,
            json={
                "weekday": start_date.weekday(),
                "session_time": "10:00:00",
                "start_date": start_date.isoformat(),
                "count": 1,
                "room_id": room.json()["id"],
                "subject_session_ids": [templates[0]["id"]],
            },
        )
        self.assertEqual(preview.status_code, 409)

    def test_class_enrollment_room_schedule_attendance_and_absence_decision(self):
        subject_id, class_id = self._base_program_and_class()
        with main.SessionLocal() as db:
            instructor = main.User(
                full_name="Sprint Instructor", email="s34-instructor@example.test",
                password_hash=main.hash_password("Instructor123"), role="instructor",
            )
            ta = main.User(
                full_name="Sprint TA", email="s34-ta@example.test",
                password_hash=main.hash_password("Teaching123"), role="ta",
            )
            db.add_all([instructor, ta])
            db.flush()
            db.add_all([
                main.UserRoleAssignment(user_id=instructor.id, role="instructor"),
                main.UserRoleAssignment(user_id=ta.id, role="ta"),
            ])
            db.commit()
            instructor_id, ta_id = instructor.id, ta.id
            instructor_headers = {"Authorization": f"Bearer {main.encode_token(instructor)}"}
        staff_assignment = self.client.put(
            f"/training/classes/{class_id}/subjects/{subject_id}/staff",
            headers=self.admin_headers,
            json={"instructor_id": instructor_id, "ta_ids": [ta_id]},
        )
        self.assertEqual(staff_assignment.status_code, 200, staff_assignment.text)
        invalid_staff_assignment = self.client.put(
            f"/training/classes/{class_id}/subjects/{subject_id}/staff",
            headers=self.admin_headers,
            json={"instructor_id": ta_id, "ta_ids": [instructor_id]},
        )
        self.assertEqual(invalid_staff_assignment.status_code, 422)
        staff_list = self.client.get(
            f"/training/classes/{class_id}/subjects", headers=instructor_headers
        )
        self.assertEqual(staff_list.status_code, 200)
        self.assertEqual(staff_list.json()[0]["instructor"]["id"], instructor_id)
        self.assertEqual(staff_list.json()[0]["tas"][0]["id"], ta_id)
        visible_classes = self.client.get("/training/classes", headers=instructor_headers)
        self.assertEqual([item["id"] for item in visible_classes.json()["items"]], [class_id])
        with main.SessionLocal() as db:
            lead = main.Lead(
                full_name="Enrolled Student",
                phone="0907654322",
                email="enrolled34@example.test",
                status="won",
            )
            db.add(lead)
            db.commit()
            lead_id = lead.id
        with patch.object(main, "send_email", return_value=True):
            converted = self.client.post(
                f"/leads/{lead_id}/convert", headers=self.admin_headers
            )
        student = converted.json()["student"]
        enrollment = self.client.post(
            f"/training/classes/{class_id}/enrollments",
            headers=self.admin_headers,
            json={"student_ids": [student["id"]]},
        )
        self.assertEqual(enrollment.status_code, 201, enrollment.text)
        roster = self.client.get(
            f"/training/classes/{class_id}/enrollments", headers=self.admin_headers
        ).json()
        self.assertEqual(roster["items"][0]["student_id"], student["id"])
        self.assertTrue(roster["items"][0]["enrolled_at"])
        self.assertTrue(roster["items"][0]["enrolled_by"])
        duplicate = self.client.post(
            f"/training/classes/{class_id}/enrollments",
            headers=self.admin_headers,
            json={"student_ids": [student["id"]]},
        )
        self.assertEqual(duplicate.status_code, 409)
        room = self.client.post(
            "/training/rooms",
            headers=self.admin_headers,
            json={"code": "R-S34", "name": "Room 34", "room_type": "physical", "capacity": 10, "location": "Floor 1"},
        )
        self.assertEqual(room.status_code, 201, room.text)
        session_templates = self.client.get(
            f"/training/subjects/{subject_id}/sessions", headers=self.admin_headers
        ).json()
        start_date = date.today() + timedelta(days=7)
        schedule_payload = {
            "weekday": start_date.weekday(),
            "session_time": "10:00:00",
            "start_date": start_date.isoformat(),
            "count": 2,
            "room_id": room.json()["id"],
            "subject_session_ids": [item["id"] for item in session_templates],
        }
        preview = self.client.post(
            f"/training/classes/{class_id}/schedule/preview",
            headers=self.admin_headers,
            json=schedule_payload,
        )
        self.assertEqual(preview.status_code, 200, preview.text)
        self.assertEqual(len(preview.json()["sessions"]), 2)
        saved = self.client.post(
            f"/training/classes/{class_id}/schedule",
            headers=self.admin_headers,
            json=schedule_payload,
        )
        self.assertEqual(saved.status_code, 201, saved.text)
        self.assertEqual(saved.json()["created_count"], 2)
        second_class = self.client.post(
            "/training/classes",
            headers=self.admin_headers,
            json={
                "program_id": self.client.get("/training/classes", headers=self.admin_headers).json()["items"][0]["program_id"],
                "code": "S34-C2",
                "name": "Conflict class",
                "start_date": start_date.isoformat(),
                "capacity": 20,
                "format": "in_person",
            },
        )
        self.assertEqual(second_class.status_code, 201, second_class.text)
        conflict_payload = {
            **schedule_payload, "count": 1,
            "subject_session_ids": [session_templates[0]["id"]],
            "instructor_id": instructor_id,
        }
        blocked = self.client.post(
            f"/training/classes/{second_class.json()['id']}/schedule",
            headers=self.admin_headers,
            json=conflict_payload,
        )
        self.assertEqual(blocked.status_code, 409)
        override = self.client.post(
            f"/training/classes/{second_class.json()['id']}/schedule",
            headers=self.admin_headers,
            json={**conflict_payload, "override_conflicts": True},
        )
        self.assertEqual(override.status_code, 201, override.text)
        start = date.today() + timedelta(days=1)
        calendar = self.client.get(
            f"/training/sessions?start={start.isoformat()}&end={(start + timedelta(days=30)).isoformat()}&class_id={class_id}",
            headers=self.admin_headers,
        )
        self.assertEqual(calendar.status_code, 200)
        self.assertEqual(len(calendar.json()), 2)
        lesson_id = saved.json()["sessions"][0]["id"]
        attendance = self.client.post(
            f"/training/sessions/{lesson_id}/attendance/bulk-present",
            headers=self.admin_headers,
        )
        self.assertEqual(attendance.status_code, 200, attendance.text)
        roster = self.client.get(
            f"/training/sessions/{lesson_id}/attendance", headers=self.admin_headers
        ).json()["items"]
        attendance_update = self.client.put(
            f"/training/sessions/{lesson_id}/attendance",
            headers=self.admin_headers,
            json={"items": [{"student_id": student["id"], "status": "late"}]},
        )
        self.assertEqual(attendance_update.status_code, 200, attendance_update.text)
        self.assertEqual(attendance_update.json()["updated_count"], len(roster))
        second_lesson_id = saved.json()["sessions"][1]["id"]
        with main.SessionLocal() as db:
            student_user = db.get(main.User, student["user_id"])
            student_user.password_hash = main.hash_password("StudentTest123")
            db.commit()
            student_headers = {"Authorization": f"Bearer {main.encode_token(student_user)}"}
        absence = self.client.post(
            "/attendance/absence-requests",
            headers=student_headers,
            json={"lesson_id": lesson_id, "reason": "Medical appointment", "evidence_ref": "upload:absence-1"},
        )
        self.assertEqual(absence.status_code, 201, absence.text)
        absence_list = self.client.get(
            "/attendance/absence-requests", headers=self.admin_headers
        ).json()
        self.assertEqual(absence_list[0]["student_name"], student["full_name"])
        self.assertEqual(absence_list[0]["lesson_id"], lesson_id)
        paged_absences = self.client.get(
            "/attendance/absence-requests?page=1&page_size=1", headers=self.admin_headers
        ).json()
        self.assertEqual(paged_absences["total"], 1)
        self.assertEqual(paged_absences["page"], 1)
        self.assertEqual(paged_absences["items"][0]["id"], absence.json()["id"])
        empty_absence_page = self.client.get(
            "/attendance/absence-requests?page=2&page_size=1", headers=self.admin_headers
        ).json()
        self.assertEqual(empty_absence_page["items"], [])
        self.assertEqual(empty_absence_page["total"], 1)
        self.assertEqual(
            self.client.get(
                "/attendance/absence-requests?page=1&page_size=101", headers=self.admin_headers
            ).status_code,
            422,
        )
        student_absences = self.client.get(
            "/attendance/absence-requests?page=1&page_size=20", headers=student_headers
        ).json()
        self.assertEqual(student_absences["total"], 1)
        self.assertEqual(student_absences["items"][0]["id"], absence.json()["id"])
        decision = self.client.post(
            f"/attendance/absence-requests/{absence.json()['id']}/decision",
            headers=self.admin_headers,
            json={"decision": "approve", "reason": "Evidence checked"},
        )
        self.assertEqual(decision.status_code, 200, decision.text)
        student_attendance = self.client.get(
            f"/training/sessions/{lesson_id}/attendance", headers=student_headers
        )
        self.assertEqual(student_attendance.json()["items"][0]["status"], "excused")
        self.assertTrue(self.client.get("/notifications", headers=student_headers).json()["items"])
        unsupported_upload = self.client.post(
            "/attendance/absence-requests/upload",
            headers=student_headers,
            data={"lesson_id": str(second_lesson_id), "reason": "Medical appointment"},
            files={"file": ("evidence.pdf", b"not a PDF", "application/pdf")},
        )
        self.assertEqual(unsupported_upload.status_code, 415, unsupported_upload.text)
        oversized_upload = self.client.post(
            "/attendance/absence-requests/upload",
            headers=student_headers,
            data={"lesson_id": str(second_lesson_id), "reason": "Medical appointment"},
            files={"file": (
                "large.pdf",
                b"%PDF-1.4\n" + b"x" * sprint34.ABSENCE_EVIDENCE_MAX_BYTES,
                "application/pdf",
            )},
        )
        self.assertEqual(oversized_upload.status_code, 413, oversized_upload.text)
        uploaded_evidence = self.client.post(
            "/attendance/absence-requests/upload",
            headers=student_headers,
            data={"lesson_id": str(second_lesson_id), "reason": "Medical appointment"},
            files={"file": ("evidence.pdf", b"%PDF-1.4\nsprint34 test\n", "application/pdf")},
        )
        self.assertEqual(uploaded_evidence.status_code, 201, uploaded_evidence.text)
        evidence_ref = uploaded_evidence.json()["evidence_ref"]
        self.assertTrue(evidence_ref.startswith("private:"))
        stored_evidence = sprint34.ABSENCE_EVIDENCE_DIR / evidence_ref.removeprefix("private:")
        self.addCleanup(stored_evidence.unlink, missing_ok=True)
        student_download = self.client.get(
            f"/attendance/absence-requests/{uploaded_evidence.json()['id']}/evidence",
            headers=student_headers,
        )
        self.assertEqual(student_download.status_code, 200)
        self.assertEqual(student_download.content, b"%PDF-1.4\nsprint34 test\n")
        self.assertEqual(student_download.headers["cache-control"], "private, no-store")
        with main.SessionLocal() as db:
            other_student = main.User(
                full_name="Unrelated Student",
                email="unrelated-student34@example.test",
                password_hash=main.hash_password("OtherStudent123"),
                role="student",
            )
            db.add(other_student)
            db.flush()
            db.add(main.UserRoleAssignment(user_id=other_student.id, role="student"))
            db.commit()
        other_login = self.client.post(
            "/auth/login",
            json={"email": "unrelated-student34@example.test", "password": "OtherStudent123"},
        )
        self.assertEqual(other_login.status_code, 200, other_login.text)
        other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}
        forbidden_download = self.client.get(
            f"/attendance/absence-requests/{uploaded_evidence.json()['id']}/evidence",
            headers=other_headers,
        )
        self.assertEqual(forbidden_download.status_code, 403)
        self.assertEqual(student_download.headers["x-content-type-options"], "nosniff")
        unauthenticated_download = self.client.get(
            f"/attendance/absence-requests/{uploaded_evidence.json()['id']}/evidence"
        )
        self.assertEqual(unauthenticated_download.status_code, 401)
        rescheduled = self.client.patch(
            f"/training/sessions/{lesson_id}",
            headers=self.admin_headers,
            json={"starts_at": (start_date + timedelta(days=14)).isoformat() + "T10:00:00"},
        )
        self.assertEqual(rescheduled.status_code, 409)
        self.assertEqual(rescheduled.json()["detail"], "Không thể đổi buổi đã điểm danh hoặc đã hủy")
        cancelled = self.client.post(
            f"/training/sessions/{second_lesson_id}/cancel",
            headers=self.admin_headers,
            json={"reason": "Room maintenance"},
        )
        self.assertEqual(cancelled.status_code, 200, cancelled.text)
        self.assertEqual(cancelled.json()["status"], "cancelled")
        deferred_from = date.today() + timedelta(days=10)
        deferred = self.client.post(
            f"/students/{student['id']}/status",
            headers=self.admin_headers,
            json={"action": "defer", "effective_date": deferred_from.isoformat(), "reason": "Medical leave"},
        )
        self.assertEqual(deferred.status_code, 200, deferred.text)
        profile = self.client.get(
            f"/students/{student['id']}", headers=self.admin_headers
        )
        self.assertEqual(profile.json()["status_history"][0]["action"], "deferred")
        self.assertEqual(profile.json()["class_history"][0]["status"], "deferred")
        past_roster = self.client.get(
            f"/training/sessions/{lesson_id}/attendance", headers=self.admin_headers
        )
        later_roster = self.client.get(
            f"/training/sessions/{second_lesson_id}/attendance", headers=self.admin_headers
        )
        self.assertEqual(len(past_roster.json()["items"]), 1)
        self.assertEqual(later_roster.json()["items"], [])
        roster = self.client.get(
            f"/training/sessions/{lesson_id}/attendance", headers=self.admin_headers
        )
        self.assertEqual(roster.status_code, 200)
        self.assertEqual(roster.json()["items"][0]["student_id"], student["id"])

    def test_schedule_preview_supports_multiple_weekdays_and_biweekly_recurrence(self):
        subject_id, class_id = self._base_program_and_class("-MULTI")
        start_date = date.today() + timedelta(days=7)
        weekdays = [start_date.weekday(), (start_date + timedelta(days=1)).weekday()]
        templates = self.client.get(
            f"/training/subjects/{subject_id}/sessions", headers=self.admin_headers
        ).json()
        preview = self.client.post(
            f"/training/classes/{class_id}/schedule/preview",
            headers=self.admin_headers,
            json={
                "weekdays": weekdays,
                "recurrence": "biweekly",
                "session_time": "18:00",
                "session_duration_minutes": 120,
                "start_date": start_date.isoformat(),
                "count": 4,
                "subject_session_ids": [item["id"] for item in templates] * 2,
            },
        )
        self.assertEqual(preview.status_code, 200, preview.text)
        starts = [date.fromisoformat(item["starts_at"][:10]) for item in preview.json()["sessions"]]
        self.assertEqual(starts, [
            start_date,
            start_date + timedelta(days=1),
            start_date + timedelta(days=14),
            start_date + timedelta(days=15),
        ])

    def test_rejected_lead_requires_reason_and_schedule_is_bounded(self):
        lead = self.client.post(
            "/leads",
            headers=self.admin_headers,
            json={"full_name": "Rejected Lead", "phone": "0907654323"},
        ).json()
        rejected = self.client.patch(
            f"/leads/{lead['id']}", headers=self.admin_headers, json={"status": "rejected"}
        )
        self.assertEqual(rejected.status_code, 422)
        rejected = self.client.patch(
            f"/leads/{lead['id']}", headers=self.admin_headers,
            json={"status": "rejected", "loss_reason": "Not interested"},
        )
        self.assertEqual(rejected.status_code, 200)
        out_of_range = self.client.get(
            f"/training/sessions?start={date.today().isoformat()}&end={(date.today() + timedelta(days=100)).isoformat()}",
            headers=self.admin_headers,
        )
        self.assertEqual(out_of_range.status_code, 422)

    def test_student_and_class_lists_paginate_and_filter_consistently(self):
        student_ids = []
        for index in ("One", "Two"):
            lead = self.client.post(
                "/leads",
                headers=self.admin_headers,
                json={
                    "full_name": f"Pagination Student {index}",
                    "phone": f"09076543{24 if index == 'One' else 25}",
                    "email": f"pagination-{index.lower()}@example.test",
                },
            )
            self.assertEqual(lead.status_code, 201, lead.text)
            marked_won = self.client.patch(
                f"/leads/{lead.json()['id']}",
                headers=self.admin_headers,
                json={"status": "won"},
            )
            self.assertEqual(marked_won.status_code, 200, marked_won.text)
            with patch.object(main, "send_email", return_value=True):
                converted = self.client.post(
                    f"/leads/{lead.json()['id']}/convert",
                    headers=self.admin_headers,
                )
            self.assertEqual(converted.status_code, 200, converted.text)
            student_ids.append(converted.json()["student"]["id"])

        student_pages = [
            self.client.get(
                f"/students?q=Pagination%20Student&page={page}&page_size=1",
                headers=self.admin_headers,
            )
            for page in (1, 2, 3)
        ]
        for response in student_pages:
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["total"], 2)
            self.assertEqual(response.json()["page_size"], 1)
        self.assertEqual([len(response.json()["items"]) for response in student_pages], [1, 1, 0])
        self.assertEqual(
            {response.json()["items"][0]["id"] for response in student_pages[:2]},
            set(student_ids),
        )
        self.assertEqual(
            self.client.get("/students?page_size=101", headers=self.admin_headers).status_code,
            422,
        )

        for suffix in ("-PAGE-1", "-PAGE-2"):
            self._base_program_and_class(suffix)
        class_pages = [
            self.client.get(
                f"/training/classes?q=class-PAGE&page={page}&page_size=1",
                headers=self.admin_headers,
            )
            for page in (1, 2, 3)
        ]
        for response in class_pages:
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["total"], 2)
            self.assertEqual(response.json()["page_size"], 1)
        self.assertEqual([len(response.json()["items"]) for response in class_pages], [1, 1, 0])
        self.assertNotEqual(
            class_pages[0].json()["items"][0]["id"],
            class_pages[1].json()["items"][0]["id"],
        )
        self.assertEqual(
            self.client.get(
                "/training/classes?page_size=101", headers=self.admin_headers
            ).status_code,
            422,
        )


if __name__ == "__main__":
    unittest.main()
