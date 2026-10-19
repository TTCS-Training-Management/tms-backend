from datetime import date
from typing import List, Dict

class AttendanceService:
    def __init__(self, max_absent_percentage: float = 20.0, warning_threshold: int = 1):
        """
        :param max_absent_percentage: Tỷ lệ vắng tối đa cho phép (%) trước khi bị cảnh cáo (VD: 20%)
        :param warning_threshold: Số buổi nghỉ còn lại tối thiểu để kích hoạt cảnh báo
        """
        self.max_absent_percentage = max_absent_percentage
        self.warning_threshold = warning_threshold

    def calculate_attendance_summary(
        self, total_sessions: int, attendance_history: List[Dict]
    ) -> Dict:
        """
        Tính toán lịch sử điểm danh, tỷ lệ chuyên cần và đưa ra cảnh báo.
        
        attendance_history format mẫu:
        [
            {"date": "2026-10-01", "status": "present"}, # present: Có mặt
            {"date": "2026-10-03", "status": "absent"},  # absent: Vắng
            {"date": "2026-10-05", "status": "late"}    # late: Đi muộn (có thể coi là có mặt)
        ]
        """
        attended_count = 0
        absent_count = 0

        for record in attendance_history:
            if record["status"] in ["present", "late"]:
                attended_count += 1
            elif record["status"] == "absent":
                absent_count += 1

        # Tính tỷ lệ chuyên cần (%)
        total_completed = len(attendance_history)
        attendance_rate = (attended_count / total_completed * 100) if total_completed > 0 else 100.0

        # Số buổi vắng tối đa cho phép toàn khóa
        max_allowed_absences = int(total_sessions * (self.max_absent_percentage / 100))
        
        # Số buổi được phép nghỉ còn lại
        remaining_allowed_absences = max(0, max_allowed_absences - absent_count)

        # Cảnh báo nếu số buổi còn lại <= ngưỡng cảnh báo
        is_warning = remaining_allowed_absences <= self.warning_threshold and absent_count > 0

        return {
            "total_sessions": total_sessions,
            "completed_sessions": total_completed,
            "attended_count": attended_count,
            "absent_count": absent_count,
            "attendance_rate": round(attendance_rate, 2),
            "max_allowed_absences": max_allowed_absences,
            "remaining_allowed_absences": remaining_allowed_absences,
            "is_warning": is_warning,
            "warning_message": (
                f"CẢNH BÁO: Bạn đã vắng {absent_count}/{max_allowed_absences} buổi cho phép. "
                f"Bạn chỉ còn được nghỉ tối đa {remaining_allowed_absences} buổi nữa!"
                if is_warning else "Tỷ lệ chuyên cần của bạn đang ở mức an toàn."
            ),
            "history": attendance_history
        }


# --- Chạy thử nghiệm ---
if __name__ == "__main__":
    service = AttendanceService(max_absent_percentage=20.0, warning_threshold=1)
    
    # Giả định khóa học có 15 buổi
    total_course_sessions = 15
    
    # Lịch sử điểm danh giả lập của học viên
    mock_history = [
        {"date": "2026-10-01", "status": "present"},
        {"date": "2026-10-03", "status": "present"},
        {"date": "2026-10-05", "status": "absent"},
        {"date": "2026-10-08", "status": "present"},
        {"date": "2026-10-10", "status": "absent"},
    ]

    result = service.calculate_attendance_summary(total_course_sessions, mock_history)
    
    print("--- KẾT QUẢ ĐIỂM DANH HỌC VIÊN ---")
    print(f"Tổng số buổi học: {result['total_sessions']}")
    print(f"Số buổi đã học: {result['completed_sessions']}")
    print(f"Số buổi có mặt: {result['attended_count']}")
    print(f"Số buổi vắng: {result['absent_count']}")
    print(f"Tỷ lệ chuyên cần: {result['attendance_rate']}%")
    print(f"Số buổi vắng cho phép còn lại: {result['remaining_allowed_absences']}")
    print(f"Trạng thái cảnh báo: {result['is_warning']}")
    print(f"Thông báo: {result['warning_message']}")