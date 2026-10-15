import sys
import unittest
from datetime import datetime, timedelta
try:
    from werkzeug.security import check_password_hash
    from app import app, db, User, PasswordResetToken, hash_token
    HAS_WERKZEUG = True
except ImportError:
    HAS_WERKZEUG = False

@unittest.skipUnless(HAS_WERKZEUG, "Requires Flask and werkzeug")
class TestPasswordResetFlow(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_01_existing_user_request_reset(self):
        """Test: Nhap email ton tai -> Tao token hop le co hieu luc 30 phut"""
        email = "beo810206@gmail.com"
        response = self.client.post("/", data={"email": email})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Nếu email tồn tại trong hệ thống".encode("utf-8"), response.data)

        # Kiem tra token trong database
        user = User.query.filter_by(email=email).first()
        self.assertIsNotNone(user)
        token_record = PasswordResetToken.query.filter_by(user_id=user.id, used=False).order_by(PasswordResetToken.id.desc()).first()
        self.assertIsNotNone(token_record)
        
        # Kiem tra thoi gian het han la khoang 30 phut
        diff = token_record.expires_at - datetime.utcnow()
        self.assertTrue(28 <= diff.total_seconds() / 60 <= 31, "Thoi han phai la 30 phut")
        print("\n[PASSED 1/5] Token reset tao thanh cong voi thoi han 30 phut.")

    def test_02_unknown_email_same_message(self):
        """Yeu cau 3: Email khong ton tai van hien thi cung mot thong bao, khong do duoc tai khoan"""
        fake_email = "nonexistent_hacker_test@gmail.com"
        response = self.client.post("/", data={"email": fake_email})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Nếu email tồn tại trong hệ thống".encode("utf-8"), response.data)
        
        # Khong tao bat ky token nao cho email khong ton tai
        fake_user = User.query.filter_by(email=fake_email).first()
        self.assertIsNone(fake_user)
        print("[PASSED 2/5] Email khong ton tai tra ve cung thong bao, khong lo tai khoan.")

    def test_03_reset_password_success(self):
        """Test: Dung link hop le -> Doi mat khau thanh cong"""
        user = User.query.filter_by(email="beo810206@gmail.com").first()
        import secrets
        raw_token = secrets.token_urlsafe(32)
        hashed = hash_token(raw_token)
        
        token_record = PasswordResetToken(
            user_id=user.id,
            token_hash=hashed,
            expires_at=datetime.utcnow() + timedelta(minutes=30),
            used=False
        )
        db.session.add(token_record)
        db.session.commit()

        # Doi mat khau thanh cong
        new_pass = "NewPassword@2026"
        res = self.client.post(f"/reset-password?token={raw_token}", data={
            "password": new_pass,
            "confirm_password": new_pass
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn("thành công".encode("utf-8"), res.data)

        # Kiem tra mat khau moi da cap nhat trong DB
        db.session.refresh(user)
        self.assertTrue(check_password_hash(user.password, new_pass))
        print("[PASSED 3/5] Doi mat khau moi thanh cong va duoc hash an toan vao Database.")

    def test_04_token_used_only_once(self):
        """Yeu cau 2: Lien ket chi su dung duoc mot lan"""
        import secrets
        user = User.query.filter_by(email="beo810206@gmail.com").first()
        raw_token = secrets.token_urlsafe(32)
        hashed = hash_token(raw_token)
        
        token_record = PasswordResetToken(
            user_id=user.id,
            token_hash=hashed,
            expires_at=datetime.utcnow() + timedelta(minutes=30),
            used=True # Da dung
        )
        db.session.add(token_record)
        db.session.commit()

        # Thu mo link da dung
        res = self.client.get(f"/reset-password?token={raw_token}")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Liên kết này đã được sử dụng".encode("utf-8"), res.data)
        print("[PASSED 4/5] Chuyen huong va bao loi khi su dung lai link da dung.")

    def test_05_token_expired_after_30_minutes(self):
        """Yeu cau 1: Link qua 30 phut bi tu choi"""
        import secrets
        user = User.query.filter_by(email="beo810206@gmail.com").first()
        raw_token = secrets.token_urlsafe(32)
        hashed = hash_token(raw_token)
        
        # Tao token da het han cach day 5 phut
        token_record = PasswordResetToken(
            user_id=user.id,
            token_hash=hashed,
            expires_at=datetime.utcnow() - timedelta(minutes=5),
            used=False
        )
        db.session.add(token_record)
        db.session.commit()

        # Thu mo link het han
        res = self.client.get(f"/reset-password?token={raw_token}")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Liên kết đã hết hạn".encode("utf-8"), res.data)
        print("[PASSED 5/5] Tu choi link reset khi da qua 30 phut.")

if __name__ == "__main__":
    unittest.main()
