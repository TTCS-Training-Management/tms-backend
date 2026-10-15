from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from fastapi import HTTPException

import sprint34


class StudentSelfProfileTests(TestCase):
    def test_returns_the_authenticated_students_profile(self):
        student = object()
        expected = {"id": 17, "full_name": "Test Student"}
        db = Mock()
        db.scalar.return_value = student

        with patch.object(sprint34, "_student_json", return_value=expected) as serialize:
            result = sprint34.student_own_profile(SimpleNamespace(id=9), db)

        self.assertEqual(result, expected)
        serialize.assert_called_once_with(student, db)

    def test_reports_when_account_has_no_linked_profile(self):
        db = Mock()
        db.scalar.return_value = None

        with self.assertRaises(HTTPException) as raised:
            sprint34.student_own_profile(SimpleNamespace(id=9), db)

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(raised.exception.detail, "Tài khoản chưa được liên kết với hồ sơ học viên")
