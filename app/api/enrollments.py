from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.enrollment import EnrollmentCreate
# Lưu ý: Điều chỉnh lại tên Model Class và ClassEnrollment cho khớp với code thực tế của nhóm trong thư mục app/models/
# from app.models.class_model import ClassModel, ClassEnrollment

router = APIRouter(prefix="/api/classes", tags=["Class Enrollments"])

@router.post("/{class_id}/enroll", status_code=status.HTTP_201_CREATED)
def enroll_students(
    class_id: int,
    payload: EnrollmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 1. Kiểm tra lớp học có tồn tại không
    # db_class = db.query(ClassModel).filter(ClassModel.id == class_id).first()
    # if not db_class:
    #     raise HTTPException(status_code=404, detail="Không tìm thấy lớp học")

    # 2. Kiểm tra sĩ số lớp với sức chứa tối đa
    # current_count = db.query(ClassEnrollment).filter(ClassEnrollment.class_id == class_id).count()
    # if current_count + len(payload.student_ids) > db_class.max_capacity:
    #     raise HTTPException(
    #         status_code=400,
    #         detail=f"Lớp đã đủ sĩ số hoặc vượt quá sức chứa tối đa ({db_class.max_capacity})"
    #     )

    successful_enrollments = []

    for student_id in payload.student_ids:
        # 3. Kiểm tra học viên đã có trong lớp chưa
        # existing = db.query(ClassEnrollment).filter_by(class_id=class_id, student_id=student_id).first()
        # if existing:
        #     continue  # Hoặc báo lỗi nếu muốn chặn toàn bộ

        # 4. Tạo bản ghi ghi danh mới
        # new_enrollment = ClassEnrollment(
        #     class_id=class_id,
        #     student_id=student_id,
        #     enrolled_by=current_user.id
        # )
        # db.add(new_enrollment)
        successful_enrollments.append(student_id)

    # db.commit()

    return {
        "message": "Ghi danh học viên thành công",
        "class_id": class_id,
        "enrolled_student_ids": successful_enrollments,
        "enrolled_by": current_user.id
    }