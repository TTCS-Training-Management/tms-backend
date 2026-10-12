from flask import Flask, request, jsonify, render_template  
from lesson import CourseLessonManager
from class_manager import ClassManager


app = Flask(__name__)

manager = CourseLessonManager()
class_manager = ClassManager()

# ==============================
# GIAO DIỆN FRONTEND
# ==============================
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

# ==============================
# TẠO DỮ LIỆU MẪU
# ==============================

manager.create_course(
    course_id=1,
    course_name="Lập trình Python",
    total_lessons=5
)

manager.create_course(
    course_id=2,
    course_name="Lập trình Web",
    total_lessons=5
)
# ==============================
# TẠO CHƯƠNG TRÌNH ĐÀO TẠO MẪU
# ==============================

class_manager.create_program(
    program_id="CT01",
    program_name="Chương trình Công nghệ thông tin",
    course_ids=[1, 2]
)
# ==============================
# LẤY DANH SÁCH CHƯƠNG TRÌNH
# ==============================

@app.route("/api/courses", methods=["GET"])
def get_courses():
    try:
        courses = manager.get_all_courses()

        return jsonify({
            "courses": courses
        }), 200

    except Exception as e:
        return jsonify({
            "message": str(e)
        }), 500

# ==============================
# TẠO MÔN HỌC
# ==============================

@app.route("/api/courses", methods=["POST"])
def create_course():
    try:
        data = request.get_json()

        course_id = data.get("id")
        course_name = data.get("name")
        total_lessons = data.get("total_lessons")

        if course_id is None:
            return jsonify({
                "message": "Thiếu id môn học."
            }), 400

        if not course_name:
            return jsonify({
                "message": "Tên môn học không được để trống."
            }), 400

        if total_lessons is None:
            return jsonify({
                "message": "Thiếu số buổi học."
            }), 400

        manager.create_course(
            course_id,
            course_name,
            int(total_lessons)
        )

        return jsonify({
            "message": "Tạo môn học thành công."
        }), 201

    except ValueError as e:
        return jsonify({
            "message": str(e)
        }), 400

    except Exception as e:
        return jsonify({
            "message": str(e)
        }), 500


# ==============================
# LẤY DANH SÁCH BUỔI HỌC
# ==============================

@app.route("/api/courses/<int:course_id>/lessons", methods=["GET"])
def get_lessons(course_id):

    try:
        lessons = manager.get_lessons(course_id)

        return jsonify({
            "course_id": course_id,
            "lessons": lessons
        }), 200

    except ValueError as e:
        return jsonify({
            "message": str(e)
        }), 404


# ==============================
# THÊM BUỔI HỌC
# ==============================

@app.route(
    "/api/courses/<int:course_id>/lessons",
    methods=["POST"]
)
def add_lesson(course_id):

    try:
        data = request.get_json()

        order = data.get("order")
        topic = data.get("topic")
        objective = data.get("objective")

        if order is None:
            return jsonify({
                "message": "Thiếu số thứ tự buổi học."
            }), 400

        if topic is None:
            return jsonify({
                "message": "Thiếu chủ đề."
            }), 400

        if objective is None:
            return jsonify({
                "message": "Thiếu mục tiêu."
            }), 400

        manager.add_lesson(
            course_id=course_id,
            order=int(order),
            topic=topic,
            objective=objective
        )

        return jsonify({
            "message": "Thêm buổi học thành công."
        }), 201

    except ValueError as e:
        return jsonify({
            "message": str(e)
        }), 400

    except Exception as e:
        return jsonify({
            "message": str(e)
        }), 500


# ==============================
# NHÂN BẢN DANH SÁCH BUỔI HỌC
# ==============================

@app.route(
    "/api/courses/<int:target_course_id>/lessons/clone",
    methods=["POST"]
)
def clone_lessons(target_course_id):

    try:
        data = request.get_json()

        source_course_id = data.get("source_course_id")

        if source_course_id is None:
            return jsonify({
                "message": "Thiếu source_course_id."
            }), 400

        manager.clone_lessons(
            source_course_id=int(source_course_id),
            target_course_id=target_course_id
        )

        return jsonify({
            "message": "Nhân bản danh sách buổi học thành công."
        }), 200

    except ValueError as e:
        return jsonify({
            "message": str(e)
        }), 400

    except Exception as e:
        return jsonify({
            "message": str(e)
        }), 500


# ==============================
# XEM THÔNG TIN MÔN + BUỔI HỌC
# ==============================

@app.route("/api/courses/<int:course_id>", methods=["GET"])
def get_course(course_id):

    try:
        course = manager.get_course(course_id)

        return jsonify(course), 200

    except ValueError as e:
        return jsonify({
            "message": str(e)
        }), 404


# ==============================
# CHẠY SERVER
# ==============================

# ==============================
# QUẢN LÝ CHƯƠNG TRÌNH ĐÀO TẠO
# ==============================

@app.route("/api/programs", methods=["GET"])
def get_programs():
    try:
        programs = class_manager.get_programs(manager)
        return jsonify({"programs": programs}), 200
    except ValueError as e:
        return jsonify({"message": str(e)}), 400
    except Exception as e:
        return jsonify({"message": str(e)}), 500


# ==============================
# MỞ LỚP HỌC MỚI
# ==============================

@app.route("/api/classes", methods=["POST"])
def create_class():
    try:
        data = request.get_json(silent=True) or {}

        required_fields = [
            "class_code",
            "program_id",
            "opening_date",
            "max_students",
            "learning_mode"
        ]

        for field in required_fields:
            if field not in data:
                return jsonify({
                    "message": f"Thiếu trường dữ liệu: {field}"
                }), 400

        new_class = class_manager.create_class(
            class_code=data["class_code"],
            program_id=data["program_id"],
            opening_date=data["opening_date"],
            max_students=data["max_students"],
            learning_mode=data["learning_mode"],
            course_manager=manager
        )

        return jsonify({
            "message": "Mở lớp học thành công.",
            "class": new_class
        }), 201

    except ValueError as e:
        return jsonify({"message": str(e)}), 400
    except Exception as e:
        return jsonify({"message": str(e)}), 500


# ==============================
# LẤY DANH SÁCH LỚP HỌC
# ==============================

@app.route("/api/classes", methods=["GET"])
def get_classes():
    return jsonify({
        "classes": class_manager.get_all_classes()
    }), 200


# ==============================
# XEM CHI TIẾT LỚP HỌC
# ==============================

@app.route("/api/classes/<class_code>", methods=["GET"])
def get_class_detail(class_code):
    try:
        class_data = class_manager.get_class(class_code)
        return jsonify(class_data), 200
    except ValueError as e:
        return jsonify({"message": str(e)}), 404


# ==============================
# CẬP NHẬT TRẠNG THÁI LỚP
# ==============================

@app.route(
    "/api/classes/<class_code>/status",
    methods=["PATCH"]
)
def update_class_status(class_code):
    try:
        data = request.get_json(silent=True) or {}
        new_status = data.get("status")

        if not new_status:
            return jsonify({
                "message": "Thiếu trạng thái mới."
            }), 400

        updated_class = class_manager.update_status(
            class_code,
            new_status
        )

        return jsonify({
            "message": "Cập nhật trạng thái thành công.",
            "class": updated_class
        }), 200

    except ValueError as e:
        return jsonify({"message": str(e)}), 400
    except Exception as e:
        return jsonify({"message": str(e)}), 500

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )