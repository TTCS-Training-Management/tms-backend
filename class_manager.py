
from copy import deepcopy
from datetime import date


class ClassManager:
    """Quản lý chương trình đào tạo và lớp học."""

    def __init__(self):
        self.programs = {}
        self.classes = {}

    def create_program(self, program_id, program_name, course_ids):
        """Tạo chương trình từ danh sách ID môn học."""

        program_id = str(program_id).strip()
        program_name = str(program_name).strip()

        if not program_id:
            raise ValueError("Mã chương trình không được để trống.")

        if not program_name:
            raise ValueError("Tên chương trình không được để trống.")

        if program_id in self.programs:
            raise ValueError("Mã chương trình đã tồn tại.")

        if not course_ids:
            raise ValueError("Chương trình phải có ít nhất một môn học.")

        self.programs[program_id] = {
            "id": program_id,
            "name": program_name,
            "course_ids": list(course_ids)
        }

    def get_programs(self, course_manager):
        """Lấy chương trình kèm danh sách môn học."""

        result = []

        for program in self.programs.values():
            courses = []

            for course_id in program["course_ids"]:
                course = course_manager.get_course(course_id)
                courses.append({
                    "id": course["id"],
                    "name": course["name"]
                })

            result.append({
                "id": program["id"],
                "name": program["name"],
                "courses": courses
            })

        return result

    def create_class(
        self,
        class_code,
        program_id,
        opening_date,
        max_students,
        learning_mode,
        course_manager
    ):
        """Mở lớp và sao chép danh sách môn từ chương trình."""

        class_code = str(class_code).strip().upper()
        program_id = str(program_id).strip()
        learning_mode = str(learning_mode).strip()

        if not class_code:
            raise ValueError("Mã lớp không được để trống.")

        if class_code in self.classes:
            raise ValueError("Mã lớp đã tồn tại.")

        if program_id not in self.programs:
            raise ValueError("Không tìm thấy chương trình đào tạo.")

        if not opening_date:
            raise ValueError("Ngày khai giảng dự kiến không được để trống.")

        try:
            date.fromisoformat(opening_date)
        except (TypeError, ValueError):
            raise ValueError("Ngày khai giảng không hợp lệ.")

        try:
            max_students = int(max_students)
        except (TypeError, ValueError):
            raise ValueError("Sĩ số tối đa phải là số nguyên.")

        if max_students <= 0:
            raise ValueError("Sĩ số tối đa phải lớn hơn 0.")

        valid_modes = {
            "Trực tiếp",
            "Trực tuyến",
            "Kết hợp",
        }

        learning_mode = str(learning_mode).strip()
        matched_mode = next(
            (mode for mode in valid_modes if mode.casefold() == learning_mode.casefold()),
            None,
        )

        if matched_mode is None:
            raise ValueError(
                f"Hình thức học không hợp lệ: {learning_mode!r}. "
                f"Các giá trị hợp lệ: {', '.join(sorted(valid_modes))}"
            )

        learning_mode = matched_mode

        program = self.programs[program_id]
        copied_courses = []

        for course_id in program["course_ids"]:
            course = course_manager.get_course(course_id)

            # Sao chép dữ liệu môn học tại thời điểm mở lớp.
            copied_courses.append(deepcopy({
                "id": course["id"],
                "name": course["name"],
                "total_lessons": course["total_lessons"],
                "lessons": course["lessons"]
            }))

        self.classes[class_code] = {
            "class_code": class_code,
            "program_id": program_id,
            "program_name": program["name"],
            "opening_date": opening_date,
            "max_students": max_students,
            "learning_mode": learning_mode,
            "status": "Chuẩn bị",
            "courses": copied_courses
        }

        return self.get_class(class_code)

    def get_class(self, class_code):
        """Lấy thông tin một lớp."""

        class_code = str(class_code).strip().upper()

        if class_code not in self.classes:
            raise ValueError("Không tìm thấy lớp học.")

        return deepcopy(self.classes[class_code])

    def get_all_classes(self):
        """Lấy danh sách lớp học."""

        return [
            deepcopy(item)
            for item in self.classes.values()
        ]

    def update_status(self, class_code, new_status):
        """Cập nhật trạng thái theo đúng vòng đời lớp."""

        class_code = str(class_code).strip().upper()

        if class_code not in self.classes:
            raise ValueError("Không tìm thấy lớp học.")

        allowed_transitions = {
            "Chuẩn bị": {"Đang học", "Huỷ"},
            "Đang học": {"Kết thúc", "Huỷ"},
            "Kết thúc": set(),
            "Huỷ": set()
        }

        current_status = self.classes[class_code]["status"]

        if new_status not in allowed_transitions:
            raise ValueError("Trạng thái lớp không hợp lệ.")

        if new_status not in allowed_transitions[current_status]:
            raise ValueError(
                f"Không thể chuyển từ {current_status} sang {new_status}."
            )

        self.classes[class_code]["status"] = new_status

        return self.get_class(class_code)
