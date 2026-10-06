import base64
import hashlib
import hmac
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from openpyxl import Workbook, load_workbook
from sqlalchemy import select

_test_database = tempfile.TemporaryDirectory(prefix="tms-sprint1-")
_database_path = Path(_test_database.name) / "sprint1.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_database_path.as_posix()}"

import main


class Sprint1ApiTests(unittest.TestCase):
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
        main.engine.dispose()
        _test_database.cleanup()

    def test_permission_matrix_defaults_to_deny(self):
        roles = self.client.get("/auth/roles", headers=self.admin_headers)
        self.assertEqual(
            {role["code"] for role in roles.json()},
            set(main.ROLE_CODES),
        )
        self.assertTrue(main.permission_allows(["admin"], "billing", "full"))
        self.assertTrue(main.permission_allows(["training_manager"], "users", "read"))
        self.assertFalse(main.permission_allows(["training_manager"], "users", "write"))
        self.assertFalse(main.permission_allows(["instructor"], "billing", "read"))
        self.assertTrue(main.permission_allows(["instructor"], "attendance", "write"))
        self.assertFalse(main.permission_allows(["unknown"], "users", "read"))

    def test_relative_sqlite_url_resolves_from_backend_directory(self):
        resolved = main.make_url(main.resolve_database_url("sqlite:///./tms.db"))
        expected = (Path(main.__file__).resolve().parent / "tms.db").resolve()
        self.assertEqual(Path(resolved.database), expected)

    def test_create_search_filter_and_paginate_accounts(self):
        activation_messages = []
        with patch.object(
            main,
            "send_email",
            side_effect=lambda message: activation_messages.append(message) or True,
        ):
            response = self.client.post(
                "/users",
                headers=self.admin_headers,
                json={
                    "full_name": "Nguyễn An",
                    "email": "nguyen.an@example.test",
                    "phone": "0901234567",
                    "roles": ["instructor", "ta"],
                    "assigned_classes": ["TMS-K14", "TMS-K15"],
                },
            )
        self.assertEqual(response.status_code, 201)
        account = response.json()
        self.assertEqual(account["roles"], ["instructor", "ta"])
        self.assertTrue(account["must_change_password"])
        self.assertTrue(account["handover_required"])
        self.assertEqual(activation_messages[0]["To"], "nguyen.an@example.test")
        self.assertIn("mật khẩu tạm thời", activation_messages[0].get_content())

        response = self.client.get(
            "/users?q=0901234567&role=ta&page=1&page_size=20",
            headers=self.admin_headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 1)
        self.assertEqual(response.json()["items"][0]["email"], "nguyen.an@example.test")

    def test_permission_is_checked_on_server(self):
        with main.SessionLocal() as db:
            manager = main.User(
                full_name="Training Manager",
                email="manager@example.test",
                password_hash=main.hash_password("Manager123"),
                role="training_manager",
            )
            instructor = main.User(
                full_name="Instructor",
                email="instructor@example.test",
                password_hash=main.hash_password("Instructor123"),
                role="instructor",
            )
            db.add_all([manager, instructor])
            db.flush()
            db.add_all(
                [
                    main.UserRoleAssignment(user_id=manager.id, role="training_manager"),
                    main.UserRoleAssignment(user_id=instructor.id, role="instructor"),
                ]
            )
            db.commit()
            manager_id = manager.id
            manager_token = main.encode_token(manager)
            instructor_token = main.encode_token(instructor)

        manager_headers = {"Authorization": f"Bearer {manager_token}"}
        instructor_headers = {"Authorization": f"Bearer {instructor_token}"}
        manager_profile = self.client.get("/auth/me", headers=manager_headers).json()
        instructor_profile = self.client.get("/auth/me", headers=instructor_headers).json()
        self.assertEqual(manager_profile["permissions"]["users"], "R")
        self.assertEqual(manager_profile["permissions"]["billing"], "R")
        self.assertEqual(instructor_profile["permissions"]["attendance"], "W")
        self.assertEqual(instructor_profile["permissions"]["billing"], "-")
        self.assertEqual(self.client.get("/users", headers=manager_headers).status_code, 200)
        self.assertEqual(self.client.get("/users", headers=instructor_headers).status_code, 403)
        self.assertEqual(
            self.client.post(
                "/users",
                headers=manager_headers,
                json={
                    "full_name": "No Admin",
                    "email": "no-admin@example.test",
                    "roles": ["student"],
                },
            ).status_code,
            403,
        )
        updated_roles = self.client.patch(
            f"/users/{manager_id}/role",
            headers=self.admin_headers,
            json={"roles": ["training_manager", "instructor"]},
        )
        self.assertEqual(updated_roles.status_code, 200)
        self.assertEqual(
            self.client.get("/users", headers=manager_headers).status_code, 200
        )
        removed_manager_role = self.client.patch(
            f"/users/{manager_id}/role",
            headers=self.admin_headers,
            json={"roles": ["instructor"]},
        )
        self.assertEqual(removed_manager_role.status_code, 200)
        self.assertEqual(
            self.client.get("/users", headers=manager_headers).status_code, 403
        )

    def test_account_is_not_created_when_activation_email_cannot_be_sent(self):
        with patch.object(main, "send_email", return_value=False):
            response = self.client.post(
                "/users",
                headers=self.admin_headers,
                json={
                    "full_name": "No Email Account",
                    "email": "no-email@example.test",
                    "roles": ["student"],
                },
            )
        self.assertEqual(response.status_code, 503)
        listing = self.client.get(
            "/users?q=no-email@example.test",
            headers=self.admin_headers,
        )
        self.assertEqual(listing.json()["total"], 0)

    def test_lock_requires_reason_and_invalidates_existing_sessions(self):
        with main.SessionLocal() as db:
            staff = main.User(
                full_name="Teacher To Lock",
                email="teacher@example.test",
                password_hash=main.hash_password("Teacher123"),
                role="instructor",
            )
            db.add(staff)
            db.flush()
            db.add(main.UserRoleAssignment(user_id=staff.id, role="instructor"))
            db.add(
                main.UserClassAssignment(user_id=staff.id, class_name="TMS-K16")
            )
            db.commit()
            staff_id = staff.id
            staff_token = main.encode_token(staff)

        response = self.client.patch(
            f"/users/{staff_id}/status",
            headers=self.admin_headers,
            json={"active": False, "reason": ""},
        )
        self.assertEqual(response.status_code, 422)

        response = self.client.patch(
            f"/users/{staff_id}/status",
            headers=self.admin_headers,
            json={"active": False, "reason": "Nghỉ việc"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["handover_required"])
        self.assertEqual(response.json()["assigned_classes"], ["TMS-K16"])
        self.assertEqual(
            self.client.get(
                "/auth/me", headers={"Authorization": f"Bearer {staff_token}"}
            ).status_code,
            401,
        )

    def test_locked_account_cannot_login_and_can_login_after_unlock(self):
        with main.SessionLocal() as db:
            staff = main.User(
                full_name="Lock and Unlock User",
                email="lock-unlock@example.test",
                password_hash=main.hash_password("LockUnlock123"),
                role="instructor",
            )
            db.add(staff)
            db.flush()
            db.add(main.UserRoleAssignment(user_id=staff.id, role="instructor"))
            db.commit()
            staff_id = staff.id

        locked = self.client.patch(
            f"/users/{staff_id}/status",
            headers=self.admin_headers,
            json={"active": False, "reason": "Nghỉ việc"},
        )
        self.assertEqual(locked.status_code, 200)
        rejected_login = self.client.post(
            "/auth/login",
            json={"email": "lock-unlock@example.test", "password": "LockUnlock123"},
        )
        self.assertEqual(rejected_login.status_code, 403)

        unlocked = self.client.patch(
            f"/users/{staff_id}/status",
            headers=self.admin_headers,
            json={"active": True},
        )
        self.assertEqual(unlocked.status_code, 200)
        self.assertTrue(unlocked.json()["is_active"])
        self.assertIsNone(unlocked.json()["lock_reason"])
        accepted_login = self.client.post(
            "/auth/login",
            json={"email": "lock-unlock@example.test", "password": "LockUnlock123"},
        )
        self.assertEqual(accepted_login.status_code, 200)

    def test_logout_revokes_session_on_server(self):
        with main.SessionLocal() as db:
            user = main.User(
                full_name="Logout User",
                email="logout@example.test",
                password_hash=main.hash_password("LogoutPass123"),
                role="student",
            )
            db.add(user)
            db.flush()
            db.add(main.UserRoleAssignment(user_id=user.id, role="student"))
            db.commit()
            token = main.encode_token(user)
        headers = {"Authorization": f"Bearer {token}"}
        self.assertEqual(self.client.post("/auth/logout", headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/auth/me", headers=headers).status_code, 401)

    def test_refresh_renews_session_and_logout_invalidates_every_token(self):
        with main.SessionLocal() as db:
            user = main.User(
                full_name="Refresh User",
                email="refresh@example.test",
                password_hash=main.hash_password("RefreshPass123"),
                role="student",
            )
            db.add(user)
            db.flush()
            db.add(main.UserRoleAssignment(user_id=user.id, role="student"))
            db.commit()
        login = self.client.post(
            "/auth/login",
            json={"email": "refresh@example.test", "password": "RefreshPass123"},
        )
        old_token = login.json()["access_token"]
        old_claims = main.decode_token(old_token)
        refreshed = self.client.post(
            "/auth/refresh",
            headers={"Authorization": f"Bearer {old_token}"},
        )
        self.assertEqual(refreshed.status_code, 200)
        new_token = refreshed.json()["access_token"]
        self.assertNotEqual(old_token, new_token)
        new_claims = main.decode_token(new_token)
        self.assertEqual(new_claims["started"], old_claims["started"])
        self.assertEqual(new_claims["max_exp"], old_claims["max_exp"])
        self.assertEqual(
            self.client.get(
                "/auth/me", headers={"Authorization": f"Bearer {new_token}"}
            ).status_code,
            200,
        )
        logged_out = self.client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {new_token}"},
        )
        self.assertEqual(logged_out.status_code, 200)
        for token in (old_token, new_token):
            self.assertEqual(
                self.client.get(
                    "/auth/me", headers={"Authorization": f"Bearer {token}"}
                ).status_code,
                401,
            )

    def test_expired_session_is_rejected(self):
        payload = {
            "sub": 1,
            "ver": 0,
            "jti": "expired-test-token",
            "exp": 1,
            "started": 1,
            "last": 1,
            "max_exp": 1,
        }
        body = base64.urlsafe_b64encode(
            json.dumps(payload, separators=(",", ":")).encode()
        ).decode()
        signature = hmac.new(
            main.TOKEN_SECRET.encode(), body.encode(), hashlib.sha256
        ).hexdigest()
        response = self.client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {body}.{signature}"},
        )
        self.assertEqual(response.status_code, 401)

    def test_admin_cannot_remove_own_admin_role(self):
        admin_id = self.client.get("/auth/me", headers=self.admin_headers).json()["id"]
        response = self.client.patch(
            f"/users/{admin_id}/role",
            headers=self.admin_headers,
            json={"roles": ["instructor"]},
        )
        self.assertEqual(response.status_code, 400)

    def test_delete_account_removes_user_assignments_and_reset_tokens(self):
        with main.SessionLocal() as db:
            user = main.User(
                full_name="Delete User",
                email="delete-user@example.test",
                password_hash=main.hash_password("DeletePass123"),
                role="instructor",
            )
            db.add(user)
            db.flush()
            db.add_all(
                [
                    main.UserRoleAssignment(user_id=user.id, role="instructor"),
                    main.UserClassAssignment(user_id=user.id, class_name="TMS-K14"),
                    main.PasswordResetToken(
                        token_hash=hashlib.sha256(b"delete-user-token").hexdigest(),
                        user_id=user.id,
                        expires_at=datetime.now(timezone.utc).replace(tzinfo=None)
                        + timedelta(minutes=30),
                    ),
                ]
            )
            db.commit()
            user_id = user.id
            token = main.encode_token(user)

        response = self.client.delete(
            f"/users/{user_id}",
            headers=self.admin_headers,
        )
        self.assertEqual(response.status_code, 204)
        with main.SessionLocal() as db:
            self.assertIsNone(db.get(main.User, user_id))
            self.assertEqual(
                db.scalar(
                    select(main.UserRoleAssignment).where(
                        main.UserRoleAssignment.user_id == user_id
                    )
                ),
                None,
            )
            self.assertEqual(
                db.scalar(
                    select(main.UserClassAssignment).where(
                        main.UserClassAssignment.user_id == user_id
                    )
                ),
                None,
            )
            self.assertEqual(
                db.scalar(
                    select(main.PasswordResetToken).where(
                        main.PasswordResetToken.user_id == user_id
                    )
                ),
                None,
            )
        self.assertEqual(
            self.client.get(
                "/auth/me",
                headers={"Authorization": "Bearer " + token},
            ).status_code,
            401,
        )

    def test_admin_cannot_delete_self(self):
        admin_id = self.client.get("/auth/me", headers=self.admin_headers).json()["id"]
        self_delete = self.client.delete(f"/users/{admin_id}", headers=self.admin_headers)
        self.assertEqual(self_delete.status_code, 400, self_delete.text)

    def test_password_reset_is_generic_single_use_and_expires(self):
        with main.SessionLocal() as db:
            reset_user = main.User(
                full_name="Reset User",
                email="reset@example.test",
                password_hash=main.hash_password("ResetPass123"),
                role="student",
            )
            db.add(reset_user)
            db.flush()
            db.add(main.UserRoleAssignment(user_id=reset_user.id, role="student"))
            db.commit()
        messages = []
        with (
            patch.object(
                main,
                "send_email",
                side_effect=lambda message: messages.append(message) or True,
            ),
            patch.object(main.secrets, "token_urlsafe", return_value="one-time-reset"),
        ):
            known = self.client.post(
                "/auth/forgot-password",
                json={"email": "reset@example.test"},
            )
            unknown = self.client.post(
                "/auth/forgot-password",
                json={"email": "nobody@example.test"},
            )
        self.assertEqual(known.json(), unknown.json())
        self.assertIn("?reset_token=one-time-reset", messages[0].get_content())
        with main.SessionLocal() as db:
            reset_record = db.scalar(
                select(main.PasswordResetToken).where(
                    main.PasswordResetToken.token_hash
                    == hashlib.sha256(b"one-time-reset").hexdigest()
                )
            )
            self.assertIsNotNone(reset_record)

        response = self.client.post(
            "/auth/reset-password",
            json={"token": "one-time-reset", "new_password": "UpdatedPass123"},
        )
        self.assertEqual(response.status_code, 200)
        with main.SessionLocal() as db:
            db.expire_all()
            reset_record = db.scalar(
                select(main.PasswordResetToken).where(
                    main.PasswordResetToken.token_hash
                    == hashlib.sha256(b"one-time-reset").hexdigest()
                )
            )
            self.assertIsNotNone(reset_record.used_at)
        reused = self.client.post(
            "/auth/reset-password",
            json={"token": "one-time-reset", "new_password": "AnotherPass123"},
        )
        self.assertEqual(reused.status_code, 400)

    def test_change_password_validates_current_password_and_revokes_old_sessions(self):
        with main.SessionLocal() as db:
            user = main.User(
                full_name="Password Change User",
                email="password-change@example.test",
                password_hash=main.hash_password("CurrentPass123"),
                role="student",
            )
            db.add(user)
            db.flush()
            db.add(main.UserRoleAssignment(user_id=user.id, role="student"))
            db.commit()
            old_token = main.encode_token(user)

        headers = {"Authorization": f"Bearer {old_token}"}
        invalid_current = self.client.post(
            "/auth/change-password",
            headers=headers,
            json={
                "current_password": "WrongPass123",
                "new_password": "UpdatedPass123",
            },
        )
        self.assertEqual(invalid_current.status_code, 400)
        changed = self.client.post(
            "/auth/change-password",
            headers=headers,
            json={
                "current_password": "CurrentPass123",
                "new_password": "UpdatedPass123",
            },
        )
        self.assertEqual(changed.status_code, 200)
        new_token = changed.json()["access_token"]
        self.assertEqual(
            self.client.get("/auth/me", headers=headers).status_code,
            401,
        )
        self.assertEqual(
            self.client.get(
                "/auth/me", headers={"Authorization": f"Bearer {new_token}"}
            ).status_code,
            200,
        )
        old_password_login = self.client.post(
            "/auth/login",
            json={
                "email": "password-change@example.test",
                "password": "CurrentPass123",
            },
        )
        new_password_login = self.client.post(
            "/auth/login",
            json={
                "email": "password-change@example.test",
                "password": "UpdatedPass123",
            },
        )
        self.assertEqual(old_password_login.status_code, 401)
        self.assertEqual(new_password_login.status_code, 200)

    def test_expired_reset_token_is_rejected(self):
        with main.SessionLocal() as db:
            reset_user = main.User(
                full_name="Expired Reset User",
                email="expired-reset@example.test",
                password_hash=main.hash_password("ExpiredPass123"),
                role="student",
            )
            db.add(reset_user)
            db.flush()
            db.add(main.UserRoleAssignment(user_id=reset_user.id, role="student"))
            db.add(
                main.PasswordResetToken(
                    token_hash=hashlib.sha256(b"expired-reset").hexdigest(),
                    user_id=reset_user.id,
                    expires_at=datetime.now(timezone.utc).replace(tzinfo=None)
                    - timedelta(seconds=1),
                )
            )
            db.commit()
        response = self.client.post(
            "/auth/reset-password",
            json={"token": "expired-reset", "new_password": "NewPassword123"},
        )
        self.assertEqual(response.status_code, 400)

    def test_idle_and_absolute_session_expiry(self):
        now = int(datetime.now(timezone.utc).timestamp())
        for name, claims in (
            (
                "idle",
                {
                    "sub": 1,
                    "ver": 0,
                    "jti": "idle-expired",
                    "started": now - 120,
                    "last": now - 901,
                    "max_exp": now + 1000,
                    "exp": now + 1000,
                },
            ),
            (
                "absolute",
                {
                    "sub": 1,
                    "ver": 0,
                    "jti": "absolute-expired",
                    "started": now - 8 * 60 * 60,
                    "last": now,
                    "max_exp": now - 1,
                    "exp": now + 1000,
                },
            ),
        ):
            with self.subTest(name=name):
                body = base64.urlsafe_b64encode(
                    json.dumps(claims, separators=(",", ":")).encode()
                ).decode()
                signature = hmac.new(
                    main.TOKEN_SECRET.encode(), body.encode(), hashlib.sha256
                ).hexdigest()
                response = self.client.get(
                    "/auth/me",
                    headers={"Authorization": f"Bearer {body}.{signature}"},
                )
                self.assertEqual(response.status_code, 401)
        with main.SessionLocal() as db:
            user = db.scalar(select(main.User).where(main.User.email == "admin@tms.local"))
            self.assertIsNotNone(user)
            idle_token = main.encode_token(user)
        token_body = idle_token.split(".", 1)[0]
        claims = json.loads(base64.urlsafe_b64decode(token_body.encode()))
        claims["last"] = now - 901
        body = base64.urlsafe_b64encode(
            json.dumps(claims, separators=(",", ":")).encode()
        ).decode()
        signature = hmac.new(
            main.TOKEN_SECRET.encode(), body.encode(), hashlib.sha256
        ).hexdigest()
        idle_token = f"{body}.{signature}"
        refreshed = self.client.post(
            "/auth/refresh",
            headers={"Authorization": f"Bearer {idle_token}"},
        )
        self.assertEqual(refreshed.status_code, 401)

    def test_five_bad_passwords_temporarily_lock_account(self):
        statuses = []
        for _ in range(5):
            response = self.client.post(
                "/auth/login",
                json={"email": "accountant@tms.local", "password": "WrongPassword1"},
            )
            statuses.append(response.status_code)
        self.assertEqual(statuses, [401, 401, 401, 401, 423])
        self.assertEqual(response.headers["retry-after"], "900")

        blocked_retry = self.client.post(
            "/auth/login",
            json={"email": "accountant@tms.local", "password": "WrongPassword1"},
        )
        self.assertEqual(blocked_retry.status_code, 423)
        self.assertGreater(int(blocked_retry.headers["retry-after"]), 0)
        with main.SessionLocal() as db:
            account = db.scalar(
                select(main.User).where(main.User.email == "accountant@tms.local")
            )
            self.assertEqual(account.failed_login_attempts, 5)

    def test_login_does_not_reveal_whether_email_exists(self):
        known = self.client.post(
            "/auth/login",
            json={"email": "admin@tms.local", "password": "WrongPassword1"},
        )
        unknown = self.client.post(
            "/auth/login",
            json={"email": "missing@example.test", "password": "WrongPassword1"},
        )
        self.assertEqual(known.status_code, 401)
        self.assertEqual(known.json()["detail"], unknown.json()["detail"])

    def test_profile_update_avatar_upload_and_serving(self):
        profile = self.client.patch(
            "/profile",
            headers=self.admin_headers,
            json={
                "full_name": "Admin Updated",
                "phone": "0901234567",
                "date_of_birth": "1990-01-02",
                "address": "Thai Nguyen",
            },
        )
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.json()["date_of_birth"], "1990-01-02")

        cleared = self.client.patch(
            "/profile",
            headers=self.admin_headers,
            json={"date_of_birth": None},
        )
        self.assertEqual(cleared.status_code, 200)
        self.assertIsNone(cleared.json()["date_of_birth"])

        with tempfile.TemporaryDirectory(prefix="tms-avatar-test-") as directory:
            with patch.object(main, "UPLOADS_DIR", Path(directory)):
                uploaded = self.client.post(
                    "/profile/avatar",
                    headers=self.admin_headers,
                    files={"file": ("avatar.png", b"test-image", "image/png")},
                )
                self.assertTrue((Path(directory) / "avatar_1.png").exists())
        self.assertEqual(uploaded.status_code, 200)

    def test_user_import_template_and_row_summary(self):
        template = self.client.get(
            "/users/import-excel/template",
            headers=self.admin_headers,
        )
        self.assertEqual(template.status_code, 200)
        workbook = load_workbook(BytesIO(template.content), read_only=True)
        self.assertEqual(
            list(next(workbook.active.iter_rows(values_only=True))),
            ["full_name", "email", "roles", "phone", "assigned_classes", "initial_password"],
        )
        workbook.close()

        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["full_name", "email", "roles", "phone", "assigned_classes", "initial_password"])
        sheet.append(["Import User", "imported@example.test", "student", "0901234567", "Class A", "Temporary123!"])
        sheet.append(["", "missing-name@example.test", "student", "", "", ""])
        sheet.append(["Invalid Email", "not-an-email", "student", "", "", "Temporary123!"])
        sheet.append(["Duplicate User", "imported@example.test", "student", "", "", "Temporary123!"])
        sheet.append(["Invalid Role", "invalid-role@example.test", "student,unknown-role", "", "", "Temporary123!"])
        sheet.append(["Weak Password", "weak-password@example.test", "student", "", "", "weak"])
        content = BytesIO()
        workbook.save(content)
        with patch.object(main, "smtp_configured", return_value=False):
            preview = self.client.post(
                "/users/import-excel/preview",
                headers=self.admin_headers,
                files={
                    "file": (
                        "users.xlsx",
                        content.getvalue(),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                },
            )
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.json()["valid"], 1)
        self.assertEqual(preview.json()["skipped"], 5)
        self.assertTrue(any("Dòng 3" in error for error in preview.json()["errors"]))
        self.assertTrue(any("Dòng 4" in error for error in preview.json()["errors"]))
        self.assertTrue(any("Dòng 5" in error for error in preview.json()["errors"]))
        self.assertTrue(any("Dòng 6" in error for error in preview.json()["errors"]))
        self.assertTrue(any("Dòng 7" in error for error in preview.json()["errors"]))
        with patch.object(main, "smtp_configured", return_value=False):
            imported = self.client.post(
                "/users/import-excel",
                headers=self.admin_headers,
                files={
                    "file": (
                        "users.xlsx",
                        content.getvalue(),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                },
            )
        self.assertEqual(imported.status_code, 200)
        self.assertEqual(imported.json()["imported"], 1)
        self.assertEqual(imported.json()["skipped"], 5)
        self.assertIn("Dòng 3", imported.json()["errors"][0])
        self.assertEqual(
            self.client.get("/users?q=imported@example.test", headers=self.admin_headers).json()["total"],
            1,
        )

    def test_public_lead_filter_and_assignment(self):
        created = self.client.post(
            "/leads/public",
            json={
                "full_name": "Sprint Lead",
                "phone": "0902222333",
                "email": "lead@example.test",
                "source": "website",
                "program_interest": "TMS",
                "website": "",
            },
        )
        self.assertEqual(created.status_code, 200)

        assignees = self.client.get("/leads/assignees", headers=self.admin_headers)
        self.assertEqual(assignees.status_code, 200)
        admin_id = self.client.get("/auth/me", headers=self.admin_headers).json()["id"]
        self.assertTrue(any(item["id"] == admin_id for item in assignees.json()))

        leads = self.client.get(
            "/leads?q=Sprint+Lead&status=new",
            headers=self.admin_headers,
        )
        self.assertEqual(leads.status_code, 200)
        lead_id = leads.json()[0]["id"]
        assigned = self.client.post(
            f"/leads/{lead_id}/assign",
            headers=self.admin_headers,
            json={"assigned_to_user_id": admin_id},
        )
        self.assertEqual(assigned.status_code, 200)
        changed = self.client.patch(
            f"/leads/{lead_id}",
            headers=self.admin_headers,
            json={"status": "contacted"},
        )
        self.assertEqual(changed.status_code, 200)
        filtered = self.client.get(
            f"/leads?status=contacted&assigned_to={admin_id}",
            headers=self.admin_headers,
        )
        self.assertEqual(len(filtered.json()), 1)
        internal = self.client.post(
            "/leads",
            headers=self.admin_headers,
            json={
                "full_name": "Walk-in Lead",
                "phone": "0902222444",
                "source": "facebook",
            },
        )
        self.assertEqual(internal.status_code, 201, internal.text)
        internal_listing = self.client.get(
            "/leads?q=Walk-in+Lead",
            headers=self.admin_headers,
        )
        self.assertEqual(internal_listing.json()[0]["source"], "facebook")

    def _create_training_program(self, suffix):
        response = self.client.post(
            "/training/programs",
            headers=self.admin_headers,
            json={"code": f"PRG-{suffix}", "name": f"Program {suffix}"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["id"]

    def _create_training_subject(self, suffix, session_count=0):
        response = self.client.post(
            "/training/subjects",
            headers=self.admin_headers,
            json={
                "code": f"SUB-{suffix}",
                "name": f"Subject {suffix}",
                "session_count": session_count,
                "weight": 1,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["id"]

    def test_program_delete_is_blocked_by_running_class_and_cleans_catalog_links(self):
        program_id = self._create_training_program("CLASS-RULE")
        subject_id = self._create_training_subject("CLASS-RULE")
        linked = self.client.post(
            f"/training/programs/{program_id}/subjects",
            headers=self.admin_headers,
            json={"subject_id": subject_id, "sequence_order": 1},
        )
        self.assertEqual(linked.status_code, 200, linked.text)
        class_response = self.client.post(
            f"/training/programs/{program_id}/classes",
            headers=self.admin_headers,
            json={"name": "Cohort 01"},
        )
        self.assertEqual(class_response.status_code, 201, class_response.text)
        class_id = class_response.json()["id"]
        running = self.client.patch(
            f"/training/classes/{class_id}",
            headers=self.admin_headers,
            json={"status": "running"},
        )
        self.assertEqual(running.status_code, 200, running.text)

        blocked = self.client.delete(
            f"/training/programs/{program_id}",
            headers=self.admin_headers,
        )
        self.assertEqual(blocked.status_code, 409)
        inactive = self.client.patch(
            f"/training/programs/{program_id}",
            headers=self.admin_headers,
            json={"status": "inactive"},
        )
        self.assertEqual(inactive.status_code, 200)
        completed = self.client.patch(
            f"/training/classes/{class_id}",
            headers=self.admin_headers,
            json={"status": "completed"},
        )
        self.assertEqual(completed.status_code, 200)
        deleted = self.client.delete(
            f"/training/programs/{program_id}",
            headers=self.admin_headers,
        )
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertEqual(
            self.client.get(
                f"/training/programs/{program_id}/subjects",
                headers=self.admin_headers,
            ).status_code,
            404,
        )

    def test_curriculum_rejects_duplicates_and_foreign_prerequisites_and_persists_order(self):
        program_id = self._create_training_program("ORDER")
        other_program_id = self._create_training_program("OTHER")
        subject_a = self._create_training_subject("ORDER-A")
        subject_b = self._create_training_subject("ORDER-B")
        subject_c = self._create_training_subject("ORDER-C")
        subject_d = self._create_training_subject("ORDER-D")
        foreign_subject = self._create_training_subject("FOREIGN")
        linked_a = self.client.post(
            f"/training/programs/{program_id}/subjects",
            headers=self.admin_headers,
            json={"subject_id": subject_a, "sequence_order": 1},
        )
        self.assertEqual(linked_a.status_code, 200, linked_a.text)
        linked_b = self.client.post(
            f"/training/programs/{program_id}/subjects",
            headers=self.admin_headers,
            json={
                "subject_id": subject_b,
                "sequence_order": 2,
                "prerequisite_subject_id": subject_a,
            },
        )
        self.assertEqual(linked_b.status_code, 200, linked_b.text)
        linked_c = self.client.post(
            f"/training/programs/{program_id}/subjects",
            headers=self.admin_headers,
            json={"subject_id": subject_c, "sequence_order": 3},
        )
        self.assertEqual(linked_c.status_code, 200, linked_c.text)
        duplicate = self.client.post(
            f"/training/programs/{program_id}/subjects",
            headers=self.admin_headers,
            json={"subject_id": subject_a, "sequence_order": 4},
        )
        self.assertEqual(duplicate.status_code, 409)
        foreign = self.client.post(
            f"/training/programs/{other_program_id}/subjects",
            headers=self.admin_headers,
            json={"subject_id": foreign_subject, "sequence_order": 1},
        )
        self.assertEqual(foreign.status_code, 200)
        invalid_prerequisite = self.client.post(
            f"/training/programs/{program_id}/subjects",
            headers=self.admin_headers,
            json={
                "subject_id": subject_d,
                "sequence_order": 4,
                "prerequisite_subject_id": foreign_subject,
            },
        )
        self.assertEqual(invalid_prerequisite.status_code, 422)
        self_prerequisite = self.client.post(
            f"/training/programs/{program_id}/subjects",
            headers=self.admin_headers,
            json={
                "subject_id": foreign_subject,
                "sequence_order": 4,
                "prerequisite_subject_id": foreign_subject,
            },
        )
        self.assertEqual(self_prerequisite.status_code, 422)

        rows = self.client.get(
            f"/training/programs/{program_id}/subjects",
            headers=self.admin_headers,
        ).json()
        reordered = self.client.put(
            f"/training/programs/{program_id}/subjects/order",
            headers=self.admin_headers,
            json={"association_ids": [rows[2]["id"], rows[0]["id"], rows[1]["id"]]},
        )
        self.assertEqual(reordered.status_code, 200, reordered.text)
        persisted = self.client.get(
            f"/training/programs/{program_id}/subjects",
            headers=self.admin_headers,
        ).json()
        self.assertEqual(
            [row["subject_id"] for row in persisted],
            [subject_c, subject_a, subject_b],
        )
        removed = self.client.delete(
            f"/training/programs/{program_id}/subjects/{rows[0]['id']}",
            headers=self.admin_headers,
        )
        self.assertEqual(removed.status_code, 200, removed.text)
        remaining = self.client.get(
            f"/training/programs/{program_id}/subjects",
            headers=self.admin_headers,
        ).json()
        subject_b_link = next(row for row in remaining if row["subject_id"] == subject_b)
        self.assertIsNone(subject_b_link["prerequisite_subject_id"])

    def test_subject_cannot_be_deleted_while_used_by_a_running_class(self):
        program_id = self._create_training_program("SUBJECT-LOCK")
        subject_id = self._create_training_subject("SUBJECT-LOCK")
        self.assertEqual(
            self.client.post(
                f"/training/programs/{program_id}/subjects",
                headers=self.admin_headers,
                json={"subject_id": subject_id, "sequence_order": 1},
            ).status_code,
            200,
        )
        training_class = self.client.post(
            f"/training/programs/{program_id}/classes",
            headers=self.admin_headers,
            json={"name": "Running cohort"},
        ).json()
        self.client.patch(
            f"/training/classes/{training_class['id']}",
            headers=self.admin_headers,
            json={"status": "running"},
        )
        blocked = self.client.delete(
            f"/training/subjects/{subject_id}",
            headers=self.admin_headers,
        )
        self.assertEqual(blocked.status_code, 409)
        self.client.patch(
            f"/training/classes/{training_class['id']}",
            headers=self.admin_headers,
            json={"status": "completed"},
        )
        deleted = self.client.delete(
            f"/training/subjects/{subject_id}",
            headers=self.admin_headers,
        )
        self.assertEqual(deleted.status_code, 200, deleted.text)

    def test_subject_sessions_are_unique_bounded_and_clone_in_order(self):
        source_id = self._create_training_subject("SESSION-SOURCE", session_count=2)
        target_id = self._create_training_subject("SESSION-TARGET", session_count=3)
        for sequence in (1, 2):
            created = self.client.post(
                f"/training/subjects/{source_id}/sessions",
                headers=self.admin_headers,
                json={
                    "sequence": sequence,
                    "title": f"Source session {sequence}",
                    "objectives": f"Objective {sequence}",
                },
            )
            self.assertEqual(created.status_code, 200, created.text)
        target_first = self.client.post(
            f"/training/subjects/{target_id}/sessions",
            headers=self.admin_headers,
            json={"sequence": 1, "title": "Existing target session"},
        )
        self.assertEqual(target_first.status_code, 200, target_first.text)
        cloned = self.client.post(
            f"/training/subjects/{target_id}/sessions/clone",
            headers=self.admin_headers,
            json={"source_subject_id": source_id},
        )
        self.assertEqual(cloned.status_code, 200, cloned.text)
        self.assertEqual(cloned.json()["copied_count"], 2)
        target_sessions = self.client.get(
            f"/training/subjects/{target_id}/sessions",
            headers=self.admin_headers,
        ).json()
        self.assertEqual([item["sequence"] for item in target_sessions], [1, 2, 3])
        self.assertEqual(target_sessions[1]["title"], "Source session 1")
        over_limit_clone = self.client.post(
            f"/training/subjects/{target_id}/sessions/clone",
            headers=self.admin_headers,
            json={"source_subject_id": source_id},
        )
        self.assertEqual(over_limit_clone.status_code, 409)
        duplicate_sequence = self.client.post(
            f"/training/subjects/{target_id}/sessions",
            headers=self.admin_headers,
            json={"sequence": 3, "title": "Duplicate"},
        )
        self.assertEqual(duplicate_sequence.status_code, 409)
        out_of_range = self.client.post(
            f"/training/subjects/{target_id}/sessions",
            headers=self.admin_headers,
            json={"sequence": 4, "title": "Over limit"},
        )
        self.assertEqual(out_of_range.status_code, 422)

    def test_public_lead_honeypot_and_rate_limit(self):
        with main.SessionLocal() as db:
            db.execute(main.delete(main.PublicLeadAttempt))
            db.commit()
        trapped = self.client.post(
            "/leads/public",
            json={
                "full_name": "Bot",
                "phone": "0907654300",
                "website": "spam.example",
            },
        )
        self.assertEqual(trapped.status_code, 400)
        for index in range(5):
            accepted = self.client.post(
                "/leads/public",
                json={
                    "full_name": f"Rate Test {index}",
                    "phone": f"09076543{index:02d}",
                    "website": "",
                },
            )
            self.assertEqual(accepted.status_code, 200, accepted.text)
            self.assertIn("sớm liên hệ", accepted.json()["message"])
        limited = self.client.post(
            "/leads/public",
            json={
                "full_name": "Rate Test Limit",
                "phone": "0907654399",
                "website": "",
            },
        )
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited.headers.get("retry-after"), "600")


if __name__ == "__main__":
    unittest.main()
