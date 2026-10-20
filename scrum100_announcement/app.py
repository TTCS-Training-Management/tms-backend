
from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from pathlib import Path
from datetime import datetime

app = Flask(__name__)
app.secret_key = "scrum100-local-demo-key"

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "database.db"


# =========================
# KET NOI CO SO DU LIEU
# =========================
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# =========================
# KHOI TAO CO SO DU LIEU
# =========================
def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS enrollments (
            class_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            PRIMARY KEY (class_id, student_id),
            FOREIGN KEY (class_id) REFERENCES classes(id),
            FOREIGN KEY (student_id) REFERENCES students(id)
        );

        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS announcement_classes (
            announcement_id INTEGER NOT NULL,
            class_id INTEGER NOT NULL,
            PRIMARY KEY (announcement_id, class_id),
            FOREIGN KEY (announcement_id)
                REFERENCES announcements(id) ON DELETE CASCADE,
            FOREIGN KEY (class_id) REFERENCES classes(id)
        );

        CREATE TABLE IF NOT EXISTS recipients (
            announcement_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            read_at TEXT,
            email_status TEXT NOT NULL DEFAULT 'pending',
            PRIMARY KEY (announcement_id, student_id),
            FOREIGN KEY (announcement_id)
                REFERENCES announcements(id) ON DELETE CASCADE,
            FOREIGN KEY (student_id) REFERENCES students(id)
        );
        """)

        # Them lop mau neu chua co du lieu
        if db.execute(
            "SELECT COUNT(*) FROM classes"
        ).fetchone()[0] == 0:
            db.executemany(
                "INSERT INTO classes(name) VALUES (?)",
                [("CNTT01",), ("CNTT02",), ("KTPM01",)]
            )

        # Them hoc vien mau neu chua co du lieu
        if db.execute(
            "SELECT COUNT(*) FROM students"
        ).fetchone()[0] == 0:
            db.executemany(
                "INSERT INTO students(name, email) VALUES (?, ?)",
                [
                    ("Nguyễn Văn An", "an@example.com"),
                    ("Trần Thị Bình", "binh@example.com"),
                    ("Lê Văn Cường", "cuong@example.com"),
                    ("Phạm Thị Dung", "dung@example.com"),
                    ("Hoàng Văn Em", "em@example.com"),
                ]
            )

        # Gan hoc vien vao lop neu chua co du lieu
        if db.execute(
            "SELECT COUNT(*) FROM enrollments"
        ).fetchone()[0] == 0:
            db.executemany(
                "INSERT INTO enrollments(class_id, student_id) VALUES (?, ?)",
                [
                    (1, 1), (1, 2), (1, 3),
                    (2, 3), (2, 4), (3, 5)
                ]
            )


# =========================
# TRANG CHU
# =========================
@app.route("/")
def index():
    with get_db() as db:
        announcements = db.execute("""
            SELECT
                a.*,
                COUNT(r.student_id) AS total_students,
                COALESCE(
                    SUM(
                        CASE
                            WHEN r.read_at IS NOT NULL THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS read_count
            FROM announcements a
            LEFT JOIN recipients r
                ON r.announcement_id = a.id
            GROUP BY a.id
            ORDER BY a.id DESC
        """).fetchall()

    return render_template(
        "index.html",
        announcements=announcements
    )


# =========================
# TAO THONG BAO
# =========================
@app.route("/create", methods=["GET", "POST"])
def create():
    with get_db() as db:
        classes = db.execute(
            "SELECT * FROM classes ORDER BY name"
        ).fetchall()

        if request.method == "POST":
            title = request.form.get("title", "").strip()
            content = request.form.get("content", "").strip()
            class_ids = list(
                dict.fromkeys(request.form.getlist("class_ids"))
            )

            # Kiem tra du lieu nhap vao
            if not title or not content or not class_ids:
                flash(
                    "Vui lòng nhập tiêu đề, nội dung "
                    "và chọn ít nhất một lớp."
                )
                return render_template(
                    "create.html",
                    classes=classes
                )

            # Kiem tra ma lop
            try:
                selected_ids = [
                    int(value) for value in class_ids
                ]
            except ValueError:
                flash("Danh sách lớp không hợp lệ.")
                return render_template(
                    "create.html",
                    classes=classes
                )

            placeholders = ",".join(
                "?" for _ in selected_ids
            )

            valid_classes = db.execute(
                f"""
                SELECT id
                FROM classes
                WHERE id IN ({placeholders})
                """,
                selected_ids
            ).fetchall()

            if len(valid_classes) != len(set(selected_ids)):
                flash("Có lớp không hợp lệ.")
                return render_template(
                    "create.html",
                    classes=classes
                )

            # Tao thong bao
            cursor = db.execute("""
                INSERT INTO announcements(
                    title,
                    content,
                    created_at
                )
                VALUES (?, ?, ?)
            """, (
                title,
                content,
                datetime.now().strftime("%d/%m/%Y %H:%M")
            ))

            announcement_id = cursor.lastrowid

            # Luu cac lop nhan thong bao
            db.executemany(
                """
                INSERT INTO announcement_classes(
                    announcement_id,
                    class_id
                )
                VALUES (?, ?)
                """,
                [
                    (announcement_id, cid)
                    for cid in selected_ids
                ]
            )

            # Lay danh sach hoc vien thuoc cac lop da chon
            students = db.execute(f"""
                SELECT DISTINCT student_id
                FROM enrollments
                WHERE class_id IN ({placeholders})
            """, selected_ids).fetchall()

            # Mo phong xu ly email, khong gui email that
            db.executemany("""
                INSERT INTO recipients(
                    announcement_id,
                    student_id,
                    email_status
                )
                VALUES (?, ?, 'simulated')
            """, [
                (announcement_id, row["student_id"])
                for row in students
            ])

            flash(
                f"Đã tạo thông báo thành công! "
                f"Đã mô phỏng email cho {len(students)} học viên. "
                f"Không có email thật nào được gửi."
            )

            return redirect(
                url_for(
                    "detail",
                    announcement_id=announcement_id
                )
            )

    return render_template(
        "create.html",
        classes=classes
    )


# =========================
# CHI TIET THONG BAO
# =========================
@app.route("/announcement/<int:announcement_id>")
def detail(announcement_id):
    with get_db() as db:
        announcement = db.execute(
            "SELECT * FROM announcements WHERE id = ?",
            (announcement_id,)
        ).fetchone()

        if announcement is None:
            return "Không tìm thấy thông báo", 404

        recipients = db.execute("""
            SELECT
                s.id,
                s.name,
                s.email,
                r.read_at,
                r.email_status
            FROM recipients r
            JOIN students s
                ON s.id = r.student_id
            WHERE r.announcement_id = ?
            ORDER BY s.name
        """, (announcement_id,)).fetchall()

        classes = db.execute("""
            SELECT c.name
            FROM announcement_classes ac
            JOIN classes c
                ON c.id = ac.class_id
            WHERE ac.announcement_id = ?
            ORDER BY c.name
        """, (announcement_id,)).fetchall()

    total_students = len(recipients)
    read_count = sum(
        1 for recipient in recipients
        if recipient["read_at"]
    )

    simulated_count = sum(
        1 for recipient in recipients
        if recipient["email_status"] == "simulated"
    )

    return render_template(
        "detail.html",
        announcement=announcement,
        recipients=recipients,
        classes=classes,
        read_count=read_count,
        total_students=total_students,
        simulated_count=simulated_count
    )


# =========================
# TRANG THONG BAO HOC VIEN
# =========================
@app.route("/student/<int:student_id>")
def student_view(student_id):
    with get_db() as db:
        student = db.execute(
            "SELECT * FROM students WHERE id = ?",
            (student_id,)
        ).fetchone()

        if student is None:
            return "Không tìm thấy học viên", 404

        announcements = db.execute("""
            SELECT
                a.id,
                a.title,
                a.content,
                a.created_at,
                r.read_at
            FROM recipients r
            JOIN announcements a
                ON a.id = r.announcement_id
            WHERE r.student_id = ?
            ORDER BY a.id DESC
        """, (student_id,)).fetchall()

    return render_template(
        "student.html",
        student=student,
        announcements=announcements
    )


# =========================
# DANH DAU DA DOC
# =========================
@app.route(
    "/announcement/<int:announcement_id>/read/<int:student_id>",
    methods=["POST"]
)
def mark_read(announcement_id, student_id):
    with get_db() as db:
        recipient = db.execute("""
            SELECT 1
            FROM recipients
            WHERE announcement_id = ?
              AND student_id = ?
        """, (
            announcement_id,
            student_id
        )).fetchone()

        if recipient is None:
            return "Không tìm thấy người nhận thông báo", 404

        db.execute("""
            UPDATE recipients
            SET read_at = COALESCE(read_at, ?)
            WHERE announcement_id = ?
              AND student_id = ?
        """, (
            datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            announcement_id,
            student_id
        ))

    flash("Đã cập nhật trạng thái đọc.")

    return redirect(
        url_for("student_view", student_id=student_id)
    )


# =========================
# CHAY UNG DUNG
# =========================
if __name__ == "__main__":
    init_db()
    app.run(debug=True)
