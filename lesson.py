from dataclasses import dataclass, asdict
from typing import List


@dataclass
class Lesson:
    order: int
    topic: str
    objective: str


class CourseLessonManager:
    def __init__(self):
        self.courses = {}

    def create_course(self, course_id: int, course_name: str, total_lessons: int):
        """
        Tạo một môn học.
        """
        if course_id in self.courses:
            raise ValueError("Môn học đã tồn tại.")

        if total_lessons <= 0:
            raise ValueError("Số buổi học phải lớn hơn 0.")

        self.courses[course_id] = {
            "id": course_id,
            "name": course_name,
            "total_lessons": total_lessons,
            "lessons": []
        }

    def add_lesson(
        self,
        course_id: int,
        order: int,
        topic: str,
        objective: str
    ):
        """
        Thêm một buổi học vào môn.
        """

        if course_id not in self.courses:
            raise ValueError("Không tìm thấy môn học.")

        course = self.courses[course_id]

        # Kiểm tra số buổi tối đa
        if len(course["lessons"]) >= course["total_lessons"]:
            raise ValueError(
                "Không thể thêm buổi học. "
                "Số buổi đã đạt giới hạn của môn."
            )

        # Kiểm tra số thứ tự
        if order < 1 or order > course["total_lessons"]:
            raise ValueError(
                f"Số thứ tự phải nằm trong khoảng "
                f"1 đến {course['total_lessons']}."
            )

        # Không cho trùng số thứ tự
        for lesson in course["lessons"]:
            if lesson.order == order:
                raise ValueError(
                    f"Buổi học số {order} đã tồn tại."
                )

        if not topic.strip():
            raise ValueError("Chủ đề không được để trống.")

        if not objective.strip():
            raise ValueError("Mục tiêu không được để trống.")

        lesson = Lesson(
            order=order,
            topic=topic,
            objective=objective
        )

        course["lessons"].append(lesson)

        # Sắp xếp theo số thứ tự
        course["lessons"].sort(key=lambda x: x.order)

    def get_lessons(self, course_id: int):
        """
        Lấy danh sách buổi học của một môn.
        """

        if course_id not in self.courses:
            raise ValueError("Không tìm thấy môn học.")

        course = self.courses[course_id]

        return [asdict(lesson) for lesson in course["lessons"]]

    def clone_lessons(
        self,
        source_course_id: int,
        target_course_id: int
    ):
        """
        Nhân bản danh sách buổi học từ môn nguồn
        sang môn đích.
        """

        if source_course_id not in self.courses:
            raise ValueError("Không tìm thấy môn học nguồn.")

        if target_course_id not in self.courses:
            raise ValueError("Không tìm thấy môn học đích.")

        source_course = self.courses[source_course_id]
        target_course = self.courses[target_course_id]

        source_lessons = source_course["lessons"]

        # Kiểm tra số lượng buổi
        if len(source_lessons) > target_course["total_lessons"]:
            raise ValueError(
                "Không thể nhân bản. "
                "Số buổi của môn nguồn lớn hơn "
                "số buổi cho phép của môn đích."
            )

        # Xóa danh sách hiện tại của môn đích
        target_course["lessons"] = []

        # Sao chép từng buổi
        for lesson in source_lessons:
            new_lesson = Lesson(
                order=lesson.order,
                topic=lesson.topic,
                objective=lesson.objective
            )

            target_course["lessons"].append(new_lesson)

    def get_course(self, course_id: int):
        """
        Lấy thông tin môn học.
        """

        if course_id not in self.courses:
            raise ValueError("Không tìm thấy môn học.")

        course = self.courses[course_id]

        return {
            "id": course["id"],
            "name": course["name"],
            "total_lessons": course["total_lessons"],
            "lesson_count": len(course["lessons"]),
            "lessons": [
                asdict(lesson)
                for lesson in course["lessons"]
            ]
        }