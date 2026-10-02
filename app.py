from flask import Flask, request, jsonify

from lesson import CourseLessonManager


app = Flask(__name__)

manager = CourseLessonManager()


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

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )