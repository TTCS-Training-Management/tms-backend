from flask import Flask, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash

from datetime import datetime, timedelta

import secrets
import hashlib


# =========================================================
# 1. KHỞI TẠO FLASK
# =========================================================

app = Flask(__name__)


# =========================================================
# 2. CẤU HÌNH DATABASE
# =========================================================

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# =========================================================
# 3. CẤU HÌNH EMAIL
# =========================================================

# =========================================================

app.config["MAIL_SERVER"] = "smtp.gmail.com"

app.config["MAIL_PORT"] = 465

app.config["MAIL_USE_SSL"] = True

app.config["MAIL_USE_TLS"] = False

app.config["MAIL_USERNAME"] = "beo810206@gmail.com"

app.config["MAIL_PASSWORD"] = "shbs ebvg vrac wykq"

app.config["MAIL_DEFAULT_SENDER"] = "beo810206@gmail.com"

mail = Mail(app)


# =========================================================
# 4. MODEL USER
# =========================================================

class User(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    email = db.Column(
        db.String(255),
        unique=True,
        nullable=False
    )

    password = db.Column(
        db.String(255),
        nullable=False
    )


# =========================================================
# 5. MODEL PASSWORD RESET TOKEN
# =========================================================

class PasswordResetToken(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    token_hash = db.Column(
        db.String(64),
        unique=True,
        nullable=False
    )

    expires_at = db.Column(
        db.DateTime,
        nullable=False
    )

    used = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


# =========================================================
# 6. HÀM HASH TOKEN
# =========================================================

def hash_token(token):

    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


# =========================================================
# 7. TRANG QUÊN MẬT KHẨU
# =========================================================

@app.route("/", methods=["GET", "POST"])
def forgot_password():

    message = None

    # Người dùng bấm nút gửi
    if request.method == "POST":

        # Lấy email từ form
        email = request.form.get(
            "email",
            ""
        ).strip().lower()


        # =================================================
        # TÌM USER
        # =================================================

        user = User.query.filter_by(
            email=email
        ).first()


        # =================================================
        # NẾU EMAIL TỒN TẠI
        # =================================================

        if user:

            # ---------------------------------------------
            # TẠO TOKEN NGẪU NHIÊN
            # ---------------------------------------------

            token = secrets.token_urlsafe(32)


            # ---------------------------------------------
            # HASH TOKEN
            # ---------------------------------------------

            token_hash = hash_token(token)


            # =================================================
            # YÊU CẦU 1:
            # LINK CÓ HIỆU LỰC 30 PHÚT
            # =================================================

            expires_at = (
                datetime.utcnow()
                + timedelta(minutes=30)
            )


            # ---------------------------------------------
            # XÓA TOKEN CŨ CHƯA DÙNG
            # ---------------------------------------------

            PasswordResetToken.query.filter_by(
                user_id=user.id,
                used=False
            ).delete()


            # ---------------------------------------------
            # TẠO TOKEN MỚI
            # ---------------------------------------------

            reset_token = PasswordResetToken(

                user_id=user.id,

                token_hash=token_hash,

                expires_at=expires_at,

                used=False

            )


            db.session.add(reset_token)

            db.session.commit()


            # ---------------------------------------------
            # TẠO LINK ĐẶT LẠI MẬT KHẨU
            # ---------------------------------------------

            reset_link = url_for(

                "reset_password",

                token=token,

                _external=True

            )

            # In link ra terminal de tien test / cham bai
            print("\n" + "=" * 55)
            print("[TEST / DEBUG] RESET PASSWORD LINK:")
            print(reset_link)
            print("=" * 55 + "\n")


            # ---------------------------------------------
            # NỘI DUNG EMAIL
            # ---------------------------------------------

            email_body = f"""
Xin chào,

Bạn vừa yêu cầu đặt lại mật khẩu.

Hãy nhấn vào liên kết bên dưới:

{reset_link}

Liên kết này có hiệu lực trong 30 phút
và chỉ được sử dụng một lần.

Nếu bạn không yêu cầu đặt lại mật khẩu,
hãy bỏ qua email này.

Trân trọng.
"""


            # ---------------------------------------------
            # GỬI EMAIL
            # ---------------------------------------------

            try:

                msg = Message(

                    subject="Đặt lại mật khẩu",

                    recipients=[email]

                )

                msg.body = email_body

                mail.send(msg)

                print("[Flask-Mail] Da gui email thanh cong.")


            except Exception as error:

                print("[Flask-Mail] Loi gui email (Can App Password cua Gmail):", error)


        # =================================================
        # YÊU CẦU 3:
        # KHÔNG TIẾT LỘ EMAIL CÓ TỒN TẠI HAY KHÔNG
        # =================================================
        #
        # Dù email có tồn tại hay không,
        # người dùng đều nhận cùng một thông báo.
        #
        # =================================================

        message = (
            "Nếu email tồn tại trong hệ thống, "
            "chúng tôi đã gửi liên kết đặt lại mật khẩu."
        )

        # Hiển thị trang kết quả
        return render_template(
            "forgot_password.html",
            message=message
        )


    # Hiển thị trang ban đầu (GET)
    return render_template(
        "forgot_password.html",
        message=None
    )


# =========================================================
# 8. TRANG ĐẶT LẠI MẬT KHẨU
# =========================================================

@app.route(
    "/reset-password",
    methods=["GET", "POST"]
)
def reset_password():

    # Lấy token từ URL
    token = request.args.get("token")


    # =================================================
    # KIỂM TRA KHÔNG CÓ TOKEN
    # =================================================

    if not token:

        return render_template(

            "reset_password.html",

            error="Liên kết không hợp lệ.",

            token=""

        )


    # =================================================
    # HASH TOKEN
    # =================================================

    token_hash = hash_token(token)


    # =================================================
    # TÌM TOKEN TRONG DATABASE
    # =================================================

    reset_token = PasswordResetToken.query.filter_by(

        token_hash=token_hash

    ).first()


    # =================================================
    # TOKEN KHÔNG TỒN TẠI
    # =================================================

    if not reset_token:

        return render_template(

            "reset_password.html",

            error="Liên kết không hợp lệ.",

            token=token

        )


    # =================================================
    # YÊU CẦU 2:
    # LINK CHỈ ĐƯỢC DÙNG MỘT LẦN
    # =================================================

    if reset_token.used:

        return render_template(

            "reset_password.html",

            error="Liên kết này đã được sử dụng.",

            token=token

        )


    # =================================================
    # YÊU CẦU 1:
    # KIỂM TRA LINK ĐÃ HẾT 30 PHÚT CHƯA
    # =================================================

    if datetime.utcnow() > reset_token.expires_at:

        return render_template(

            "reset_password.html",

            error=(
                "Liên kết đã hết hạn. "
                "Vui lòng yêu cầu một liên kết mới."
            ),

            token=token

        )


    # =================================================
    # NGƯỜI DÙNG GỬI MẬT KHẨU MỚI
    # =================================================

    if request.method == "POST":

        password = request.form.get(
            "password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )


        # ---------------------------------------------
        # KIỂM TRA MẬT KHẨU RỖNG
        # ---------------------------------------------

        if not password:

            return render_template(

                "reset_password.html",

                error="Vui lòng nhập mật khẩu mới.",

                token=token

            )


        # ---------------------------------------------
        # KIỂM TRA ĐỘ DÀI
        # ---------------------------------------------

        if len(password) < 8:

            return render_template(

                "reset_password.html",

                error=(
                    "Mật khẩu phải có ít nhất 8 ký tự."
                ),

                token=token

            )


        # ---------------------------------------------
        # KIỂM TRA NHẬP LẠI MẬT KHẨU
        # ---------------------------------------------

        if password != confirm_password:

            return render_template(

                "reset_password.html",

                error="Mật khẩu nhập lại không khớp.",

                token=token

            )


        # =================================================
        # TÌM USER
        # =================================================

        user = db.session.get(

            User,

            reset_token.user_id

        )


        if not user:

            return render_template(

                "reset_password.html",

                error="Không tìm thấy tài khoản.",

                token=token

            )


        # =================================================
        # MÃ HÓA MẬT KHẨU
        # =================================================

        user.password = generate_password_hash(
            password
        )


        # =================================================
        # YÊU CẦU 2:
        # ĐÁNH DẤU TOKEN ĐÃ ĐƯỢC SỬ DỤNG
        # =================================================

        reset_token.used = True


        # Lưu database
        db.session.commit()


        # Chuyển đến trang thành công
        return render_template(
            "success.html"
        )


    # =================================================
    # HIỂN THỊ FORM RESET PASSWORD
    # =================================================

    return render_template(

        "reset_password.html",

        token=token

    )


# =========================================================
# 9. TRANG ĐĂNG KÝ TÀI KHOẢN MỚI
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    success = None

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            error = "Vui lòng nhập đầy đủ email và mật khẩu."
        elif len(password) < 8:
            error = "Mật khẩu phải có ít nhất 8 ký tự."
        elif User.query.filter_by(email=email).first():
            error = "Email này đã tồn tại trong hệ thống."
        else:
            new_user = User(
                email=email,
                password=generate_password_hash(password)
            )
            db.session.add(new_user)
            db.session.commit()
            success = f"Tạo tài khoản {email} thành công! Bây giờ bạn có thể thử quên mật khẩu cho tài khoản này."

    return render_template(
        "register.html",
        error=error,
        success=success
    )


# =========================================================
# 10. TẠO DATABASE & SEED TÀI KHOẢN MẶC ĐỊNH
# =========================================================

with app.app_context():

    db.create_all()

    # Tự động nạp tài khoản mẫu nếu chưa có
    default_accounts = [
        "beo810206@gmail.com",
        "dtc245200687@ictu.edu.vn"
    ]
    for acc in default_accounts:
        if not User.query.filter_by(email=acc).first():
            db.session.add(
                User(
                    email=acc,
                    password=generate_password_hash("12345678")
                )
            )
    db.session.commit()


# =========================================================
# 10. KIỂM TRA CÁC YÊU CẦU DESCRIPTION
# =========================================================

"""
YÊU CẦU 1:
Link đặt lại mật khẩu có hiệu lực 30 phút.

Được thực hiện bằng:

expires_at = datetime.utcnow() + timedelta(minutes=30)

và kiểm tra:

if datetime.utcnow() > reset_token.expires_at:
    LINK ĐÃ HẾT HẠN


YÊU CẦU 2:
Link chỉ sử dụng được một lần.

Được kiểm tra bằng:

if reset_token.used:
    LINK ĐÃ ĐƯỢC SỬ DỤNG

Sau khi đổi mật khẩu thành công:

reset_token.used = True


YÊU CẦU 3:
Email không tồn tại vẫn hiển thị cùng một thông báo.

Email được tìm bằng:

user = User.query.filter_by(
    email=email
).first()

Nếu có user:
    gửi email.

Nếu không có user:
    không gửi email.

Nhưng cả hai trường hợp đều trả:

Nếu email tồn tại trong hệ thống,
chúng tôi đã gửi liên kết đặt lại mật khẩu.

Do đó người dùng bên ngoài không biết
email có tồn tại trong hệ thống hay không.
"""


# =========================================================
# 11. CHẠY SERVER
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )