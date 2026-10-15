"""Sprint 3 and 4 student, class, schedule, and attendance APIs."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
import re
import secrets
from typing import Any

from fastapi import Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint,
    and_, case, func, or_, select,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Mapped, mapped_column

import main as m

ABSENCE_EVIDENCE_DIR = m.BACKEND_DIR / "private_uploads" / "absence_evidence"
ABSENCE_EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
ABSENCE_EVIDENCE_MAX_BYTES = 10 * 1024 * 1024
ABSENCE_EVIDENCE_SUFFIXES = {".pdf", ".jpg", ".jpeg", ".png"}


class StudentProfile(m.Base):
    __tablename__ = "student_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), unique=True, index=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="RESTRICT"), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120), index=True)
    phone: Mapped[str] = mapped_column(String(40), index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    entry_level: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    status_effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ClassDetails(m.Base):
    __tablename__ = "training_class_details"

    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("training_classes.id", ondelete="CASCADE"), unique=True, index=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    start_date: Mapped[date] = mapped_column(Date, index=True)
    capacity: Mapped[int] = mapped_column(Integer)
    format: Mapped[str] = mapped_column(String(20))


class ClassSubject(m.Base):
    __tablename__ = "class_subjects"
    __table_args__ = (UniqueConstraint("class_id", "subject_id", name="uq_class_subject"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("training_classes.id", ondelete="CASCADE"), index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("training_subjects.id", ondelete="RESTRICT"), index=True)
    sequence_order: Mapped[int] = mapped_column(Integer)
    instructor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)


class ClassSubjectTA(m.Base):
    __tablename__ = "class_subject_tas"
    __table_args__ = (UniqueConstraint("class_subject_id", "user_id", name="uq_class_subject_ta"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    class_subject_id: Mapped[int] = mapped_column(ForeignKey("class_subjects.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)


class StudentEnrollment(m.Base):
    __tablename__ = "student_enrollments"
    __table_args__ = (UniqueConstraint("student_id", "class_id", name="uq_student_class_enrollment"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id", ondelete="RESTRICT"), index=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("training_classes.id", ondelete="RESTRICT"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    enrolled_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    effective_from: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class StudentStatusHistory(m.Base):
    __tablename__ = "student_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id", ondelete="RESTRICT"), index=True)
    action: Mapped[str] = mapped_column(String(20))
    effective_date: Mapped[date] = mapped_column(Date, index=True)
    reason: Mapped[str] = mapped_column(String(1000))
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    target_class_id: Mapped[int | None] = mapped_column(ForeignKey("training_classes.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class TrainingRoom(m.Base):
    __tablename__ = "training_rooms"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    room_type: Mapped[str] = mapped_column(String(20))
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    location: Mapped[str | None] = mapped_column(String(300), nullable=True)
    online_link: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class TrainingHoliday(m.Base):
    __tablename__ = "training_holidays"

    id: Mapped[int] = mapped_column(primary_key=True)
    holiday_date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))


class TrainingLesson(m.Base):
    __tablename__ = "training_lessons"
    __table_args__ = (UniqueConstraint("class_id", "starts_at", name="uq_class_lesson_start"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("training_classes.id", ondelete="CASCADE"), index=True)
    class_subject_id: Mapped[int | None] = mapped_column(ForeignKey("class_subjects.id", ondelete="SET NULL"), nullable=True, index=True)
    subject_session_id: Mapped[int | None] = mapped_column(ForeignKey("subject_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    room_id: Mapped[int | None] = mapped_column(ForeignKey("training_rooms.id", ondelete="SET NULL"), nullable=True, index=True)
    instructor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    starts_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    status: Mapped[str] = mapped_column(String(20), default="scheduled", index=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class LessonAudit(m.Base):
    __tablename__ = "training_lesson_audits"

    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("training_lessons.id", ondelete="RESTRICT"), index=True)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    action: Mapped[str] = mapped_column(String(30))
    detail: Mapped[str] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class Attendance(m.Base):
    __tablename__ = "lesson_attendance"
    __table_args__ = (UniqueConstraint("lesson_id", "student_id", name="uq_lesson_student_attendance"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("training_lessons.id", ondelete="RESTRICT"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id", ondelete="RESTRICT"), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    marked_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class AttendanceAudit(m.Base):
    __tablename__ = "attendance_audits"

    id: Mapped[int] = mapped_column(primary_key=True)
    attendance_id: Mapped[int] = mapped_column(ForeignKey("lesson_attendance.id", ondelete="RESTRICT"), index=True)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    old_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    new_status: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class AbsenceRequest(m.Base):
    __tablename__ = "absence_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("training_lessons.id", ondelete="RESTRICT"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id", ondelete="RESTRICT"), index=True)
    reason: Mapped[str] = mapped_column(String(2000))
    evidence_ref: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    decision_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class InAppNotice(m.Base):
    __tablename__ = "in_app_notices"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ScheduleRequest(BaseModel):
    weekday: int | None = Field(default=None, ge=0, le=6)
    weekdays: list[int] | None = Field(default=None, max_length=7)
    recurrence: str = Field(default="weekly", pattern="^(weekly|biweekly)$")
    session_time: time
    start_date: date
    count: int = Field(ge=1, le=120)
    room_id: int | None = None
    instructor_id: int | None = None
    session_duration_minutes: int = Field(default=90, ge=15, le=600)
    skip_holidays: bool = True
    holidays: list[date] = Field(default_factory=list, max_length=366)
    subject_session_ids: list[int] | None = Field(default=None, max_length=120)
    override_conflicts: bool = False


def _roles(db: m.Session, user: m.User) -> list[str]:
    return m.assigned_roles(db, user)


def _allowed(db: m.Session, user: m.User, module: str, action: str) -> bool:
    return m.permission_allows(_roles(db, user), module, action)


def _need(db: m.Session, user: m.User, module: str, action: str) -> None:
    if not _allowed(db, user, module, action):
        raise HTTPException(403, "Bạn không có quyền truy cập chức năng này")


def _require_roles(db: m.Session, user: m.User, *roles: str) -> None:
    if not set(roles).intersection(_roles(db, user)):
        raise HTTPException(403, "Bạn không có quyền thực hiện thao tác này")


def _parse_date(value: Any, field_name: str) -> date:
    try:
        return value if isinstance(value, date) and not isinstance(value, datetime) else date.fromisoformat(str(value))
    except (TypeError, ValueError) as error:
        raise HTTPException(422, f"{field_name} phải ở định dạng YYYY-MM-DD") from error


def _parse_datetime(value: Any, field_name: str) -> datetime:
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as error:
        raise HTTPException(422, f"{field_name} không hợp lệ") from error
    return parsed.replace(tzinfo=None)


def _student_json(
    student: StudentProfile,
    db: m.Session,
    enrollments: list[tuple[StudentEnrollment, m.TrainingClass, ClassDetails | None]] | None = None,
    status_history: list[StudentStatusHistory] | None = None,
) -> dict[str, Any]:
    if enrollments is None:
        enrollments = db.execute(
            select(StudentEnrollment, m.TrainingClass, ClassDetails)
            .join(m.TrainingClass, m.TrainingClass.id == StudentEnrollment.class_id)
            .outerjoin(ClassDetails, ClassDetails.class_id == m.TrainingClass.id)
            .where(StudentEnrollment.student_id == student.id)
            .order_by(StudentEnrollment.enrolled_at.desc())
            .limit(100)
        ).all()
    if status_history is None:
        status_history = db.scalars(
            select(StudentStatusHistory)
            .where(StudentStatusHistory.student_id == student.id)
            .order_by(StudentStatusHistory.created_at.desc())
            .limit(100)
        ).all()
    return {
        "id": student.id,
        "student_code": student.student_code,
        "user_id": student.user_id,
        "lead_id": student.lead_id,
        "full_name": student.full_name,
        "phone": student.phone,
        "email": student.email,
        "date_of_birth": student.date_of_birth.isoformat() if student.date_of_birth else None,
        "address": student.address,
        "entry_level": student.entry_level,
        "notes": student.notes,
        "status": student.status,
        "status_effective_date": student.status_effective_date.isoformat() if student.status_effective_date else None,
        "status_history": [
            {
                "id": item.id,
                "action": item.action,
                "effective_date": item.effective_date.isoformat(),
                "reason": item.reason,
                "actor_user_id": item.actor_user_id,
                "target_class_id": item.target_class_id,
                "created_at": item.created_at.isoformat(),
            }
            for item in status_history
        ],
        "class_history": [
            {
                "class_id": training_class.id,
                "class_code": details.code if details else None,
                "class_name": training_class.name,
                "status": enrollment.status,
                "enrolled_at": enrollment.enrolled_at.isoformat(),
                "effective_from": enrollment.effective_from.isoformat(),
                "effective_to": enrollment.effective_to.isoformat() if enrollment.effective_to else None,
            }
            for enrollment, training_class, details in enrollments
        ],
    }


def _class_summaries(db: m.Session, classes: list[m.TrainingClass]) -> list[dict[str, Any]]:
    if not classes:
        return []
    class_ids = [item.id for item in classes]
    details_by_class = {
        item.class_id: item
        for item in db.scalars(select(ClassDetails).where(ClassDetails.class_id.in_(class_ids))).all()
    }
    programs = {
        item.id: item
        for item in db.scalars(select(m.TrainingProgram).where(
            m.TrainingProgram.id.in_({row.program_id for row in classes})
        )).all()
    }
    enrollment_counts = dict(db.execute(
        select(StudentEnrollment.class_id, func.count(StudentEnrollment.id))
        .where(
            StudentEnrollment.class_id.in_(class_ids),
            StudentEnrollment.status == "active",
            StudentEnrollment.effective_to.is_(None),
        )
        .group_by(StudentEnrollment.class_id)
    ).all())
    now = datetime.now()
    lesson_counts = {
        class_id: (int(total or 0), int(completed or 0))
        for class_id, total, completed in db.execute(
            select(
                TrainingLesson.class_id,
                func.count(TrainingLesson.id),
                func.sum(case((or_(TrainingLesson.status == "completed", and_(TrainingLesson.status == "scheduled", TrainingLesson.ends_at <= now)), 1), else_=0)),
            )
            .where(TrainingLesson.class_id.in_(class_ids), TrainingLesson.status.in_(["scheduled", "completed"]))
            .group_by(TrainingLesson.class_id)
        ).all()
    }
    instructors_by_class: dict[int, set[int]] = {class_id: set() for class_id in class_ids}
    for class_id, instructor_id in db.execute(
        select(ClassSubject.class_id, ClassSubject.instructor_id)
        .where(ClassSubject.class_id.in_(class_ids), ClassSubject.instructor_id.is_not(None))
    ).all():
        instructors_by_class[class_id].add(instructor_id)
    results = []
    for training_class in classes:
        details = details_by_class.get(training_class.id)
        enrollment_count = int(enrollment_counts.get(training_class.id, 0))
        total_lessons, completed_lessons = lesson_counts.get(training_class.id, (0, 0))
        program = programs.get(training_class.program_id)
        if training_class.status == "completed":
            curriculum_progress = 100
        elif total_lessons > 0:
            curriculum_progress = min(100, round((completed_lessons / total_lessons) * 100))
        else:
            curriculum_progress = 0
        results.append({
            "id": training_class.id, "program_id": training_class.program_id,
            "program_name": program.name if program else None,
            "code": details.code if details else None, "name": training_class.name,
            "start_date": details.start_date.isoformat() if details else None,
            "capacity": details.capacity if details else None, "format": details.format if details else None,
            "status": training_class.status, "enrollment_count": enrollment_count,
            "scheduled_lessons": total_lessons, "completed_lessons": completed_lessons,
            "curriculum_progress": curriculum_progress,
            "instructor_ids": sorted(instructors_by_class[training_class.id]),
            "capacity_warning": bool(details and enrollment_count > details.capacity),
        })
    return results


def _class_subjects(db: m.Session, class_id: int) -> list[ClassSubject]:
    return db.scalars(select(ClassSubject).where(ClassSubject.class_id == class_id).order_by(ClassSubject.sequence_order)).all()


def _student_roster(db: m.Session, class_id: int, on_date: date) -> list[StudentProfile]:
    return db.scalars(
        select(StudentProfile)
        .join(StudentEnrollment, StudentEnrollment.student_id == StudentProfile.id)
        .where(
            StudentEnrollment.class_id == class_id,
            StudentEnrollment.effective_from <= on_date,
            or_(StudentEnrollment.effective_to.is_(None), StudentEnrollment.effective_to > on_date),
        )
        .order_by(StudentProfile.student_code)
    ).all()


def _class_instructor_ids(db: m.Session, class_id: int) -> set[int]:
    subject_ids = {row.id for row in _class_subjects(db, class_id)}
    ids = set(db.scalars(select(ClassSubject.instructor_id).where(
        ClassSubject.id.in_(subject_ids), ClassSubject.instructor_id.is_not(None)
    )).all()) if subject_ids else set()
    if subject_ids:
        ids.update(db.scalars(select(ClassSubjectTA.user_id).where(ClassSubjectTA.class_subject_id.in_(subject_ids))).all())
    return ids


def _can_manage_class(db: m.Session, user: m.User, class_id: int) -> bool:
    if _allowed(db, user, "classes", "full"):
        return True
    assigned = db.scalar(
        select(ClassSubject.id)
        .outerjoin(ClassSubjectTA, ClassSubjectTA.class_subject_id == ClassSubject.id)
        .where(
            ClassSubject.class_id == class_id,
            or_(ClassSubject.instructor_id == user.id, ClassSubjectTA.user_id == user.id),
        )
        .limit(1)
    )
    return assigned is not None


def _lesson_json(db: m.Session, lesson: TrainingLesson) -> dict[str, Any]:
    training_class = db.get(m.TrainingClass, lesson.class_id)
    details = db.scalar(select(ClassDetails).where(ClassDetails.class_id == lesson.class_id))
    room = db.get(TrainingRoom, lesson.room_id) if lesson.room_id else None
    subject_session = db.get(m.SubjectSession, lesson.subject_session_id) if lesson.subject_session_id else None
    subject_link = db.get(ClassSubject, lesson.class_subject_id) if lesson.class_subject_id else None
    subject = db.get(m.TrainingSubject, subject_link.subject_id) if subject_link else None
    instructor = db.get(m.User, lesson.instructor_id) if lesson.instructor_id else None
    return {
        "id": lesson.id,
        "class_id": lesson.class_id,
        "class_code": details.code if details else None,
        "class_name": training_class.name if training_class else None,
        "class_subject_id": lesson.class_subject_id,
        "subject_id": subject.id if subject else None,
        "subject_name": subject.name if subject else None,
        "subject_session_id": lesson.subject_session_id,
        "subject_session_title": subject_session.title if subject_session else None,
        "room_id": lesson.room_id,
        "room_name": room.name if room else None,
        "instructor_id": lesson.instructor_id,
        "instructor_name": instructor.full_name if instructor else None,
        "title": lesson.title,
        "starts_at": lesson.starts_at.isoformat(),
        "ends_at": lesson.ends_at.isoformat(),
        "status": lesson.status,
        "cancellation_reason": lesson.cancellation_reason,
    }


def _notice(db: m.Session, user_id: int, title: str, body: str) -> None:
    db.add(InAppNotice(user_id=user_id, title=title[:200], body=body[:2000]))


def _notify_lesson_people(db: m.Session, lesson: TrainingLesson, message: str) -> None:
    recipients = _class_instructor_ids(db, lesson.class_id)
    recipients.update(student.user_id for student in _student_roster(db, lesson.class_id, lesson.starts_at.date()))
    for user_id in recipients:
        _notice(db, user_id, "Cập nhật lịch học", message)


def _conflicts(
    db: m.Session, starts_at: datetime, ends_at: datetime, room_id: int | None,
    instructor_id: int | None, exclude_lesson_id: int | None = None,
    class_id: int | None = None,
) -> list[dict[str, Any]]:
    conditions = [
        TrainingLesson.status == "scheduled",
        TrainingLesson.starts_at < ends_at,
        TrainingLesson.ends_at > starts_at,
    ]
    if exclude_lesson_id is not None:
        conditions.append(TrainingLesson.id != exclude_lesson_id)
    if room_id is None and instructor_id is None and class_id is None:
        return []
    statement = select(TrainingLesson).where(and_(*conditions), or_(
        TrainingLesson.room_id == room_id if room_id is not None else False,
        TrainingLesson.instructor_id == instructor_id if instructor_id is not None else False,
        TrainingLesson.class_id == class_id if class_id is not None else False,
    ))
    rows = db.scalars(statement.order_by(TrainingLesson.starts_at).limit(100)).all()
    conflicts = []
    for row in rows:
        conflicts.append({
            "session_id": row.id,
            "class_id": row.class_id,
            "starts_at": row.starts_at.isoformat(),
            "ends_at": row.ends_at.isoformat(),
            "room_conflict": room_id is not None and row.room_id == room_id,
            "instructor_conflict": instructor_id is not None and row.instructor_id == instructor_id,
            "class_conflict": class_id is not None and row.class_id == class_id,
        })
    return conflicts


def _schedule_drafts(db: m.Session, class_id: int, request: ScheduleRequest) -> list[dict[str, Any]]:
    if request.start_date < date.today():
        raise HTTPException(422, "Ngày bắt đầu lịch học không được ở quá khứ")
    weekdays = request.weekdays if request.weekdays is not None else (
        [request.weekday] if request.weekday is not None else []
    )
    if not weekdays or any(day < 0 or day > 6 for day in weekdays) or len(set(weekdays)) != len(weekdays):
        raise HTTPException(422, "Chọn ít nhất một thứ trong tuần hợp lệ, không lặp")
    room = db.get(TrainingRoom, request.room_id) if request.room_id else None
    if request.room_id and (room is None or not room.is_active):
        raise HTTPException(422, "Phòng học không tồn tại hoặc đã ngừng hoạt động")
    enrollment_count = db.scalar(select(func.count(StudentEnrollment.id)).where(
        StudentEnrollment.class_id == class_id,
        StudentEnrollment.status == "active",
        StudentEnrollment.effective_to.is_(None),
    )) or 0
    if room and room.room_type == "physical" and room.capacity is not None and enrollment_count > room.capacity:
        raise HTTPException(409, f"Sức chứa phòng ({room.capacity}) nhỏ hơn sĩ số hiện tại ({enrollment_count})")
    holiday_dates = set(request.holidays)
    if request.skip_holidays:
        holiday_dates.update(db.scalars(select(TrainingHoliday.holiday_date)).all())
    class_subjects = _class_subjects(db, class_id)
    templates: list[tuple[ClassSubject | None, m.SubjectSession | None]] = []
    if request.subject_session_ids is not None:
        if len(request.subject_session_ids) != request.count:
            raise HTTPException(422, "Số subject_session_ids phải bằng số buổi yêu cầu")
        for template_id in request.subject_session_ids:
            template = db.get(m.SubjectSession, template_id)
            if template is None:
                raise HTTPException(422, f"Không tìm thấy subject session {template_id}")
            class_subject = next(
                (item for item in class_subjects if item.subject_id == template.subject_id), None
            )
            if class_subject is None:
                raise HTTPException(422, "Mẫu buổi học không thuộc môn của lớp")
            templates.append((class_subject, template))
    else:
        for class_subject in class_subjects:
            for template in db.scalars(select(m.SubjectSession).where(
                m.SubjectSession.subject_id == class_subject.subject_id
            ).order_by(m.SubjectSession.sequence)).all():
                templates.append((class_subject, template))
        if not templates:
            templates = [(class_subjects[0] if class_subjects else None, None)] * request.count
        if request.count > len(templates):
            raise HTTPException(422, "Số buổi vượt quá số mẫu buổi học của chương trình")
        templates = templates[:request.count]

    drafts: list[dict[str, Any]] = []
    current = request.start_date
    first_monday = request.start_date - timedelta(days=request.start_date.weekday())
    skipped = 0
    while len(drafts) < request.count:
        week_index = (current - first_monday).days // 7
        occurs_this_week = request.recurrence == "weekly" or week_index % 2 == 0
        if occurs_this_week and current.weekday() in weekdays:
            if request.skip_holidays and current in holiday_dates:
                skipped += 1
                if skipped > 366:
                    raise HTTPException(422, "Không tìm được đủ ngày học sau khi bỏ qua ngày nghỉ")
            else:
                start = datetime.combine(current, request.session_time)
                end = start + timedelta(minutes=request.session_duration_minutes)
                class_subject, template = templates[len(drafts)]
                instructor_id = request.instructor_id or (class_subject.instructor_id if class_subject else None)
                if instructor_id is not None:
                    instructor = db.get(m.User, instructor_id)
                    if instructor is None or not instructor.is_active or "instructor" not in _roles(db, instructor):
                        raise HTTPException(422, "Buổi học cần giảng viên đang hoạt động có vai trò instructor")
                conflicts = _conflicts(db, start, end, request.room_id, instructor_id, class_id=class_id)
                drafts.append({
                    "starts_at": start,
                    "ends_at": end,
                    "class_subject_id": class_subject.id if class_subject else None,
                    "subject_session_id": template.id if template else None,
                    "title": template.title if template else f"Buổi {len(drafts) + 1}",
                    "instructor_id": instructor_id,
                    "room_id": request.room_id,
                    "conflicts": conflicts,
                })
        current += timedelta(days=1)
        if (current - request.start_date).days > 366 * 4:
            raise HTTPException(422, "Không tìm được đủ buổi học trong giới hạn 4 năm")
    return drafts


def _attendance_permission(db: m.Session, user: m.User, lesson: TrainingLesson) -> None:
    if not _allowed(db, user, "attendance", "write"):
        raise HTTPException(403, "Bạn không có quyền cập nhật điểm danh")
    if not _allowed(db, user, "attendance", "full") and not _can_manage_class(db, user, lesson.class_id):
        raise HTTPException(403, "Bạn chưa được phân công vào lớp này")
    if not _allowed(db, user, "attendance", "full") and lesson.starts_at.date() != date.today():
        raise HTTPException(403, "Giảng viên chỉ được cập nhật điểm danh trong ngày học")


def _upsert_attendance(db: m.Session, lesson: TrainingLesson, student: StudentProfile, user: m.User, status_value: str, note: str | None = None) -> Attendance:
    row = db.scalar(select(Attendance).where(
        Attendance.lesson_id == lesson.id, Attendance.student_id == student.id
    ))
    old_status = row.status if row else None
    if row is None:
        row = Attendance(lesson_id=lesson.id, student_id=student.id, status=status_value, marked_by=user.id, note=note)
        db.add(row)
        db.flush()
    else:
        row.status = status_value
        row.marked_by = user.id
        if note is not None:
            row.note = note
    db.add(AttendanceAudit(
        attendance_id=row.id,
        actor_user_id=user.id,
        old_status=old_status,
        new_status=status_value,
        reason=note,
    ))
    return row


@m.app.get("/leads/summary")
def lead_summary(user: m.Annotated[m.User, Depends(m.require_permission("leads", "read"))], db: m.DbSession, q: str | None = None) -> dict[str, Any]:
    statement = select(m.Lead.status, func.count(m.Lead.id)).group_by(m.Lead.status)
    if q and q.strip():
        term = f"%{q.strip()}%"
        statement = statement.where(or_(
            m.Lead.full_name.ilike(term), m.Lead.phone.ilike(term), m.Lead.email.ilike(term),
        ))
    if not _allowed(db, user, "leads", "full"):
        statement = statement.where(m.Lead.assigned_to_user_id == user.id)
    counts = {key: count for key, count in db.execute(statement).all()}
    stages = ("new", "contacted", "consulting", "trial", "won", "rejected", "converted")
    return {"counts": {stage: int(counts.get(stage, 0)) for stage in stages}, "total": sum(counts.get(stage, 0) for stage in stages)}


@m.app.get("/leads/follow-ups/overdue")
def overdue_lead_followups(
    user: m.Annotated[m.User, Depends(m.require_permission("leads", "read"))],
    db: m.DbSession,
    as_of: datetime | None = None,
    q: str | None = None,
) -> list[dict[str, Any]]:
    due = (as_of or datetime.now(timezone.utc)).replace(tzinfo=None)
    statement = select(m.Lead, m.LeadInteraction).join(
        m.LeadInteraction, m.LeadInteraction.lead_id == m.Lead.id
    ).where(
        m.Lead.status != "converted",
        m.LeadInteraction.follow_up_at.is_not(None),
        m.LeadInteraction.follow_up_at <= due,
    )
    if q and q.strip():
        term = f"%{q.strip()}%"
        statement = statement.where(or_(
            m.Lead.full_name.ilike(term), m.Lead.phone.ilike(term), m.Lead.email.ilike(term),
        ))
    if not _allowed(db, user, "leads", "full"):
        statement = statement.where(m.Lead.assigned_to_user_id == user.id)
    return [
        {"lead_id": lead.id, "full_name": lead.full_name, "interaction_id": interaction.id,
         "interaction_type": interaction.interaction_type, "content": interaction.note,
         "follow_up_at": interaction.follow_up_at.isoformat()}
        for lead, interaction in db.execute(statement.order_by(m.LeadInteraction.follow_up_at).limit(100)).all()
    ]


@m.app.post("/leads/{lead_id}/convert")
def convert_lead(lead_id: int, user: m.Annotated[m.User, Depends(m.require_permission("leads", "write"))], db: m.DbSession, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    lead = db.get(m.Lead, lead_id)
    if lead is None:
        raise HTTPException(404, "Không tìm thấy lead")
    m.ensure_lead_access(db, user, lead)
    if lead.converted_at is not None:
        existing = db.scalar(select(StudentProfile).where(StudentProfile.lead_id == lead.id))
        if existing is None:
            raise HTTPException(500, "Lead đã đánh dấu chuyển đổi nhưng không có hồ sơ học viên")
        if lead.status != "converted":
            lead.status = "converted"
            db.commit()
        return {"student": _student_json(existing, db), "message": "Lead đã được chuyển đổi"}
    if lead.status != "won":
        raise HTTPException(409, "Chỉ có thể chuyển đổi lead ở trạng thái won")
    if not lead.email:
        raise HTTPException(422, "Lead cần có email để tạo tài khoản học viên")
    email = m.validate_email(lead.email)
    existing_user = db.scalar(select(m.User).where(m.User.email == email))
    if existing_user:
        existing_profile = db.scalar(select(StudentProfile).where(
            (StudentProfile.user_id == existing_user.id) | (StudentProfile.email == email)
        ))
        if existing_profile:
            if existing_profile.lead_id is None:
                existing_profile.lead_id = lead.id
            lead.status = "converted"
            lead.converted_at = datetime.now(timezone.utc).replace(tzinfo=None)
            m.record_lead_interaction(db, lead, user, "converted", f"Đã đồng bộ với học viên {existing_profile.student_code}")
            db.commit()
            db.refresh(existing_profile)
            return {"student": _student_json(existing_profile, db), "message": f"Đã chuyển đổi và liên kết với học viên {existing_profile.student_code}"}
        elif existing_user.role == "student" or "student" in _roles(db, existing_user):
            code = f"STU-{date.today():%Y%m%d}-{secrets.token_hex(3).upper()}"
            profile = StudentProfile(
                student_code=code, user_id=existing_user.id, lead_id=lead.id,
                full_name=lead.full_name, phone=lead.phone, email=email,
                address=(payload or {}).get("address"),
                entry_level=(payload or {}).get("entry_level"),
                notes=lead.notes,
            )
            db.add(profile)
            lead.status = "converted"
            lead.converted_at = datetime.now(timezone.utc).replace(tzinfo=None)
            m.record_lead_interaction(db, lead, user, "converted", f"Chuyển thành học viên {code}")
            db.commit()
            db.refresh(profile)
            return {"student": _student_json(profile, db), "message": f"Đã tạo hồ sơ học viên {code} cho tài khoản hiện có"}
        else:
            raise HTTPException(409, "Email đã được sử dụng bởi một tài khoản khác")
    temporary_password = f"{secrets.token_urlsafe(10)}A1!"
    try:
        delivered = m.send_email(m.activation_email(email, lead.full_name, temporary_password))
    except (OSError, m.smtplib.SMTPException):
        delivered = False
    if not delivered:
        raise HTTPException(503, "Không gửi được email kích hoạt; chưa tạo tài khoản học viên")
    student_user = m.User(
        full_name=lead.full_name, email=email, phone=lead.phone,
        password_hash=m.hash_password(temporary_password), role="student",
        must_change_password=True,
    )
    db.add(student_user)
    db.flush()
    db.add(m.UserRoleAssignment(user_id=student_user.id, role="student"))
    code = f"STU-{date.today():%Y%m%d}-{secrets.token_hex(3).upper()}"
    profile = StudentProfile(
        student_code=code, user_id=student_user.id, lead_id=lead.id,
        full_name=lead.full_name, phone=lead.phone, email=email,
        address=(payload or {}).get("address"),
        entry_level=(payload or {}).get("entry_level"),
        notes=lead.notes,
    )
    db.add(profile)
    lead.status = "converted"
    lead.converted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    m.record_lead_interaction(db, lead, user, "converted", f"Chuyển thành học viên {code}")
    db.commit()
    db.refresh(profile)
    return {"student": _student_json(profile, db), "message": "Đã tạo hồ sơ và gửi email kích hoạt"}


@m.app.get("/students")
def list_students(
    user: m.Annotated[m.User, Depends(m.require_permission("student_records", "read"))],
    db: m.DbSession,
    q: str | None = None,
    class_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    statement = select(StudentProfile)
    if class_id:
        statement = statement.join(StudentEnrollment, StudentEnrollment.student_id == StudentProfile.id).where(StudentEnrollment.class_id == class_id, StudentEnrollment.status == "active")
    if q and q.strip():
        term = f"%{q.strip()}%"
        statement = statement.where(or_(
            StudentProfile.student_code.ilike(term), StudentProfile.full_name.ilike(term),
            StudentProfile.phone.ilike(term),
        ))
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    students = db.scalars(statement.order_by(StudentProfile.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    if students:
        history_by_student: dict[int, list[tuple[StudentEnrollment, m.TrainingClass, ClassDetails | None]]] = {
            student.id: [] for student in students
        }
        status_history_by_student: dict[int, list[StudentStatusHistory]] = {
            student.id: [] for student in students
        }
        for enrollment, training_class, details in db.execute(
            select(StudentEnrollment, m.TrainingClass, ClassDetails)
            .join(m.TrainingClass, m.TrainingClass.id == StudentEnrollment.class_id)
            .outerjoin(ClassDetails, ClassDetails.class_id == m.TrainingClass.id)
            .where(StudentEnrollment.student_id.in_(history_by_student))
            .order_by(StudentEnrollment.enrolled_at.desc())
        ).all():
            if len(history_by_student[enrollment.student_id]) < 100:
                history_by_student[enrollment.student_id].append((enrollment, training_class, details))
        for entry in db.scalars(
            select(StudentStatusHistory)
            .where(StudentStatusHistory.student_id.in_(status_history_by_student))
            .order_by(StudentStatusHistory.created_at.desc())
        ).all():
            if len(status_history_by_student[entry.student_id]) < 100:
                status_history_by_student[entry.student_id].append(entry)
        items = [
            _student_json(item, db, history_by_student[item.id], status_history_by_student[item.id])
            for item in students
        ]
    else:
        items = []
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@m.app.get("/students/me")
def student_own_profile(user: m.CurrentUser, db: m.DbSession) -> dict[str, Any]:
    student = db.scalar(select(StudentProfile).where(StudentProfile.user_id == user.id))
    if student is None and getattr(user, "email", None):
        student = db.scalar(select(StudentProfile).where(func.lower(StudentProfile.email) == user.email.lower()))
        if student is not None:
            student.user_id = user.id
            try:
                db.commit()
            except Exception:
                db.rollback()
    if student is None:
        raise HTTPException(404, "Tài khoản chưa được liên kết với hồ sơ học viên")
    return _student_json(student, db)


@m.app.get("/students/me/schedule")
def student_own_schedule(user: m.CurrentUser, db: m.DbSession, start: date, end: date) -> list[dict[str, Any]]:
    student = db.scalar(select(StudentProfile).where(StudentProfile.user_id == user.id))
    if student is None and getattr(user, "email", None):
        student = db.scalar(select(StudentProfile).where(func.lower(StudentProfile.email) == user.email.lower()))
        if student is not None:
            student.user_id = user.id
            try:
                db.commit()
            except Exception:
                db.rollback()
    if student is None:
        raise HTTPException(404, "Không tìm thấy hồ sơ học viên")
    if start > end or (end - start).days > 93:
        raise HTTPException(422, "Khoảng lịch phải hợp lệ và không quá 94 ngày")
    allowed_class_ids = select(StudentEnrollment.class_id).where(
        StudentEnrollment.student_id == student.id,
        StudentEnrollment.effective_from <= end,
        or_(StudentEnrollment.effective_to.is_(None), StudentEnrollment.effective_to > start),
    )
    rows = db.scalars(select(TrainingLesson).where(
        TrainingLesson.class_id.in_(allowed_class_ids),
        TrainingLesson.starts_at >= datetime.combine(start, time.min),
        TrainingLesson.starts_at < datetime.combine(end + timedelta(days=1), time.min),
    ).order_by(TrainingLesson.starts_at).limit(1000)).all()
    return [_lesson_json(db, item) for item in rows]


@m.app.get("/students/{student_id}")
def get_student(student_id: int, user: m.CurrentUser, db: m.DbSession) -> dict[str, Any]:
    student = db.get(StudentProfile, student_id)
    if student is None:
        raise HTTPException(404, "Không tìm thấy học viên")
    if student.user_id != user.id:
        _need(db, user, "student_records", "read")
    return _student_json(student, db)


@m.app.patch("/students/{student_id}")
def update_student(student_id: int, user: m.CurrentUser, db: m.DbSession, payload: dict[str, Any]) -> dict[str, Any]:
    student = db.get(StudentProfile, student_id)
    if student is None:
        raise HTTPException(404, "Không tìm thấy học viên")
    manager = _allowed(db, user, "student_records", "full")
    if student.user_id != user.id and not manager:
        raise HTTPException(403, "Bạn không có quyền cập nhật hồ sơ này")
    allowed = {"full_name", "phone", "date_of_birth", "address", "entry_level", "notes"}
    if not payload or set(payload) - allowed or (not manager and set(payload) - {"full_name", "phone", "date_of_birth", "address"}):
        raise HTTPException(422, "Các trường cập nhật học viên không hợp lệ")
    for field, value in payload.items():
        if field == "date_of_birth":
            value = _parse_date(value, field) if value else None
        elif value is not None:
            value = str(value).strip()
            max_length = 120 if field in {"full_name", "entry_level"} else 500 if field == "address" else 4000 if field == "notes" else 40
            if len(value) > max_length or (field == "full_name" and not value):
                raise HTTPException(422, f"Giá trị {field} không hợp lệ")
            if field == "phone" and not m.re.fullmatch(r"^(\+84|84|0)[0-9]{9,10}$", value.replace(" ", "")):
                raise HTTPException(422, "Số điện thoại không hợp lệ")
        elif field in {"full_name", "phone"}:
            raise HTTPException(422, f"Giá trị {field} là bắt buộc")
        setattr(student, field, value)
    if "full_name" in payload:
        account = db.get(m.User, student.user_id)
        if account:
            account.full_name = student.full_name
    if "phone" in payload:
        account = db.get(m.User, student.user_id)
        if account:
            account.phone = student.phone
    db.commit()
    return _student_json(student, db)


@m.app.post("/students/{student_id}/status")
def change_student_status(student_id: int, user: m.Annotated[m.User, Depends(m.require_permission("student_records", "full"))], db: m.DbSession, payload: dict[str, Any]) -> dict[str, Any]:
    student = db.get(StudentProfile, student_id)
    if student is None:
        raise HTTPException(404, "Không tìm thấy học viên")
    action = str(payload.get("action", ""))
    if action not in {"defer", "transfer", "withdraw"}:
        raise HTTPException(422, "action phải là defer, transfer hoặc withdraw")
    reason = str(payload.get("reason", "")).strip()
    if not reason or len(reason) > 1000:
        raise HTTPException(422, "Lý do là bắt buộc và tối đa 1000 ký tự")
    effective_date = _parse_date(payload.get("effective_date"), "effective_date")
    target_class_id = payload.get("target_class_id")
    target_class = None
    if action == "transfer":
        try:
            target_class_id = int(target_class_id)
        except (TypeError, ValueError) as error:
            raise HTTPException(422, "Chuyển lớp cần target_class_id hợp lệ") from error
        target_class = db.get(m.TrainingClass, target_class_id)
        if target_class is None or target_class.status in {"completed", "cancelled"}:
            raise HTTPException(422, "Lớp nhận chuyển không tồn tại hoặc đã kết thúc")
        details = db.scalar(select(ClassDetails).where(ClassDetails.class_id == target_class_id))
        occupied = db.scalar(select(func.count(StudentEnrollment.id)).where(
            StudentEnrollment.class_id == target_class_id, StudentEnrollment.status == "active",
            StudentEnrollment.effective_to.is_(None),
        )) or 0
        if details and occupied >= details.capacity:
            raise HTTPException(409, "Lớp nhận chuyển đã đủ sĩ số")
        if db.scalar(select(StudentEnrollment.id).where(
            StudentEnrollment.student_id == student.id,
            StudentEnrollment.class_id == target_class_id,
        )):
            raise HTTPException(409, "Học viên đã có lịch sử ghi danh lớp nhận chuyển")
    active_enrollments = db.scalars(select(StudentEnrollment).where(
        StudentEnrollment.student_id == student.id, StudentEnrollment.status == "active",
        StudentEnrollment.effective_to.is_(None),
    )).all()
    if action in {"withdraw", "transfer"} and not active_enrollments:
        raise HTTPException(409, "Học viên không có lớp đang học để cập nhật")
    history_action = {"defer": "deferred", "transfer": "transferred", "withdraw": "withdrawn"}[action]
    if action == "defer":
        for enrollment in active_enrollments:
            enrollment.status = "deferred"
            enrollment.effective_to = effective_date
        student.status = "deferred"
    elif action == "withdraw":
        for enrollment in active_enrollments:
            enrollment.status = "withdrawn"
            enrollment.effective_to = effective_date
        student.status = "withdrawn"
    else:
        for enrollment in active_enrollments:
            enrollment.status = "transferred"
            enrollment.effective_to = effective_date
        assert target_class is not None
        db.add(StudentEnrollment(
            student_id=student.id, class_id=target_class.id, status="active",
            effective_from=effective_date, actor_user_id=user.id,
        ))
        student.status = "active"
    student.status_effective_date = effective_date
    db.add(StudentStatusHistory(
        student_id=student.id, action=history_action, effective_date=effective_date,
        reason=reason, actor_user_id=user.id, target_class_id=target_class_id,
    ))
    db.commit()
    return {"student_id": student.id, "status": student.status, "effective_date": effective_date.isoformat(), "action": action}


def _class_summary(db: m.Session, training_class: m.TrainingClass) -> dict[str, Any]:
    details = db.scalar(select(ClassDetails).where(ClassDetails.class_id == training_class.id))
    program = db.get(m.TrainingProgram, training_class.program_id)
    enrolled = db.scalar(select(func.count(StudentEnrollment.id)).where(
        StudentEnrollment.class_id == training_class.id, StudentEnrollment.status == "active",
        StudentEnrollment.effective_to.is_(None),
    )) or 0
    total_lessons = db.scalar(select(func.count(TrainingLesson.id)).where(
        TrainingLesson.class_id == training_class.id, TrainingLesson.status.in_(["scheduled", "completed"]),
    )) or 0
    completed_lessons = db.scalar(select(func.count(TrainingLesson.id)).where(
        TrainingLesson.class_id == training_class.id,
        or_(
            TrainingLesson.status == "completed",
            and_(TrainingLesson.status == "scheduled", TrainingLesson.ends_at <= datetime.now()),
        ),
    )) or 0
    if training_class.status == "completed":
        curriculum_progress = 100
    elif total_lessons > 0:
        curriculum_progress = min(100, round((completed_lessons / total_lessons) * 100))
    else:
        curriculum_progress = 0
    instructor_ids = set(db.scalars(select(ClassSubject.instructor_id).where(
        ClassSubject.class_id == training_class.id, ClassSubject.instructor_id.is_not(None)
    )).all())
    return {
        "id": training_class.id, "program_id": training_class.program_id,
        "program_name": program.name if program else None,
        "code": details.code if details else None, "name": training_class.name,
        "start_date": details.start_date.isoformat() if details else None,
        "capacity": details.capacity if details else None, "format": details.format if details else None,
        "status": training_class.status, "enrollment_count": enrolled,
        "scheduled_lessons": total_lessons, "completed_lessons": completed_lessons,
        "curriculum_progress": curriculum_progress,
        "instructor_ids": sorted(instructor_ids),
        "capacity_warning": bool(details and enrolled > details.capacity),
    }


@m.app.get("/training/classes")
def global_classes(
    user: m.Annotated[m.User, Depends(m.require_permission("classes", "read"))],
    db: m.DbSession,
    q: str | None = None, program_id: int | None = None, status: str | None = None,
    instructor_id: int | None = None, date_from: date | None = None, date_to: date | None = None,
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    statement = select(m.TrainingClass).outerjoin(ClassDetails, ClassDetails.class_id == m.TrainingClass.id)
    if q:
        term = f"%{q.strip()}%"
        statement = statement.where(or_(ClassDetails.code.ilike(term), m.TrainingClass.name.ilike(term)))
    if program_id is not None:
        statement = statement.where(m.TrainingClass.program_id == program_id)
    if status:
        if status not in {"planned", "running", "completed", "cancelled"}:
            raise HTTPException(422, "Trạng thái lớp không hợp lệ")
        statement = statement.where(m.TrainingClass.status == status)
    if date_from:
        statement = statement.where(ClassDetails.start_date >= date_from)
    if date_to:
        statement = statement.where(ClassDetails.start_date <= date_to)
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "date_from không được sau date_to")
    if instructor_id is not None:
        instructor_classes = select(ClassSubject.class_id).where(ClassSubject.instructor_id == instructor_id)
        statement = statement.where(m.TrainingClass.id.in_(instructor_classes))
    if "training_manager" not in _roles(db, user) and "admin" not in _roles(db, user):
        assigned_class_ids = select(ClassSubject.class_id).outerjoin(ClassSubjectTA, ClassSubjectTA.class_subject_id == ClassSubject.id).where(
            or_(ClassSubject.instructor_id == user.id, ClassSubjectTA.user_id == user.id)
        )
        statement = statement.where(m.TrainingClass.id.in_(assigned_class_ids))
    count_statement = select(func.count()).select_from(statement.order_by(None).subquery())
    total = db.scalar(count_statement) or 0
    rows = db.scalars(statement.order_by(m.TrainingClass.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": _class_summaries(db, rows), "total": total, "page": page, "page_size": page_size}


@m.app.post("/training/classes", status_code=status.HTTP_201_CREATED)
def create_class(user: m.Annotated[m.User, Depends(m.require_permission("classes", "full"))], db: m.DbSession, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        program_id = int(payload["program_id"])
        start_date = _parse_date(payload["start_date"], "start_date")
        raw_capacity = payload["capacity"]
        if isinstance(raw_capacity, bool):
            raise ValueError("capacity")
        capacity = int(raw_capacity)
    except (KeyError, TypeError, ValueError) as error:
        raise HTTPException(422, "program_id, start_date và capacity hợp lệ là bắt buộc") from error
    program = db.get(m.TrainingProgram, program_id)
    if program is None or program.status != "active":
        raise HTTPException(422, "Chương trình không tồn tại hoặc đã ngừng áp dụng")
    code = str(payload.get("code", "")).strip()
    name = str(payload.get("name", "")).strip()
    class_format = str(payload.get("format", "in_person"))
    class_status = str(payload.get("status", "planned"))
    if not code or len(code) > 40 or not name or len(name) > 200 or capacity < 1:
        raise HTTPException(422, "Mã, tên hoặc sức chứa lớp không hợp lệ")
    if class_format not in {"in_person", "online", "hybrid"} or class_status not in {"planned", "running", "completed", "cancelled"}:
        raise HTTPException(422, "Hình thức hoặc trạng thái lớp không hợp lệ")
    if db.scalar(select(ClassDetails.id).where(func.lower(ClassDetails.code) == code.lower())):
        raise HTTPException(409, "Mã lớp đã tồn tại")
    training_class = m.TrainingClass(program_id=program_id, name=name, status=class_status)
    db.add(training_class)
    db.flush()
    db.add(ClassDetails(class_id=training_class.id, code=code, start_date=start_date, capacity=capacity, format=class_format))
    for association in db.scalars(select(m.ProgramSubject).where(
        m.ProgramSubject.program_id == program_id
    ).order_by(m.ProgramSubject.sequence_order)).all():
        db.add(ClassSubject(class_id=training_class.id, subject_id=association.subject_id, sequence_order=association.sequence_order))
    db.commit()
    return _class_summary(db, training_class)


@m.app.patch("/training/classes/{class_id}")
def update_class_full(
    class_id: int,
    user: m.Annotated[m.User, Depends(m.require_permission("classes", "full"))],
    db: m.DbSession,
    payload: dict[str, Any],
) -> dict[str, Any]:
    training_class = db.get(m.TrainingClass, class_id)
    if training_class is None:
        raise HTTPException(404, "Không tìm thấy lớp học")
    details = db.scalar(select(ClassDetails).where(ClassDetails.class_id == class_id))
    if not details:
        details = ClassDetails(class_id=class_id, code=f"CL{class_id:04d}", capacity=20)
        db.add(details)
    if "name" in payload:
        name = str(payload["name"]).strip()
        if not name or len(name) > 200:
            raise HTTPException(422, "Tên lớp không hợp lệ")
        training_class.name = name
    if "status" in payload:
        new_status = str(payload["status"])
        if new_status not in {"planned", "running", "completed", "cancelled"}:
            raise HTTPException(422, "Trạng thái lớp không hợp lệ")
        training_class.status = new_status
    if details:
        if "code" in payload:
            code = str(payload["code"]).strip()
            if not code or len(code) > 40:
                raise HTTPException(422, "Mã lớp không hợp lệ")
            dup = db.scalar(select(ClassDetails.id).where(func.lower(ClassDetails.code) == code.lower(), ClassDetails.class_id != class_id))
            if dup:
                raise HTTPException(409, "Mã lớp đã tồn tại")
            details.code = code
        if "capacity" in payload:
            capacity = int(payload["capacity"])
            if capacity < 1:
                raise HTTPException(422, "Sức chứa tối thiểu 1 học viên")
            details.capacity = capacity
        if "format" in payload:
            fmt = str(payload["format"])
            if fmt in {"in_person", "online", "hybrid"}:
                details.format = fmt
        if "start_date" in payload and payload["start_date"]:
            details.start_date = _parse_date(payload["start_date"], "start_date")
    db.commit()
    db.refresh(training_class)
    return _class_summary(db, training_class)


@m.app.delete("/training/classes/{class_id}")
def delete_class(
    class_id: int,
    user: m.Annotated[m.User, Depends(m.require_permission("classes", "full"))],
    db: m.DbSession,
) -> dict[str, Any]:
    training_class = db.get(m.TrainingClass, class_id)
    if training_class is None:
        raise HTTPException(404, "Không tìm thấy lớp học")
    # Kiểm tra xem lớp đã có lịch hoặc học viên chưa
    has_enrollment = db.scalar(select(StudentEnrollment.id).where(StudentEnrollment.class_id == class_id))
    has_session = db.scalar(select(ClassSession.id).where(ClassSession.class_id == class_id))
    if has_enrollment or has_session:
        # Nếu đã có dữ liệu, chuyển sang trạng thái đã hủy (cancelled) để bảo toàn dữ liệu
        training_class.status = "cancelled"
        db.commit()
        return {"message": "Lớp học đã có dữ liệu liên quan, đã được chuyển sang trạng thái Đã hủy.", "status": "cancelled"}
    
    # Nếu là lớp mới tạo chưa có học viên/lịch thì xóa hoàn toàn
    db.execute(delete(ClassSubjectTA).where(ClassSubjectTA.class_subject_id.in_(select(ClassSubject.id).where(ClassSubject.class_id == class_id))))
    db.execute(delete(ClassSubject).where(ClassSubject.class_id == class_id))
    db.execute(delete(ClassDetails).where(ClassDetails.class_id == class_id))
    db.delete(training_class)
    db.commit()
    return {"message": "Đã xóa lớp học thành công.", "id": class_id}


@m.app.get("/training/classes/{class_id}/enrollments")
def list_enrollments(
    class_id: int,
    user: m.Annotated[m.User, Depends(m.require_permission("classes", "read"))],
    db: m.DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    if db.get(m.TrainingClass, class_id) is None:
        raise HTTPException(404, "Không tìm thấy lớp học")
    if not _allowed(db, user, "classes", "full") and not _can_manage_class(db, user, class_id):
        raise HTTPException(403, "Bạn chưa được phân công vào lớp này")
    base = select(StudentEnrollment, StudentProfile, m.User).join(
        StudentProfile, StudentProfile.id == StudentEnrollment.student_id
    ).outerjoin(
        m.User, m.User.id == StudentEnrollment.actor_user_id
    ).where(StudentEnrollment.class_id == class_id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.execute(base.order_by(StudentEnrollment.enrolled_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [
        {"student_id": student.id, "student_code": student.student_code, "full_name": student.full_name,
         "status": enrollment.status, "enrolled_at": enrollment.enrolled_at.isoformat(),
         "effective_from": enrollment.effective_from.isoformat(),
         "enrolled_by": actor.full_name if actor else None,
         "effective_to": enrollment.effective_to.isoformat() if enrollment.effective_to else None}
        for enrollment, student, actor in rows
    ], "total": total, "page": page, "page_size": page_size}


@m.app.post("/training/classes/{class_id}/enrollments", status_code=status.HTTP_201_CREATED)
def bulk_enroll(class_id: int, user: m.Annotated[m.User, Depends(m.require_permission("classes", "full"))], db: m.DbSession, payload: dict[str, Any]) -> dict[str, Any]:
    training_class = db.get(m.TrainingClass, class_id)
    if training_class is None:
        raise HTTPException(404, "Không tìm thấy lớp học")
    student_ids = payload.get("student_ids")
    if not isinstance(student_ids, list) or not student_ids or len(student_ids) > 500:
        raise HTTPException(422, "Chọn từ 1 đến 500 học viên")
    try:
        ids = [int(value) for value in student_ids]
    except (TypeError, ValueError) as error:
        raise HTTPException(422, "student_ids phải là số nguyên") from error
    if len(ids) != len(set(ids)):
        raise HTTPException(409, "Danh sách học viên có bản ghi trùng lặp")
    students = db.scalars(select(StudentProfile).where(StudentProfile.id.in_(ids))).all()
    if len(students) != len(ids) or any(student.status != "active" for student in students):
        raise HTTPException(422, "Một hoặc nhiều học viên không tồn tại hoặc không ở trạng thái active")
    existing_ids = set(db.scalars(select(StudentEnrollment.student_id).where(
        StudentEnrollment.class_id == class_id, StudentEnrollment.student_id.in_(ids),
    )).all())
    if existing_ids:
        raise HTTPException(409, "Một hoặc nhiều học viên đã có lịch sử ghi danh lớp này")
    details = db.scalar(select(ClassDetails).where(ClassDetails.class_id == class_id))
    count = db.scalar(select(func.count(StudentEnrollment.id)).where(
        StudentEnrollment.class_id == class_id, StudentEnrollment.status == "active",
        StudentEnrollment.effective_to.is_(None),
    )) or 0
    if details and count + len(ids) > details.capacity:
        raise HTTPException(409, f"Vượt sức chứa lớp: còn {max(0, details.capacity - count)} chỗ")
    for student in students:
        db.add(StudentEnrollment(student_id=student.id, class_id=class_id, actor_user_id=user.id, effective_from=date.today()))
    db.commit()
    return {"enrolled_count": len(students), "class_id": class_id}


@m.app.get("/training/classes/{class_id}/subjects")
def list_class_subject_staff(class_id: int, user: m.Annotated[m.User, Depends(m.require_permission("classes", "read"))], db: m.DbSession) -> list[dict[str, Any]]:
    if db.get(m.TrainingClass, class_id) is None:
        raise HTTPException(404, "Không tìm thấy lớp học")
    if not _allowed(db, user, "classes", "full") and not _can_manage_class(db, user, class_id):
        raise HTTPException(403, "Bạn chưa được phân công vào lớp này")
    assignments = db.execute(
        select(ClassSubject, m.TrainingSubject, m.User)
        .join(m.TrainingSubject, m.TrainingSubject.id == ClassSubject.subject_id)
        .outerjoin(m.User, m.User.id == ClassSubject.instructor_id)
        .where(ClassSubject.class_id == class_id)
        .order_by(ClassSubject.sequence_order)
    ).all()
    assignment_ids = [assignment.id for assignment, _, _ in assignments]
    tas_by_assignment: dict[int, list[dict[str, Any]]] = {item_id: [] for item_id in assignment_ids}
    if assignment_ids:
        for assignment_id, ta in db.execute(
            select(ClassSubjectTA.class_subject_id, m.User)
            .join(m.User, m.User.id == ClassSubjectTA.user_id)
            .where(ClassSubjectTA.class_subject_id.in_(assignment_ids))
            .order_by(m.User.full_name)
        ).all():
            tas_by_assignment[assignment_id].append({"id": ta.id, "full_name": ta.full_name})
    return [
        {
            "id": assignment.id, "subject_id": subject.id, "subject_code": subject.code,
            "subject_name": subject.name, "sequence_order": assignment.sequence_order,
            "instructor": {"id": instructor.id, "full_name": instructor.full_name} if instructor else None,
            "tas": tas_by_assignment[assignment.id],
        }
        for assignment, subject, instructor in assignments
    ]


@m.app.put("/training/classes/{class_id}/subjects/{subject_id}/staff")
def assign_class_subject_staff(class_id: int, subject_id: int, user: m.Annotated[m.User, Depends(m.require_permission("classes", "full"))], db: m.DbSession, payload: dict[str, Any]) -> dict[str, Any]:
    training_class = db.get(m.TrainingClass, class_id)
    if training_class is None:
        raise HTTPException(404, "Không tìm thấy lớp học")
    assignment = db.scalar(select(ClassSubject).where(ClassSubject.class_id == class_id, ClassSubject.subject_id == subject_id))
    if assignment is None:
        # Nếu môn học thuộc chương trình của lớp nhưng chưa có trong ClassSubject, tự động tạo mới
        is_program_subject = db.scalar(select(m.ProgramSubject.id).where(m.ProgramSubject.program_id == training_class.program_id, m.ProgramSubject.subject_id == subject_id))
        subject_exists = db.get(m.TrainingSubject, subject_id)
        if subject_exists and (is_program_subject or True):
            assignment = ClassSubject(class_id=class_id, subject_id=subject_id, sequence_order=1)
            db.add(assignment)
            db.flush()
        else:
            raise HTTPException(404, "Môn học không thuộc lớp này")
    instructor_id = payload.get("instructor_id")
    ta_ids = payload.get("ta_ids", [])
    if not isinstance(ta_ids, list) or len(ta_ids) > 100:
        raise HTTPException(422, "ta_ids phải là danh sách tối đa 100 trợ giảng")
    try:
        instructor_id = int(instructor_id) if instructor_id is not None else None
        normalized_ta = list(dict.fromkeys(int(item) for item in ta_ids))
    except (TypeError, ValueError) as error:
        raise HTTPException(422, "Thông tin giảng viên hoặc trợ giảng không hợp lệ") from error
    ids = ([instructor_id] if instructor_id else []) + normalized_ta
    accounts = {item.id: item for item in db.scalars(select(m.User).where(m.User.id.in_(ids))).all()} if ids else {}
    roles_by_id = {identifier: _roles(db, accounts[identifier]) for identifier in accounts}
    if instructor_id is not None and (instructor_id not in accounts or not accounts[instructor_id].is_active or "instructor" not in roles_by_id[instructor_id]):
        raise HTTPException(422, "Người phụ trách phải là giảng viên đang hoạt động")
    if any(identifier not in accounts or not accounts[identifier].is_active or "ta" not in roles_by_id[identifier] for identifier in normalized_ta):
        raise HTTPException(422, "Các tài khoản trợ giảng phải đang hoạt động và có vai trò TA")
    assignment.instructor_id = instructor_id
    db.query(ClassSubjectTA).filter(ClassSubjectTA.class_subject_id == assignment.id).delete(synchronize_session=False)
    for identifier in normalized_ta:
        db.add(ClassSubjectTA(class_subject_id=assignment.id, user_id=identifier))
    db.commit()
    return {"class_id": class_id, "subject_id": subject_id, "instructor_id": instructor_id, "ta_ids": normalized_ta}


@m.app.get("/training/rooms")
def list_rooms(user: m.Annotated[m.User, Depends(m.require_permission("classes", "read"))], db: m.DbSession, include_inactive: bool = False) -> list[dict[str, Any]]:
    statement = select(TrainingRoom)
    if not include_inactive or not _allowed(db, user, "classes", "full"):
        statement = statement.where(TrainingRoom.is_active.is_(True))
    return [
        {"id": room.id, "code": room.code, "name": room.name, "room_type": room.room_type,
         "capacity": room.capacity, "location": room.location, "online_link": room.online_link,
         "is_active": room.is_active}
        for room in db.scalars(statement.order_by(TrainingRoom.name)).all()
    ]


def _room_fields(payload: dict[str, Any], current: TrainingRoom | None = None) -> dict[str, Any]:
    values = {
        key: payload.get(key, getattr(current, key, True if key == "is_active" else None))
        for key in ("code", "name", "room_type", "capacity", "location", "online_link", "is_active")
    }
    values["code"] = str(values["code"] or "").strip()
    values["name"] = str(values["name"] or "").strip()
    if not values["code"] or len(values["code"]) > 40 or not values["name"] or len(values["name"]) > 120:
        raise HTTPException(422, "Mã phòng và tên phòng là bắt buộc")
    if values["room_type"] not in {"physical", "online"}:
        raise HTTPException(422, "room_type phải là physical hoặc online")
    if values["room_type"] == "physical":
        if isinstance(values["capacity"], bool) or not isinstance(values["capacity"], int) or values["capacity"] < 1 or not values["location"]:
            raise HTTPException(422, "Phòng vật lý cần capacity dương và location")
        values["online_link"] = None
    elif not values["online_link"] or len(str(values["online_link"])) > 1000:
        raise HTTPException(422, "Phòng trực tuyến cần online_link")
    else:
        values["capacity"] = None
        values["location"] = None
    values["is_active"] = bool(values["is_active"])
    return values


@m.app.post("/training/rooms", status_code=status.HTTP_201_CREATED)
def create_room(user: m.Annotated[m.User, Depends(m.require_permission("classes", "full"))], db: m.DbSession, payload: dict[str, Any]) -> dict[str, Any]:
    values = _room_fields(payload)
    if db.scalar(select(TrainingRoom.id).where(func.lower(TrainingRoom.code) == values["code"].lower())):
        raise HTTPException(409, "Mã phòng đã tồn tại")
    room = TrainingRoom(**values)
    db.add(room)
    db.commit()
    db.refresh(room)
    return {"id": room.id, **values}


@m.app.patch("/training/rooms/{room_id}")
def update_room(room_id: int, user: m.Annotated[m.User, Depends(m.require_permission("classes", "full"))], db: m.DbSession, payload: dict[str, Any]) -> dict[str, Any]:
    room = db.get(TrainingRoom, room_id)
    if room is None:
        raise HTTPException(404, "Không tìm thấy phòng học")
    values = _room_fields(payload, room)
    if db.scalar(select(TrainingRoom.id).where(func.lower(TrainingRoom.code) == values["code"].lower(), TrainingRoom.id != room.id)):
        raise HTTPException(409, "Mã phòng đã tồn tại")
    for key, value in values.items():
        setattr(room, key, value)
    db.commit()
    return {"id": room.id, **values}


@m.app.delete("/training/rooms/{room_id}")
def delete_room(room_id: int, user: m.Annotated[m.User, Depends(m.require_permission("classes", "full"))], db: m.DbSession) -> dict[str, str]:
    room = db.get(TrainingRoom, room_id)
    if room is None:
        raise HTTPException(404, "Không tìm thấy phòng học")
    if db.scalar(select(TrainingLesson.id).where(TrainingLesson.room_id == room.id).limit(1)):
        room.is_active = False
    else:
        db.delete(room)
    db.commit()
    return {"message": "Đã xóa hoặc ngừng sử dụng phòng học"}


@m.app.post("/training/holidays", status_code=status.HTTP_201_CREATED)
def create_holiday(user: m.Annotated[m.User, Depends(m.require_permission("classes", "full"))], db: m.DbSession, payload: dict[str, Any]) -> dict[str, Any]:
    holiday_date = _parse_date(payload.get("holiday_date"), "holiday_date")
    name = str(payload.get("name", "")).strip()
    if not name or len(name) > 120:
        raise HTTPException(422, "Tên ngày nghỉ là bắt buộc")
    existing = db.scalar(select(TrainingHoliday).where(TrainingHoliday.holiday_date == holiday_date))
    if existing:
        raise HTTPException(409, "Ngày nghỉ đã được cấu hình")
    row = TrainingHoliday(holiday_date=holiday_date, name=name)
    db.add(row)
    db.commit()
    return {"id": row.id, "holiday_date": holiday_date.isoformat(), "name": name}


@m.app.get("/training/holidays")
def list_holidays(user: m.Annotated[m.User, Depends(m.require_permission("classes", "read"))], db: m.DbSession, start: date | None = None, end: date | None = None) -> list[dict[str, Any]]:
    if start and end and start > end:
        raise HTTPException(422, "start không được sau end")
    statement = select(TrainingHoliday)
    if start:
        statement = statement.where(TrainingHoliday.holiday_date >= start)
    if end:
        statement = statement.where(TrainingHoliday.holiday_date <= end)
    return [
        {"id": row.id, "holiday_date": row.holiday_date.isoformat(), "name": row.name}
        for row in db.scalars(statement.order_by(TrainingHoliday.holiday_date).limit(500)).all()
    ]


@m.app.post("/training/classes/{class_id}/schedule/preview")
def preview_schedule(class_id: int, user: m.Annotated[m.User, Depends(m.require_permission("classes", "full"))], db: m.DbSession, payload: ScheduleRequest) -> dict[str, Any]:
    if db.get(m.TrainingClass, class_id) is None:
        raise HTTPException(404, "Không tìm thấy lớp học")
    drafts = _schedule_drafts(db, class_id, payload)
    conflicts = [item for draft in drafts for item in draft["conflicts"]]
    return {
        "sessions": [
            {**{key: value.isoformat() if isinstance(value, datetime) else value for key, value in draft.items() if key != "conflicts"},
             "conflicts": draft["conflicts"]}
            for draft in drafts
        ],
        "conflicts": conflicts,
        "has_conflicts": bool(conflicts),
    }


@m.app.post("/training/classes/{class_id}/schedule", status_code=status.HTTP_201_CREATED)
def create_schedule(class_id: int, user: m.Annotated[m.User, Depends(m.require_permission("classes", "full"))], db: m.DbSession, payload: ScheduleRequest) -> dict[str, Any]:
    training_class = db.get(m.TrainingClass, class_id)
    if training_class is None:
        raise HTTPException(404, "Không tìm thấy lớp học")
    drafts = _schedule_drafts(db, class_id, payload)
    conflicts = [conflict for draft in drafts for conflict in draft["conflicts"]]
    if any(item["class_conflict"] for item in conflicts) or (
        conflicts and not (payload.override_conflicts and {"training_manager", "admin"}.intersection(_roles(db, user)))
    ):
        raise HTTPException(409, detail={"message": "Lịch có xung đột; chỉ quản lý đào tạo có thể xác nhận ghi đè", "conflicts": conflicts})
    created = []
    for draft in drafts:
        lesson = TrainingLesson(
            class_id=class_id, class_subject_id=draft["class_subject_id"],
            subject_session_id=draft["subject_session_id"], room_id=draft["room_id"],
            instructor_id=draft["instructor_id"], title=draft["title"],
            starts_at=draft["starts_at"], ends_at=draft["ends_at"], created_by=user.id,
        )
        db.add(lesson)
        db.flush()
        db.add(LessonAudit(lesson_id=lesson.id, actor_user_id=user.id, action="created", detail="Tạo lịch định kỳ"))
        created.append(lesson)
    db.commit()
    return {"created_count": len(created), "sessions": [_lesson_json(db, lesson) for lesson in created]}


@m.app.get("/training/sessions")
def list_sessions(
    user: m.Annotated[m.User, Depends(m.require_permission("classes", "read"))],
    db: m.DbSession,
    start: date, end: date, class_id: int | None = None,
    instructor_id: int | None = None, room_id: int | None = None,
) -> list[dict[str, Any]]:
    if start > end or (end - start).days > 93:
        raise HTTPException(422, "start/end phải hợp lệ và phạm vi tối đa 94 ngày")
    statement = select(TrainingLesson).where(
        TrainingLesson.starts_at >= datetime.combine(start, time.min),
        TrainingLesson.starts_at < datetime.combine(end + timedelta(days=1), time.min),
    )
    if class_id is not None:
        statement = statement.where(TrainingLesson.class_id == class_id)
    if instructor_id is not None:
        statement = statement.where(TrainingLesson.instructor_id == instructor_id)
    if room_id is not None:
        statement = statement.where(TrainingLesson.room_id == room_id)
    roles = _roles(db, user)
    if "training_manager" not in roles and "admin" not in roles:
        assigned_classes = select(ClassSubject.class_id).outerjoin(ClassSubjectTA, ClassSubjectTA.class_subject_id == ClassSubject.id).where(
            or_(ClassSubject.instructor_id == user.id, ClassSubjectTA.user_id == user.id)
        )
        own_student = db.scalar(select(StudentProfile.id).where(StudentProfile.user_id == user.id))
        if own_student:
            enrolled_classes = select(StudentEnrollment.class_id).where(
                StudentEnrollment.student_id == own_student, StudentEnrollment.status == "active",
                StudentEnrollment.effective_from <= end,
                or_(StudentEnrollment.effective_to.is_(None), StudentEnrollment.effective_to > start),
            )
            statement = statement.where(or_(TrainingLesson.class_id.in_(assigned_classes), TrainingLesson.class_id.in_(enrolled_classes)))
        else:
            statement = statement.where(TrainingLesson.class_id.in_(assigned_classes))
    rows = db.scalars(statement.order_by(TrainingLesson.starts_at).limit(1000)).all()
    return [_lesson_json(db, row) for row in rows]


@m.app.get("/training/sessions/{session_id}")
def get_session(session_id: int, user: m.CurrentUser, db: m.DbSession) -> dict[str, Any]:
    lesson = db.get(TrainingLesson, session_id)
    if lesson is None:
        raise HTTPException(404, "Không tìm thấy buổi học")
    if not _allowed(db, user, "classes", "full") and not _can_manage_class(db, user, lesson.class_id):
        student_id = db.scalar(select(StudentProfile.id).where(StudentProfile.user_id == user.id))
        enrollment = db.scalar(select(StudentEnrollment.id).where(
            StudentEnrollment.student_id == (student_id or -1),
            StudentEnrollment.class_id == lesson.class_id,
            StudentEnrollment.effective_from <= lesson.starts_at.date(),
            or_(StudentEnrollment.effective_to.is_(None), StudentEnrollment.effective_to > lesson.starts_at.date()),
        ))
        if enrollment is None:
            raise HTTPException(404, "Không tìm thấy buổi học")
    return _lesson_json(db, lesson)


@m.app.patch("/training/sessions/{session_id}")
def update_session(session_id: int, user: m.Annotated[m.User, Depends(m.require_permission("classes", "full"))], db: m.DbSession, payload: dict[str, Any]) -> dict[str, Any]:
    lesson = db.get(TrainingLesson, session_id)
    if lesson is None:
        raise HTTPException(404, "Không tìm thấy buổi học")
    if lesson.starts_at.date() <= date.today():
        raise HTTPException(409, "Chỉ được đổi buổi học tương lai")
    if lesson.status != "scheduled" or db.scalar(select(Attendance.id).where(Attendance.lesson_id == lesson.id).limit(1)):
        raise HTTPException(409, "Không thể đổi buổi đã điểm danh hoặc đã hủy")
    allowed = {"starts_at", "ends_at", "room_id", "instructor_id", "title", "override_conflicts", "reason"}
    if not payload or set(payload) - allowed:
        raise HTTPException(422, "Các trường cập nhật buổi học không hợp lệ")
    old = {"starts_at": lesson.starts_at.isoformat(), "ends_at": lesson.ends_at.isoformat(), "room_id": lesson.room_id, "instructor_id": lesson.instructor_id}
    for field in ("starts_at", "ends_at"):
        if field in payload:
            setattr(lesson, field, _parse_datetime(payload[field], field))
    if lesson.ends_at <= lesson.starts_at:
        raise HTTPException(422, "ends_at phải sau starts_at")
    if "room_id" in payload:
        room_id = payload["room_id"]
        room = db.get(TrainingRoom, int(room_id)) if room_id is not None else None
        if room_id is not None and (room is None or not room.is_active):
            raise HTTPException(422, "Phòng học không tồn tại hoặc không hoạt động")
        lesson.room_id = room.id if room else None
    if "instructor_id" in payload:
        lesson.instructor_id = int(payload["instructor_id"]) if payload["instructor_id"] is not None else None
    if "title" in payload:
        title = str(payload["title"]).strip()
        if not title or len(title) > 200:
            raise HTTPException(422, "Tiêu đề buổi học không hợp lệ")
        lesson.title = title
    reason = str(payload.get("reason", "")).strip()
    if len(reason) > 1000:
        raise HTTPException(422, "Lý do thay đổi tối đa 1000 ký tự")
    conflicts = _conflicts(
        db, lesson.starts_at, lesson.ends_at, lesson.room_id, lesson.instructor_id,
        lesson.id, lesson.class_id,
    )
    override = payload.get("override_conflicts") is True and {"training_manager", "admin"}.intersection(_roles(db, user))
    if any(item["class_conflict"] for item in conflicts) or (conflicts and not override):
        raise HTTPException(409, detail={"message": "Buổi học bị xung đột", "conflicts": conflicts})
    lesson.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(LessonAudit(lesson_id=lesson.id, actor_user_id=user.id, action="rescheduled", detail=str({
        "old": old,
        "new": {key: getattr(lesson, key) for key in ("starts_at", "ends_at", "room_id", "instructor_id")},
        "reason": reason or None,
    })))
    _notify_lesson_people(db, lesson, f"Buổi học {lesson.title} đã được điều chỉnh.{f' Lý do: {reason}' if reason else ''}")
    db.commit()
    return _lesson_json(db, lesson)


@m.app.post("/training/sessions/{session_id}/cancel")
def cancel_session(session_id: int, user: m.Annotated[m.User, Depends(m.require_permission("classes", "full"))], db: m.DbSession, payload: dict[str, Any]) -> dict[str, Any]:
    lesson = db.get(TrainingLesson, session_id)
    if lesson is None:
        raise HTTPException(404, "Không tìm thấy buổi học")
    if lesson.starts_at.date() <= date.today():
        raise HTTPException(409, "Chỉ được hủy buổi học tương lai")
    if lesson.status != "scheduled" or db.scalar(select(Attendance.id).where(Attendance.lesson_id == lesson.id).limit(1)):
        raise HTTPException(409, "Không thể hủy buổi đã điểm danh hoặc đã hủy")
    reason = str(payload.get("reason", "")).strip()
    if not reason or len(reason) > 1000:
        raise HTTPException(422, "Lý do hủy là bắt buộc")
    lesson.status = "cancelled"
    lesson.cancellation_reason = reason
    db.add(LessonAudit(lesson_id=lesson.id, actor_user_id=user.id, action="cancelled", detail=reason))
    _notify_lesson_people(db, lesson, f"Buổi học {lesson.title} đã bị hủy. Lý do: {reason}")
    db.commit()
    return {"id": lesson.id, "status": lesson.status, "reason": reason}


@m.app.get("/training/sessions/{session_id}/attendance")
def get_attendance(session_id: int, user: m.CurrentUser, db: m.DbSession) -> dict[str, Any]:
    lesson = db.get(TrainingLesson, session_id)
    if lesson is None:
        raise HTTPException(404, "Không tìm thấy buổi học")
    if not _allowed(db, user, "attendance", "read") and db.scalar(select(StudentProfile.id).where(StudentProfile.user_id == user.id)) is None:
        raise HTTPException(403, "Bạn không có quyền xem điểm danh")
    if (
        not _allowed(db, user, "attendance", "full")
        and db.scalar(select(StudentProfile.id).where(StudentProfile.user_id == user.id)) is None
        and not _can_manage_class(db, user, lesson.class_id)
    ):
        raise HTTPException(403, "Bạn chưa được phân công vào lớp này")
    rows = db.execute(select(StudentProfile, Attendance).outerjoin(
        Attendance, and_(Attendance.student_id == StudentProfile.id, Attendance.lesson_id == lesson.id)
    ).join(StudentEnrollment, StudentEnrollment.student_id == StudentProfile.id).where(
        StudentEnrollment.class_id == lesson.class_id,
        StudentEnrollment.effective_from <= lesson.starts_at.date(),
        or_(StudentEnrollment.effective_to.is_(None), StudentEnrollment.effective_to > lesson.starts_at.date()),
    ).order_by(StudentProfile.student_code)).all()
    return {"session_id": lesson.id, "items": [
        {"student_id": student.id, "student_code": student.student_code, "full_name": student.full_name,
         "status": attendance.status if attendance else None, "note": attendance.note if attendance else None}
        for student, attendance in rows
        if _can_manage_class(db, user, lesson.class_id) or student.user_id == user.id
    ]}


@m.app.put("/training/sessions/{session_id}/attendance")
def update_attendance(session_id: int, user: m.CurrentUser, db: m.DbSession, payload: dict[str, Any]) -> dict[str, Any]:
    lesson = db.get(TrainingLesson, session_id)
    if lesson is None:
        raise HTTPException(404, "Không tìm thấy buổi học")
    _attendance_permission(db, user, lesson)
    entries = payload.get("items")
    if not isinstance(entries, list) or not entries or len(entries) > 500:
        raise HTTPException(422, "items phải chứa từ 1 đến 500 bản ghi điểm danh")
    valid_statuses = {"present", "late", "excused", "unexcused"}
    try:
        requested_ids = [int(entry["student_id"]) for entry in entries]
    except (KeyError, TypeError, ValueError) as error:
        raise HTTPException(422, "student_id không hợp lệ") from error
    if len(requested_ids) != len(set(requested_ids)):
        raise HTTPException(422, "Danh sách điểm danh không được chứa học viên trùng lặp")
    roster_ids = {student.id for student in _student_roster(db, lesson.class_id, lesson.starts_at.date())}
    for entry in entries:
        try:
            student_id = int(entry["student_id"])
        except (KeyError, TypeError, ValueError) as error:
            raise HTTPException(422, "student_id không hợp lệ") from error
        attendance_status = str(entry.get("status", ""))
        if student_id not in roster_ids:
            raise HTTPException(422, f"Học viên {student_id} không thuộc danh sách điểm danh")
        if attendance_status not in valid_statuses:
            raise HTTPException(422, "Trạng thái phải là present, late, excused hoặc unexcused")
        note = str(entry.get("note", "") or "").strip() or None
        if note and len(note) > 1000:
            raise HTTPException(422, "Ghi chú điểm danh tối đa 1000 ký tự")
        _upsert_attendance(db, lesson, db.get(StudentProfile, student_id), user, attendance_status, note)
    db.commit()
    return {"updated_count": len(entries)}


@m.app.post("/training/sessions/{session_id}/attendance/bulk-present")
def bulk_present(session_id: int, user: m.CurrentUser, db: m.DbSession) -> dict[str, Any]:
    lesson = db.get(TrainingLesson, session_id)
    if lesson is None:
        raise HTTPException(404, "Không tìm thấy buổi học")
    _attendance_permission(db, user, lesson)
    students = _student_roster(db, lesson.class_id, lesson.starts_at.date())
    for student in students:
        _upsert_attendance(db, lesson, student, user, "present")
    db.commit()
    return {"updated_count": len(students), "status": "present"}


@m.app.get("/attendance/absence-requests")
def list_absence_requests(
    user: m.CurrentUser,
    db: m.DbSession,
    status_filter: str | None = None,
    page: int | None = Query(default=None, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> list[dict[str, Any]] | dict[str, Any]:
    _need(db, user, "attendance", "read")
    statement = select(AbsenceRequest)
    roles = _roles(db, user)
    if "student" in roles and not _allowed(db, user, "attendance", "full"):
        student_id = db.scalar(select(StudentProfile.id).where(StudentProfile.user_id == user.id))
        statement = statement.where(AbsenceRequest.student_id == (student_id or -1))
    elif not _allowed(db, user, "attendance", "full"):
        assigned_classes = select(ClassSubject.class_id).outerjoin(ClassSubjectTA, ClassSubjectTA.class_subject_id == ClassSubject.id).where(or_(ClassSubject.instructor_id == user.id, ClassSubjectTA.user_id == user.id))
        statement = statement.join(TrainingLesson, TrainingLesson.id == AbsenceRequest.lesson_id).where(TrainingLesson.class_id.in_(assigned_classes))
    if status_filter:
        if status_filter not in {"pending", "approved", "rejected"}:
            raise HTTPException(422, "Trạng thái yêu cầu không hợp lệ")
        statement = statement.where(AbsenceRequest.status == status_filter)
    total = db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
    ordered = statement.order_by(AbsenceRequest.created_at.desc(), AbsenceRequest.id.desc())
    rows = (
        db.scalars(ordered.offset((page - 1) * page_size).limit(page_size)).all()
        if page is not None
        else db.scalars(ordered.limit(100)).all()
    )
    items = []
    for row in rows:
        student = db.get(StudentProfile, row.student_id)
        lesson = db.get(TrainingLesson, row.lesson_id)
        items.append({
            "id": row.id, "lesson_id": row.lesson_id, "student_id": row.student_id,
            "student_name": student.full_name if student else None,
            "session_title": lesson.title if lesson else None,
            "starts_at": lesson.starts_at.isoformat() if lesson else None,
            "reason": row.reason, "evidence_ref": row.evidence_ref, "status": row.status,
            "decision_reason": row.decision_reason, "created_at": row.created_at.isoformat(),
        })
    if page is None:
        return items
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@m.app.post("/attendance/absence-requests", status_code=status.HTTP_201_CREATED)
def create_absence_request(user: m.Annotated[m.User, Depends(m.require_permission("attendance", "write"))], db: m.DbSession, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        lesson_id = int(payload["lesson_id"])
    except (KeyError, TypeError, ValueError) as error:
        raise HTTPException(422, "lesson_id hợp lệ là bắt buộc") from error
    student, _, reason = _validate_absence_submission(user, db, lesson_id, str(payload.get("reason", "")))
    evidence = str(payload.get("evidence_ref", "") or "").strip() or None
    if evidence and len(evidence) > 1000:
        raise HTTPException(422, "evidence_ref tối đa 1000 ký tự")
    request_row = AbsenceRequest(lesson_id=lesson_id, student_id=student.id, reason=reason, evidence_ref=evidence)
    db.add(request_row)
    db.commit()
    db.refresh(request_row)
    return {"id": request_row.id, "lesson_id": lesson_id, "student_id": student.id, "status": "pending"}


def _validate_absence_submission(
    user: m.User, db: m.Session, lesson_id: int, reason: str
) -> tuple[StudentProfile, TrainingLesson, str]:
    student = db.scalar(select(StudentProfile).where(StudentProfile.user_id == user.id))
    if student is None:
        raise HTTPException(403, "Chỉ học viên có thể gửi yêu cầu vắng mặt")
    lesson = db.get(TrainingLesson, lesson_id)
    if lesson is None:
        raise HTTPException(404, "Không tìm thấy buổi học")
    if student not in _student_roster(db, lesson.class_id, lesson.starts_at.date()):
        raise HTTPException(403, "Buổi học không thuộc lớp đang học của bạn")
    normalized_reason = reason.strip()
    if not normalized_reason or len(normalized_reason) > 2000:
        raise HTTPException(422, "Lý do bắt buộc, tối đa 2000 ký tự")
    existing = db.scalar(select(AbsenceRequest.id).where(
        AbsenceRequest.lesson_id == lesson_id,
        AbsenceRequest.student_id == student.id,
        AbsenceRequest.status == "pending",
    ))
    if existing:
        raise HTTPException(409, "Đã có yêu cầu đang chờ xử lý cho buổi học này")
    return student, lesson, normalized_reason


@m.app.post("/attendance/absence-requests/upload", status_code=status.HTTP_201_CREATED)
async def create_absence_request_with_evidence(
    user: m.Annotated[m.User, Depends(m.require_permission("attendance", "write"))],
    db: m.DbSession,
    lesson_id: int = Form(...),
    reason: str = Form(...),
    file: UploadFile = File(...),
) -> dict[str, Any]:
    student, _, normalized_reason = _validate_absence_submission(user, db, lesson_id, reason)
    original_name = Path((file.filename or "evidence").replace("\\", "/")).name[:255]
    suffix = Path(original_name).suffix.lower()
    if suffix not in ABSENCE_EVIDENCE_SUFFIXES:
        raise HTTPException(415, "Chỉ chấp nhận tệp PDF, JPG hoặc PNG")
    data = await file.read(ABSENCE_EVIDENCE_MAX_BYTES + 1)
    if not data or len(data) > ABSENCE_EVIDENCE_MAX_BYTES:
        raise HTTPException(413, "Minh chứng phải có dung lượng từ 1 byte đến 10 MB")
    signatures = {
        ".pdf": data.startswith(b"%PDF-"),
        ".jpg": data.startswith(b"\xff\xd8\xff"),
        ".jpeg": data.startswith(b"\xff\xd8\xff"),
        ".png": data.startswith(b"\x89PNG\r\n\x1a\n"),
    }
    if not signatures[suffix]:
        raise HTTPException(415, "Nội dung tệp không khớp với định dạng được hỗ trợ")

    storage_name = f"{secrets.token_hex(24)}{suffix}"
    target = ABSENCE_EVIDENCE_DIR / storage_name
    target.write_bytes(data)
    request_row = AbsenceRequest(
        lesson_id=lesson_id,
        student_id=student.id,
        reason=normalized_reason,
        evidence_ref=f"private:{storage_name}",
    )
    db.add(request_row)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        target.unlink(missing_ok=True)
        raise
    db.refresh(request_row)
    return {
        "id": request_row.id,
        "lesson_id": lesson_id,
        "student_id": student.id,
        "status": request_row.status,
        "evidence_ref": request_row.evidence_ref,
    }


@m.app.get("/attendance/absence-requests/{request_id}/evidence")
def download_absence_evidence(
    request_id: int, user: m.CurrentUser, db: m.DbSession
) -> FileResponse:
    _need(db, user, "attendance", "read")
    request_row = db.get(AbsenceRequest, request_id)
    if request_row is None or not request_row.evidence_ref or not request_row.evidence_ref.startswith("private:"):
        raise HTTPException(404, "Không tìm thấy minh chứng")
    if not _allowed(db, user, "attendance", "full"):
        roles = _roles(db, user)
        if "student" in roles:
            student_id = db.scalar(select(StudentProfile.id).where(StudentProfile.user_id == user.id))
            if student_id != request_row.student_id:
                raise HTTPException(403, "Bạn không có quyền xem minh chứng này")
        else:
            lesson = db.get(TrainingLesson, request_row.lesson_id)
            if lesson is None or not _can_manage_class(db, user, lesson.class_id):
                raise HTTPException(403, "Bạn chưa được phân công duyệt minh chứng này")
    storage_name = request_row.evidence_ref.removeprefix("private:")
    if not re.fullmatch(r"[a-f0-9]{48}\.(?:pdf|jpg|jpeg|png)", storage_name):
        raise HTTPException(404, "Không tìm thấy minh chứng")
    target = ABSENCE_EVIDENCE_DIR / storage_name
    if not target.is_file():
        raise HTTPException(404, "Tệp minh chứng không còn tồn tại")
    return FileResponse(
        target,
        filename=f"minh-chung-{request_id}{target.suffix}",
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@m.app.post("/attendance/absence-requests/{request_id}/decision")
def decide_absence_request(request_id: int, user: m.Annotated[m.User, Depends(m.require_permission("attendance", "write"))], db: m.DbSession, payload: dict[str, Any]) -> dict[str, Any]:
    request_row = db.get(AbsenceRequest, request_id)
    if request_row is None:
        raise HTTPException(404, "Không tìm thấy yêu cầu vắng mặt")
    lesson = db.get(TrainingLesson, request_row.lesson_id)
    if lesson is None or not _can_manage_class(db, user, lesson.class_id):
        raise HTTPException(403, "Chỉ giảng viên hoặc trợ giảng được phân công mới có thể duyệt")
    decision = str(payload.get("decision", ""))
    reason = str(payload.get("reason", "")).strip()
    if decision not in {"approve", "reject"}:
        raise HTTPException(422, "decision phải là approve hoặc reject")
    if decision == "reject" and not reason:
        raise HTTPException(422, "Từ chối yêu cầu cần có lý do")
    if len(reason) > 1000:
        raise HTTPException(422, "Lý do xử lý tối đa 1000 ký tự")
    if request_row.status != "pending":
        raise HTTPException(409, "Yêu cầu đã được xử lý")
    request_row.status = "approved" if decision == "approve" else "rejected"
    request_row.decision_reason = reason or None
    request_row.decided_by = user.id
    request_row.decided_at = datetime.now(timezone.utc).replace(tzinfo=None)
    student = db.get(StudentProfile, request_row.student_id)
    if decision == "approve" and student:
        attendance = _upsert_attendance(db, lesson, student, user, "excused", reason or "Yêu cầu vắng mặt được duyệt")
    if student:
        _notice(db, student.user_id, "Kết quả yêu cầu vắng mặt", f"Yêu cầu của bạn đã {'được duyệt' if decision == 'approve' else 'bị từ chối'}. {reason}")
    db.commit()
    return {"id": request_row.id, "status": request_row.status, "decision_reason": request_row.decision_reason}


@m.app.get("/notifications")
def list_notifications(user: m.CurrentUser, db: m.DbSession, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)) -> dict[str, Any]:
    statement = select(InAppNotice).where(InAppNotice.user_id == user.id)
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    unread_count = db.scalar(select(func.count(InAppNotice.id)).where(
        InAppNotice.user_id == user.id, InAppNotice.read_at.is_(None)
    )) or 0
    rows = db.scalars(statement.order_by(InAppNotice.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [
        {"id": row.id, "title": row.title, "body": row.body,
         "created_at": row.created_at.isoformat(), "read_at": row.read_at.isoformat() if row.read_at else None}
        for row in rows
    ], "total": total, "unread_count": unread_count, "page": page, "page_size": page_size}
