from datetime import date, timedelta
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = "scrum76-demo-secret"
DB_NAME = "schedule.db"

WEEKDAYS = {
    "0": "Thứ 2", "1": "Thứ 3", "2": "Thứ 4",
    "3": "Thứ 5", "4": "Thứ 6", "5": "Thứ 7", "6": "Chủ nhật"
}
SHIFTS = ["Ca sáng", "Ca chiều", "Ca tối"]


def connect_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS holidays (
                holiday_date TEXT PRIMARY KEY,
                description TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_name TEXT NOT NULL,
                start_date TEXT NOT NULL,
                shift TEXT NOT NULL,
                weekdays TEXT NOT NULL,
                total_sessions INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS class_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                schedule_id INTEGER NOT NULL,
                session_no INTEGER NOT NULL,
                session_date TEXT NOT NULL,
                weekday TEXT NOT NULL,
                shift TEXT NOT NULL,
                lesson_name TEXT NOT NULL,
                FOREIGN KEY(schedule_id) REFERENCES schedules(id)
            )
        """)


def get_holidays():
    with connect_db() as conn:
        rows = conn.execute(
            "SELECT holiday_date, description FROM holidays ORDER BY holiday_date"
        ).fetchall()
    return {row["holiday_date"]: row["description"] for row in rows}


def generate_dates(start_date, weekdays, total_sessions, holidays):
    """Tạo đúng số buổi vào các thứ đã chọn; bỏ qua ngày nghỉ đã khai báo."""
    result = []
    current = start_date
    # Giới hạn an toàn để tránh vòng lặp vô hạn khi dữ liệu không hợp lệ.
    for _ in range(3650):
        if len(result) >= total_sessions:
            break
        if str(current.weekday()) in weekdays and current.isoformat() not in holidays:
            result.append(current)
        current += timedelta(days=1)
    if len(result) != total_sessions:
        raise ValueError("Không thể tạo đủ số buổi trong phạm vi 10 năm.")
    return result


@app.route("/")
def index():
    with connect_db() as conn:
        schedules = conn.execute("""
            SELECT id, course_name, start_date, shift, total_sessions, created_at
            FROM schedules ORDER BY id DESC
        """).fetchall()
        holidays = conn.execute("""
            SELECT holiday_date, description FROM holidays ORDER BY holiday_date
        """).fetchall()
    return render_template(
        "index.html", schedules=schedules, holidays=holidays,
        weekdays=WEEKDAYS, shifts=SHIFTS
    )


@app.route("/holidays/add", methods=["POST"])
def add_holiday():
    holiday_date = request.form.get("holiday_date", "").strip()
    description = request.form.get("description", "").strip()
    try:
        date.fromisoformat(holiday_date)
        if not description:
            raise ValueError
    except ValueError:
        flash("Vui lòng nhập ngày nghỉ hợp lệ và mô tả ngày nghỉ.", "error")
        return redirect(url_for("index"))

    with connect_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO holidays (holiday_date, description) VALUES (?, ?)",
            (holiday_date, description)
        )
    flash("Đã lưu ngày nghỉ.", "success")
    return redirect(url_for("index"))


@app.route("/holidays/delete/<holiday_date>", methods=["POST"])
def delete_holiday(holiday_date):
    with connect_db() as conn:
        conn.execute("DELETE FROM holidays WHERE holiday_date = ?", (holiday_date,))
    flash("Đã xóa ngày nghỉ.", "success")
    return redirect(url_for("index"))


@app.route("/schedule/preview", methods=["POST"])
def preview_schedule():
    course_name = request.form.get("course_name", "").strip()
    start_date_text = request.form.get("start_date", "").strip()
    shift = request.form.get("shift", "").strip()
    weekdays = request.form.getlist("weekdays")
    total_text = request.form.get("total_sessions", "").strip()
    lesson_lines = [
        line.strip() for line in request.form.get("lessons", "").splitlines()
        if line.strip()
    ]

    try:
        if not course_name:
            raise ValueError("Vui lòng nhập tên môn học.")
        start_date = date.fromisoformat(start_date_text)
        if shift not in SHIFTS:
            raise ValueError("Vui lòng chọn ca học hợp lệ.")
        if not weekdays or any(day not in WEEKDAYS for day in weekdays):
            raise ValueError("Hãy chọn ít nhất một thứ trong tuần.")
        total_sessions = int(total_text)
        if total_sessions < 1 or total_sessions > 300:
            raise ValueError("Số buổi phải từ 1 đến 300.")
        if len(lesson_lines) != total_sessions:
            raise ValueError(
                f"Cần nhập đúng {total_sessions} bài học, mỗi bài trên một dòng. "
                f"Hiện bạn đã nhập {len(lesson_lines)} bài."
            )

        holidays = get_holidays()
        dates = generate_dates(start_date, set(weekdays), total_sessions, holidays)
        preview_rows = []
        for number, (session_date, lesson) in enumerate(zip(dates, lesson_lines), start=1):
            preview_rows.append({
                "number": number,
                "date": session_date.isoformat(),
                "weekday": WEEKDAYS[str(session_date.weekday())],
                "shift": shift,
                "lesson": lesson,
                "holiday_note": ""
            })

        return render_template(
            "preview.html",
            course_name=course_name,
            start_date=start_date_text,
            shift=shift,
            weekdays=weekdays,
            total_sessions=total_sessions,
            rows=preview_rows,
            lesson_lines=lesson_lines
        )
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("index"))


@app.route("/schedule/save", methods=["POST"])
def save_schedule():
    course_name = request.form.get("course_name", "").strip()
    start_date_text = request.form.get("start_date", "").strip()
    shift = request.form.get("shift", "").strip()
    weekdays = request.form.getlist("weekdays")
    try:
        total_sessions = int(request.form.get("total_sessions", "0"))
        lessons = [
            line.strip() for line in request.form.get("lessons", "").splitlines()
            if line.strip()
        ]
        start_date = date.fromisoformat(start_date_text)
        if not course_name or shift not in SHIFTS:
            raise ValueError("Dữ liệu lịch học không hợp lệ.")
        if not weekdays or any(day not in WEEKDAYS for day in weekdays):
            raise ValueError("Hãy chọn ít nhất một thứ trong tuần.")
        if not 1 <= total_sessions <= 300 or len(lessons) != total_sessions:
            raise ValueError("Số buổi và số bài học phải khớp nhau.")

        holidays = get_holidays()
        dates = generate_dates(start_date, set(weekdays), total_sessions, holidays)

        with connect_db() as conn:
            cursor = conn.execute("""
                INSERT INTO schedules
                (course_name, start_date, shift, weekdays, total_sessions)
                VALUES (?, ?, ?, ?, ?)
            """, (course_name, start_date_text, shift, ",".join(sorted(weekdays)), total_sessions))
            schedule_id = cursor.lastrowid
            for number, (session_date, lesson) in enumerate(zip(dates, lessons), start=1):
                conn.execute("""
                    INSERT INTO class_sessions
                    (schedule_id, session_no, session_date, weekday, shift, lesson_name)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    schedule_id, number, session_date.isoformat(),
                    WEEKDAYS[str(session_date.weekday())], shift, lesson
                ))
        flash("Đã lưu thời khóa biểu thành công.", "success")
        return redirect(url_for("schedule_detail", schedule_id=schedule_id))
    except (ValueError, TypeError) as exc:
        flash(str(exc) or "Dữ liệu không hợp lệ.", "error")
        return redirect(url_for("index"))


@app.route("/schedule/<int:schedule_id>")
def schedule_detail(schedule_id):
    with connect_db() as conn:
        schedule = conn.execute(
            "SELECT * FROM schedules WHERE id = ?", (schedule_id,)
        ).fetchone()
        sessions = conn.execute("""
            SELECT * FROM class_sessions
            WHERE schedule_id = ? ORDER BY session_no
        """, (schedule_id,)).fetchall()
    if schedule is None:
        flash("Không tìm thấy thời khóa biểu.", "error")
        return redirect(url_for("index"))
    return render_template("detail.html", schedule=schedule, sessions=sessions)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
