"""Sprint 5 and 6 attendance-risk, assignment, grading and learning-material APIs."""

from __future__ import annotations

import json
import logging
import re
import secrets
import smtplib
from datetime import date, datetime, time, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, or_, select
from sqlalchemy.orm import Mapped, mapped_column

import main as m
import sprint34 as s34


MAX_UPLOAD_BYTES = 20 * 1024 * 1024
UPLOAD_ROOT = m.BACKEND_DIR / "uploads" / "learning"
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
ALLOWED_UPLOAD_SUFFIXES = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".zip", ".txt", ".png", ".jpg", ".jpeg"}
logger = logging.getLogger(__name__)


class AttendancePolicy(m.Base):
    __tablename__ = "attendance_policies"

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("training_programs.id", ondelete="CASCADE"), unique=True)
    absence_threshold_percent: Mapped[int] = mapped_column(Integer, default=20)


class Assignment(m.Base):
    __tablename__ = "training_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("training_classes.id", ondelete="CASCADE"), index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("training_subjects.id", ondelete="RESTRICT"), index=True)
    lesson_id: Mapped[int | None] = mapped_column(ForeignKey("training_lessons.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    due_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    max_score: Mapped[float] = mapped_column(default=10)
    state: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    late_policy: Mapped[str] = mapped_column(String(20), default="accept")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class AssignmentAttachment(m.Base):
    __tablename__ = "assignment_attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("training_assignments.id", ondelete="CASCADE"), index=True)
    storage_name: Mapped[str] = mapped_column(String(100), unique=True)
    display_name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class AssignmentSubmission(m.Base):
    __tablename__ = "assignment_submissions"
    __table_args__ = (UniqueConstraint("assignment_id", "student_id", name="uq_assignment_student"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("training_assignments.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id", ondelete="RESTRICT"), index=True)
    state: Mapped[str] = mapped_column(String(20), default="submitted", index=True)
    current_version: Mapped[int] = mapped_column(Integer, default=0)
    published_score: Mapped[float | None] = mapped_column(nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class SubmissionVersion(m.Base):
    __tablename__ = "assignment_submission_versions"
    __table_args__ = (UniqueConstraint("submission_id", "version_number", name="uq_submission_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("assignment_submissions.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    repo_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    files_json: Mapped[str] = mapped_column(Text, default="[]")
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    is_late: Mapped[bool] = mapped_column(default=False)


class RubricTemplate(m.Base):
    __tablename__ = "rubric_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    criteria_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class SubmissionGrade(m.Base):
    __tablename__ = "submission_grades"
    __table_args__ = (UniqueConstraint("submission_id", "version_number", name="uq_submission_grade_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("assignment_submissions.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column()
    feedback: Mapped[str] = mapped_column(Text, default="")
    criteria_json: Mapped[str] = mapped_column(Text, default="[]")
    graded_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class GradeAudit(m.Base):
    __tablename__ = "grade_audits"

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("assignment_submissions.id", ondelete="CASCADE"), index=True)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    action: Mapped[str] = mapped_column(String(30))
    detail: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class LearningMaterial(m.Base):
    __tablename__ = "learning_materials"

    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("training_classes.id", ondelete="CASCADE"), index=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("training_lessons.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    storage_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    available_early: Mapped[bool] = mapped_column(default=False)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class ClassAnnouncement(m.Base):
    __tablename__ = "class_announcements"

    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("training_classes.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class AnnouncementRead(m.Base):
    __tablename__ = "announcement_reads"
    __table_args__ = (UniqueConstraint("announcement_id", "user_id", name="uq_announcement_user_read"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    announcement_id: Mapped[int] = mapped_column(ForeignKey("class_announcements.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    read_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class AttendancePolicyInput(BaseModel):
    absence_threshold_percent: int = Field(ge=1, le=100)


class AssignmentInput(BaseModel):
    class_id: int
    subject_id: int
    lesson_id: int | None = None
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=12000)
    due_at: datetime
    max_score: float = Field(gt=0, le=1000)
    state: str = Field(default="draft", pattern="^(draft|published)$")
    late_policy: str = Field(default="accept", pattern="^(accept|block)$")


class GradeInput(BaseModel):
    score: float = Field(ge=0)
    feedback: str = Field(default="", max_length=12000)
    criteria: list[dict[str, Any]] = Field(default_factory=list, max_length=50)


class RubricInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    criteria: list[dict[str, Any]] = Field(min_length=1, max_length=50)


def _need(user: m.User, db: m.Session, module: str, action: str) -> None:
    if not m.permission_allows(m.assigned_roles(db, user), module, action):
        raise HTTPException(403, "Bạn không có quyền truy cập chức năng này")


def _student_for_user(db: m.Session, user: m.User) -> s34.StudentProfile:
    student = db.scalar(select(s34.StudentProfile).where(s34.StudentProfile.user_id == user.id))
    if student is None:
        raise HTTPException(403, "Không tìm thấy hồ sơ học viên của tài khoản")
    return student


def _class_access(db: m.Session, user: m.User, class_id: int, module: str, action: str) -> bool:
    if m.permission_allows(m.assigned_roles(db, user), module, "full"):
        return True
    if module == "attendance" and action == "read" and m.permission_allows(m.assigned_roles(db, user), module, "read"):
        return s34._can_manage_class(db, user, class_id)
    return s34._can_manage_class(db, user, class_id)


def _json_material(db: m.Session, item: LearningMaterial, for_student: bool = False) -> dict[str, Any]:
    lesson = db.get(s34.TrainingLesson, item.lesson_id)
    if for_student and lesson and lesson.ends_at > datetime.now() and not item.available_early:
        raise HTTPException(403, "Tài liệu chỉ mở sau khi buổi học diễn ra")
    return {
        "id": item.id, "class_id": item.class_id, "lesson_id": item.lesson_id,
        "lesson_title": lesson.title if lesson else "", "title": item.title,
        "file_name": item.display_name, "external_url": item.external_url,
        "available_early": item.available_early, "created_at": item.created_at.isoformat(),
    }


async def _save_upload(file: UploadFile) -> tuple[str, str]:
    name = Path(file.filename or "upload").name[:255]
    if Path(name).suffix.lower() not in ALLOWED_UPLOAD_SUFFIXES:
        raise HTTPException(415, "Định dạng tệp này chưa được hỗ trợ")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Tệp phải có dung lượng từ 1 byte đến 20MB")
    storage_name = secrets.token_hex(20) + Path(name).suffix.lower()
    (UPLOAD_ROOT / storage_name).write_bytes(data)
    return storage_name, name


def _assignment_json(db: m.Session, assignment: Assignment, student_id: int | None = None) -> dict[str, Any]:
    attachments = db.scalars(select(AssignmentAttachment).where(AssignmentAttachment.assignment_id == assignment.id)).all()
    data: dict[str, Any] = {
        "id": assignment.id, "class_id": assignment.class_id, "subject_id": assignment.subject_id,
        "lesson_id": assignment.lesson_id, "title": assignment.title, "description": assignment.description,
        "due_at": assignment.due_at.isoformat(), "max_score": assignment.max_score, "state": assignment.state,
        "late_policy": assignment.late_policy,
        "attachments": [{"id": x.id, "file_name": x.display_name} for x in attachments],
    }
    if student_id is not None:
        submission = db.scalar(select(AssignmentSubmission).where(
            AssignmentSubmission.assignment_id == assignment.id,
            AssignmentSubmission.student_id == student_id,
        ))
        data["submission"] = _submission_json(db, submission, include_private=False) if submission else None
    return data


def _submission_json(db: m.Session, submission: AssignmentSubmission, include_private: bool) -> dict[str, Any]:
    versions = db.scalars(select(SubmissionVersion).where(
        SubmissionVersion.submission_id == submission.id
    ).order_by(SubmissionVersion.version_number.desc())).all()
    data: dict[str, Any] = {
        "id": submission.id, "assignment_id": submission.assignment_id, "student_id": submission.student_id,
        "state": submission.state, "current_version": submission.current_version,
        "versions": [{
            "id": v.id, "version_number": v.version_number, "repo_url": v.repo_url,
            "files": json.loads(v.files_json), "submitted_at": v.submitted_at.isoformat(), "is_late": v.is_late,
        } for v in versions],
    }
    if include_private:
        grade = db.scalar(select(SubmissionGrade).where(
            SubmissionGrade.submission_id == submission.id,
            SubmissionGrade.version_number == submission.current_version,
        ))
        data["grade"] = ({
            "score": grade.score, "feedback": grade.feedback,
            "criteria": json.loads(grade.criteria_json), "published": grade.published_at is not None,
        } if grade and grade.published_at else None)
    else:
        data["grade"] = None
    return data


@m.app.get("/attendance/policies")
def list_attendance_policies(user: m.CurrentUser, db: m.DbSession) -> list[dict[str, Any]]:
    _need(user, db, "attendance", "read")
    programs = db.scalars(select(m.TrainingProgram).order_by(m.TrainingProgram.name)).all()
    rows = {row.program_id: row for row in db.scalars(select(AttendancePolicy)).all()}
    return [{"program_id": p.id, "program_name": p.name,
             "absence_threshold_percent": rows[p.id].absence_threshold_percent if p.id in rows else 20}
            for p in programs]


@m.app.put("/attendance/policies/{program_id}")
def set_attendance_policy(program_id: int, payload: AttendancePolicyInput,
                          user: m.Annotated[m.User, Depends(m.require_permission("attendance", "full"))],
                          db: m.DbSession) -> dict[str, Any]:
    if db.get(m.TrainingProgram, program_id) is None:
        raise HTTPException(404, "Không tìm thấy chương trình")
    row = db.scalar(select(AttendancePolicy).where(AttendancePolicy.program_id == program_id))
    if row is None:
        row = AttendancePolicy(program_id=program_id, absence_threshold_percent=payload.absence_threshold_percent)
        db.add(row)
    else:
        row.absence_threshold_percent = payload.absence_threshold_percent
    db.commit()
    return {"program_id": program_id, "absence_threshold_percent": row.absence_threshold_percent}


@m.app.get("/attendance/classes/{class_id}/summary")
def attendance_summary(class_id: int, user: m.CurrentUser, db: m.DbSession) -> dict[str, Any]:
    if not _class_access(db, user, class_id, "attendance", "read"):
        raise HTTPException(403, "Bạn chưa được phân công vào lớp này")
    training_class = db.get(m.TrainingClass, class_id)
    if training_class is None:
        raise HTTPException(404, "Không tìm thấy lớp")
    lessons = db.scalars(select(s34.TrainingLesson).where(
        s34.TrainingLesson.class_id == class_id, s34.TrainingLesson.status == "scheduled",
        s34.TrainingLesson.ends_at <= datetime.now(),
    ).order_by(s34.TrainingLesson.starts_at)).all()
    enrollments = db.scalars(select(s34.StudentEnrollment).where(
        s34.StudentEnrollment.class_id == class_id, s34.StudentEnrollment.status == "active",
    )).all()
    students = {en.student_id: db.get(s34.StudentProfile, en.student_id) for en in enrollments}
    student_ids = set(students)
    attendance_rows = db.scalars(select(s34.Attendance).where(
        s34.Attendance.lesson_id.in_([lesson.id for lesson in lessons] or [-1]),
        s34.Attendance.student_id.in_(student_ids or {-1}),
    )).all()
    attendance = {(row.lesson_id, row.student_id): row.status for row in attendance_rows}
    cfg = db.scalar(select(AttendancePolicy).where(AttendancePolicy.program_id == training_class.program_id))
    threshold = cfg.absence_threshold_percent if cfg else 20
    items = []
    risk_ids: set[int] = set()
    for student_id, student in students.items():
        if student is None:
            continue
        statuses = [attendance.get((lesson.id, student_id)) for lesson in lessons]
        absent = sum(value in {"unexcused", "excused"} for value in statuses)
        unexcused = sum(value == "unexcused" for value in statuses)
        pct = round(absent * 100 / len(lessons), 1) if lessons else 0.0
        risk = bool(lessons and pct >= threshold)
        if risk:
            risk_ids.add(student_id)
        items.append({
            "student_id": student_id, "student_code": student.student_code, "student_name": student.full_name,
            "statuses": statuses, "absence_count": absent, "unexcused_count": unexcused,
            "attendance_percent": round(100 - pct, 1), "absence_percent": pct,
            "threshold_percent": threshold, "at_risk": risk,
        })
    return {"class_id": class_id, "class_name": training_class.name, "lessons": [
        {"id": lesson.id, "title": lesson.title, "starts_at": lesson.starts_at.isoformat()}
        for lesson in lessons
    ], "threshold_percent": threshold, "items": items}


@m.app.get("/attendance/classes/{class_id}/summary.xlsx")
def export_attendance_summary(class_id: int, user: m.CurrentUser, db: m.DbSession) -> StreamingResponse:
    summary = attendance_summary(class_id, user, db)
    workbook = m.Workbook()
    sheet = workbook.active
    sheet.title = "Chuyên cần"
    sheet.append(["Mã học viên", "Họ tên", *[f"{i + 1}. {lesson['title']}" for i, lesson in enumerate(summary["lessons"])], "Vắng", "Vắng không phép", "Chuyên cần %", "Cảnh báo"])
    for row in summary["items"]:
        sheet.append([row["student_code"], row["student_name"], *[
            {"present": "Có mặt", "late": "Đi muộn", "excused": "Vắng có phép", "unexcused": "Vắng không phép"}.get(value, "Chưa điểm danh")
            for value in row["statuses"]
        ], row["absence_count"], row["unexcused_count"], row["attendance_percent"], "Có" if row["at_risk"] else "Không"])
    output = m.BytesIO()
    workbook.save(output)
    output.seek(0)
    filename = f"attendance-class-{class_id}-{date.today().isoformat()}.xlsx"
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@m.app.get("/assignments")
def list_assignments(user: m.CurrentUser, db: m.DbSession, class_id: int | None = None,
                     state: str | None = None) -> list[dict[str, Any]]:
    roles = m.assigned_roles(db, user)
    statement = select(Assignment)
    student_id: int | None = None
    if "student" in roles and not m.permission_allows(roles, "assignments", "full"):
        student = _student_for_user(db, user)
        student_id = student.id
        active_classes = select(s34.StudentEnrollment.class_id).where(
            s34.StudentEnrollment.student_id == student.id,
            s34.StudentEnrollment.status == "active",
            s34.StudentEnrollment.effective_from <= date.today(),
            or_(s34.StudentEnrollment.effective_to.is_(None), s34.StudentEnrollment.effective_to > date.today()),
        )
        statement = statement.where(Assignment.class_id.in_(active_classes), Assignment.state == "published")
    elif not m.permission_allows(roles, "assignments", "full"):
        assigned = select(s34.ClassSubject.class_id).outerjoin(s34.ClassSubjectTA, s34.ClassSubjectTA.class_subject_id == s34.ClassSubject.id).where(
            or_(s34.ClassSubject.instructor_id == user.id, s34.ClassSubjectTA.user_id == user.id))
        statement = statement.where(Assignment.class_id.in_(assigned))
    if class_id is not None:
        statement = statement.where(Assignment.class_id == class_id)
    if state:
        if state not in {"draft", "published"}:
            raise HTTPException(422, "Trạng thái bài tập không hợp lệ")
        statement = statement.where(Assignment.state == state)
    rows = db.scalars(statement.order_by(Assignment.due_at.desc()).limit(300)).all()
    return [_assignment_json(db, item, student_id) for item in rows]


@m.app.post("/assignments", status_code=201)
def create_assignment(payload: AssignmentInput,
                      user: m.Annotated[m.User, Depends(m.require_permission("assignments", "write"))],
                      db: m.DbSession) -> dict[str, Any]:
    if not _class_access(db, user, payload.class_id, "assignments", "write"):
        raise HTTPException(403, "Bạn chưa được phân công vào lớp này")
    if db.scalar(select(s34.ClassSubject.id).where(s34.ClassSubject.class_id == payload.class_id, s34.ClassSubject.subject_id == payload.subject_id)) is None:
        raise HTTPException(422, "Môn học không thuộc lớp đã chọn")
    if payload.lesson_id and (db.get(s34.TrainingLesson, payload.lesson_id) is None or db.get(s34.TrainingLesson, payload.lesson_id).class_id != payload.class_id):
        raise HTTPException(422, "Buổi học không thuộc lớp đã chọn")
    if payload.state == "published" and payload.due_at.replace(tzinfo=None) < datetime.now():
        raise HTTPException(422, "Hạn nộp không được ở quá khứ")
    row = Assignment(**payload.model_dump(), due_at=payload.due_at.replace(tzinfo=None), created_by=user.id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _assignment_json(db, row)


@m.app.patch("/assignments/{assignment_id}")
def update_assignment(assignment_id: int, payload: AssignmentInput,
                      user: m.Annotated[m.User, Depends(m.require_permission("assignments", "write"))],
                      db: m.DbSession) -> dict[str, Any]:
    row = db.get(Assignment, assignment_id)
    if row is None:
        raise HTTPException(404, "Không tìm thấy bài tập")
    if not _class_access(db, user, row.class_id, "assignments", "write"):
        raise HTTPException(403, "Bạn chưa được phân công vào lớp này")
    if row.state == "published" and db.scalar(select(AssignmentSubmission.id).where(AssignmentSubmission.assignment_id == row.id).limit(1)):
        if payload.class_id != row.class_id or payload.subject_id != row.subject_id:
            raise HTTPException(409, "Không đổi lớp hoặc môn sau khi đã có bài nộp")
    for key, value in payload.model_dump().items():
        setattr(row, key, value.replace(tzinfo=None) if key == "due_at" else value)
    row.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return _assignment_json(db, row)


@m.app.post("/assignments/{assignment_id}/attachments", status_code=201)
async def add_assignment_attachment(assignment_id: int, user: m.Annotated[m.User, Depends(m.require_permission("assignments", "write"))],
                                    db: m.DbSession, file: UploadFile = File(...)) -> dict[str, Any]:
    assignment = db.get(Assignment, assignment_id)
    if assignment is None:
        raise HTTPException(404, "Không tìm thấy bài tập")
    if assignment.state != "draft" or not _class_access(db, user, assignment.class_id, "assignments", "write"):
        raise HTTPException(403, "Chỉ được đính kèm tệp cho bài nháp của lớp được phân công")
    storage_name, display_name = await _save_upload(file)
    row = AssignmentAttachment(assignment_id=assignment.id, storage_name=storage_name, display_name=display_name)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "file_name": display_name}


@m.app.get("/assignments/{assignment_id}/submissions")
def list_submissions(assignment_id: int, user: m.CurrentUser, db: m.DbSession) -> list[dict[str, Any]]:
    _need(user, db, "assignments", "write")
    assignment = db.get(Assignment, assignment_id)
    if assignment is None:
        raise HTTPException(404, "Không tìm thấy bài tập")
    if not _class_access(db, user, assignment.class_id, "assignments", "write"):
        raise HTTPException(403, "Bạn chưa được phân công vào lớp này")
    roster = s34._student_roster(db, assignment.class_id, date.today())
    output = []
    for student in roster:
        submission = db.scalar(select(AssignmentSubmission).where(
            AssignmentSubmission.assignment_id == assignment.id, AssignmentSubmission.student_id == student.id))
        output.append({"student_id": student.id, "student_code": student.student_code,
            "student_name": student.full_name, "submission": _submission_json(db, submission, True) if submission else None})
    return output


@m.app.post("/assignments/{assignment_id}/submissions", status_code=201)
async def submit_assignment(assignment_id: int, user: m.Annotated[m.User, Depends(m.require_permission("assignments", "write"))],
                            db: m.DbSession, repo_url: str | None = None,
                            files: list[UploadFile] = File(default=[])) -> dict[str, Any]:
    assignment = db.get(Assignment, assignment_id)
    if assignment is None or assignment.state != "published":
        raise HTTPException(404, "Không tìm thấy bài tập đang được giao")
    student = _student_for_user(db, user)
    if db.scalar(select(s34.StudentEnrollment.id).where(
        s34.StudentEnrollment.student_id == student.id, s34.StudentEnrollment.class_id == assignment.class_id,
        s34.StudentEnrollment.status == "active", s34.StudentEnrollment.effective_from <= date.today(),
        or_(s34.StudentEnrollment.effective_to.is_(None), s34.StudentEnrollment.effective_to > date.today()))) is None:
        raise HTTPException(403, "Bài tập không thuộc lớp bạn đang theo học")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    is_late = now > assignment.due_at
    if is_late and assignment.late_policy == "block":
        raise HTTPException(409, "Bài tập không chấp nhận nộp muộn")
    normalized_repo = repo_url.strip() if repo_url else None
    if normalized_repo:
        parsed = urlparse(normalized_repo)
        if parsed.scheme != "https" or not parsed.netloc or len(normalized_repo) > 1000:
            raise HTTPException(422, "Liên kết mã nguồn phải là URL HTTPS hợp lệ")
    existing = db.scalar(select(AssignmentSubmission).where(
        AssignmentSubmission.assignment_id == assignment.id, AssignmentSubmission.student_id == student.id))
    if existing and existing.state == "graded":
        raise HTTPException(409, "Bài đã chấm xong; cần giảng viên mở lại trước khi nộp lại")
    if existing and existing.state == "needs_revision" and assignment.due_at < now:
        raise HTTPException(409, "Đã hết hạn nộp lại bài")
    if not files and not normalized_repo:
        raise HTTPException(422, "Đính kèm ít nhất một tệp hoặc liên kết repo")
    if len(files) > 10:
        raise HTTPException(422, "Mỗi lần nộp tối đa 10 tệp")
    stored: list[dict[str, str]] = []
    try:
        for file in files:
            storage, display = await _save_upload(file)
            stored.append({"storage_name": storage, "file_name": display})
    except Exception:
        for item in stored:
            (UPLOAD_ROOT / item["storage_name"]).unlink(missing_ok=True)
        raise
    if existing is None:
        existing = AssignmentSubmission(assignment_id=assignment.id, student_id=student.id)
        db.add(existing)
        db.flush()
    version_number = existing.current_version + 1
    existing.current_version = version_number
    existing.state = "submitted"
    existing.published_score = None
    existing.published_at = None
    db.add(SubmissionVersion(submission_id=existing.id, version_number=version_number,
        repo_url=normalized_repo, files_json=json.dumps(stored), submitted_at=now, is_late=is_late))
    db.commit()
    db.refresh(existing)
    return _submission_json(db, existing, False)


@m.app.get("/submissions/files/{storage_name}")
def download_submission_file(storage_name: str, user: m.CurrentUser, db: m.DbSession) -> FileResponse:
    if not re.fullmatch(r"[a-f0-9]{40}\.[a-z0-9]{1,8}", storage_name):
        raise HTTPException(404, "Không tìm thấy tệp")
    for version in db.scalars(select(SubmissionVersion)).all():
        for item in json.loads(version.files_json):
            if item.get("storage_name") != storage_name:
                continue
            submission = db.get(AssignmentSubmission, version.submission_id)
            assignment = db.get(Assignment, submission.assignment_id) if submission else None
            student = db.get(s34.StudentProfile, submission.student_id) if submission else None
            if assignment is None or student is None:
                break
            visible = student.user_id == user.id or (m.permission_allows(m.assigned_roles(db, user), "assignments", "write") and s34._can_manage_class(db, user, assignment.class_id))
            if not visible:
                raise HTTPException(403, "Bạn không có quyền xem tệp này")
            path = UPLOAD_ROOT / storage_name
            if not path.is_file():
                raise HTTPException(404, "Tệp không còn tồn tại")
            return FileResponse(path, filename=item["file_name"])
    raise HTTPException(404, "Không tìm thấy tệp")


@m.app.post("/assignments/{assignment_id}/submissions/{submission_id}/grade")
def grade_submission(assignment_id: int, submission_id: int, payload: GradeInput,
                     user: m.Annotated[m.User, Depends(m.require_permission("assignments", "write"))],
                     db: m.DbSession) -> dict[str, Any]:
    assignment = db.get(Assignment, assignment_id)
    submission = db.get(AssignmentSubmission, submission_id)
    if assignment is None or submission is None or submission.assignment_id != assignment_id:
        raise HTTPException(404, "Không tìm thấy bài nộp")
    if not _class_access(db, user, assignment.class_id, "assignments", "write"):
        raise HTTPException(403, "Bạn chưa được phân công vào lớp này")
    if payload.score > assignment.max_score:
        raise HTTPException(422, "Điểm không được vượt quá điểm tối đa")
    for criterion in payload.criteria:
        if not isinstance(criterion.get("name"), str) or not criterion["name"].strip() or not isinstance(criterion.get("score"), (int, float)) or criterion["score"] < 0:
            raise HTTPException(422, "Tiêu chí rubric cần tên và điểm không âm")
    if sum(float(item["score"]) for item in payload.criteria) > assignment.max_score:
        raise HTTPException(422, "Tổng điểm rubric không được vượt điểm tối đa")
    grade = db.scalar(select(SubmissionGrade).where(
        SubmissionGrade.submission_id == submission.id, SubmissionGrade.version_number == submission.current_version))
    previous = {"score": grade.score, "feedback": grade.feedback} if grade else None
    if grade is None:
        grade = SubmissionGrade(submission_id=submission.id, version_number=submission.current_version,
            score=payload.score, feedback=payload.feedback, criteria_json=json.dumps(payload.criteria, ensure_ascii=False), graded_by=user.id)
        db.add(grade)
    else:
        grade.score = payload.score
        grade.feedback = payload.feedback
        grade.criteria_json = json.dumps(payload.criteria, ensure_ascii=False)
        grade.graded_by = user.id
    submission.published_score = payload.score if grade.published_at else None
    submission.state = "graded"
    db.add(GradeAudit(submission_id=submission.id, actor_user_id=user.id, action="graded",
        detail=json.dumps({"before": previous, "after": payload.model_dump()}, ensure_ascii=False)))
    db.commit()
    return {"submission_id": submission.id, "state": submission.state, "published": grade.published_at is not None}


@m.app.post("/assignments/{assignment_id}/submissions/{submission_id}/publish")
def publish_grade(assignment_id: int, submission_id: int,
                  user: m.Annotated[m.User, Depends(m.require_permission("assignments", "write"))],
                  db: m.DbSession) -> dict[str, Any]:
    assignment = db.get(Assignment, assignment_id)
    submission = db.get(AssignmentSubmission, submission_id)
    if assignment is None or submission is None or submission.assignment_id != assignment_id:
        raise HTTPException(404, "Không tìm thấy bài nộp")
    if not _class_access(db, user, assignment.class_id, "assignments", "write"):
        raise HTTPException(403, "Bạn chưa được phân công vào lớp này")
    grade = db.scalar(select(SubmissionGrade).where(
        SubmissionGrade.submission_id == submission.id, SubmissionGrade.version_number == submission.current_version))
    if grade is None:
        raise HTTPException(409, "Cần chấm điểm trước khi công bố")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    grade.published_at = now
    submission.published_score = grade.score
    submission.published_at = now
    student = db.get(s34.StudentProfile, submission.student_id)
    if student:
        s34._notice(db, student.user_id, "Điểm bài tập đã được công bố", f"{assignment.title}: {grade.score:g}/{assignment.max_score:g}")
    db.add(GradeAudit(submission_id=submission.id, actor_user_id=user.id, action="published", detail=f"version={submission.current_version};score={grade.score}"))
    db.commit()
    return {"submission_id": submission.id, "published_at": now.isoformat()}


@m.app.post("/assignments/{assignment_id}/submissions/{submission_id}/revision")
def request_revision(assignment_id: int, submission_id: int, payload: dict[str, Any],
                     user: m.Annotated[m.User, Depends(m.require_permission("assignments", "write"))],
                     db: m.DbSession) -> dict[str, Any]:
    assignment = db.get(Assignment, assignment_id)
    submission = db.get(AssignmentSubmission, submission_id)
    if assignment is None or submission is None or submission.assignment_id != assignment_id:
        raise HTTPException(404, "Không tìm thấy bài nộp")
    if not _class_access(db, user, assignment.class_id, "assignments", "write"):
        raise HTTPException(403, "Bạn chưa được phân công vào lớp này")
    feedback = str(payload.get("feedback", "")).strip()
    try:
        due_at = datetime.fromisoformat(str(payload.get("due_at", "")).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError as error:
        raise HTTPException(422, "Hạn nộp lại không hợp lệ") from error
    if not feedback or len(feedback) > 12000 or due_at <= datetime.now():
        raise HTTPException(422, "Nhận xét bắt buộc và hạn nộp lại phải ở tương lai")
    submission.state = "needs_revision"
    assignment.due_at = due_at
    grade = db.scalar(select(SubmissionGrade).where(
        SubmissionGrade.submission_id == submission.id, SubmissionGrade.version_number == submission.current_version))
    if grade:
        grade.feedback = feedback
    else:
        grade = SubmissionGrade(submission_id=submission.id, version_number=submission.current_version,
            score=0, feedback=feedback, graded_by=user.id)
        db.add(grade)
    student = db.get(s34.StudentProfile, submission.student_id)
    if student:
        s34._notice(db, student.user_id, "Bài tập cần làm lại", f"{assignment.title}: {feedback}")
    db.add(GradeAudit(submission_id=submission.id, actor_user_id=user.id, action="revision", detail=feedback))
    db.commit()
    return {"submission_id": submission.id, "state": submission.state, "due_at": due_at.isoformat()}


@m.app.post("/rubrics", status_code=201)
def create_rubric(payload: RubricInput, user: m.Annotated[m.User, Depends(m.require_permission("assignments", "write"))],
                   db: m.DbSession) -> dict[str, Any]:
    total = sum(float(item.get("weight", 0)) for item in payload.criteria)
    if any(not str(item.get("name", "")).strip() or float(item.get("weight", 0)) <= 0 for item in payload.criteria) or abs(total - 100) > 0.01:
        raise HTTPException(422, "Rubric cần tiêu chí có trọng số dương, tổng trọng số bằng 100%")
    row = RubricTemplate(owner_user_id=user.id, name=payload.name, criteria_json=json.dumps(payload.criteria, ensure_ascii=False))
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "name": row.name, "criteria": json.loads(row.criteria_json)}


@m.app.get("/rubrics")
def list_rubrics(user: m.Annotated[m.User, Depends(m.require_permission("assignments", "read"))],
                 db: m.DbSession) -> list[dict[str, Any]]:
    return [{"id": row.id, "name": row.name, "criteria": json.loads(row.criteria_json)}
        for row in db.scalars(select(RubricTemplate).where(RubricTemplate.owner_user_id == user.id).order_by(RubricTemplate.name)).all()]


@m.app.get("/materials")
def list_materials(user: m.CurrentUser, db: m.DbSession, class_id: int | None = None) -> list[dict[str, Any]]:
    roles = m.assigned_roles(db, user)
    student_id: int | None = None
    if "student" in roles and not m.permission_allows(roles, "materials", "write"):
        student = _student_for_user(db, user)
        student_id = student.id
        classes = select(s34.StudentEnrollment.class_id).where(
            s34.StudentEnrollment.student_id == student.id, s34.StudentEnrollment.status == "active",
            s34.StudentEnrollment.effective_from <= date.today(),
            or_(s34.StudentEnrollment.effective_to.is_(None), s34.StudentEnrollment.effective_to > date.today()))
        statement = select(LearningMaterial).where(LearningMaterial.class_id.in_(classes))
    else:
        _need(user, db, "materials", "read")
        statement = select(LearningMaterial)
        if not m.permission_allows(roles, "materials", "full"):
            classes = select(s34.ClassSubject.class_id).outerjoin(s34.ClassSubjectTA, s34.ClassSubjectTA.class_subject_id == s34.ClassSubject.id).where(
                or_(s34.ClassSubject.instructor_id == user.id, s34.ClassSubjectTA.user_id == user.id))
            statement = statement.where(LearningMaterial.class_id.in_(classes))
    if class_id:
        statement = statement.where(LearningMaterial.class_id == class_id)
    return [_json_material(db, row, bool(student_id)) for row in db.scalars(statement.order_by(LearningMaterial.created_at.desc()).limit(300)).all()]


@m.app.post("/materials", status_code=201)
async def create_material(user: m.Annotated[m.User, Depends(m.require_permission("materials", "write"))],
                          db: m.DbSession, class_id: int, lesson_id: int, title: str,
                          available_early: bool = False, external_url: str | None = None,
                          file: UploadFile | None = File(default=None)) -> dict[str, Any]:
    lesson = db.get(s34.TrainingLesson, lesson_id)
    if lesson is None or lesson.class_id != class_id:
        raise HTTPException(422, "Buổi học không thuộc lớp đã chọn")
    if not _class_access(db, user, class_id, "materials", "write"):
        raise HTTPException(403, "Bạn chưa được phân công vào lớp này")
    url = external_url.strip() if external_url else None
    if url and (urlparse(url).scheme != "https" or not urlparse(url).netloc):
        raise HTTPException(422, "Liên kết ngoài phải là URL HTTPS")
    if not title.strip() or len(title) > 200 or not (file or url):
        raise HTTPException(422, "Cần tiêu đề và tệp hoặc liên kết tài liệu")
    storage = display = None
    if file:
        storage, display = await _save_upload(file)
    row = LearningMaterial(class_id=class_id, lesson_id=lesson_id, title=title.strip(),
        storage_name=storage, display_name=display, external_url=url, available_early=available_early, uploaded_by=user.id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _json_material(db, row)


@m.app.get("/materials/{material_id}/file")
def download_material(material_id: int, user: m.CurrentUser, db: m.DbSession) -> FileResponse:
    row = db.get(LearningMaterial, material_id)
    if row is None or not row.storage_name:
        raise HTTPException(404, "Không tìm thấy tệp học liệu")
    student_id = db.scalar(select(s34.StudentProfile.id).where(s34.StudentProfile.user_id == user.id))
    if student_id is not None:
        if db.scalar(select(s34.StudentEnrollment.id).where(
            s34.StudentEnrollment.student_id == student_id, s34.StudentEnrollment.class_id == row.class_id,
            s34.StudentEnrollment.status == "active")) is None:
            raise HTTPException(403, "Học liệu không thuộc lớp của bạn")
        _json_material(db, row, True)
    elif not _class_access(db, user, row.class_id, "materials", "read"):
        raise HTTPException(403, "Bạn không có quyền xem học liệu này")
    path = UPLOAD_ROOT / row.storage_name
    if not path.is_file():
        raise HTTPException(404, "Tệp học liệu không còn tồn tại")
    return FileResponse(path, filename=row.display_name or row.title)


@m.app.post("/announcements", status_code=201)
def create_announcement(user: m.Annotated[m.User, Depends(m.require_permission("materials", "full"))],
                        db: m.DbSession, payload: dict[str, Any]) -> dict[str, Any]:
    title, body = str(payload.get("title", "")).strip(), str(payload.get("body", "")).strip()
    class_ids = payload.get("class_ids")
    if not title or len(title) > 200 or not body or len(body) > 12000 or not isinstance(class_ids, list) or not class_ids or len(class_ids) > 100:
        raise HTTPException(422, "Cần tiêu đề, nội dung và ít nhất một lớp hợp lệ")
    if any(not isinstance(item, int) for item in class_ids) or len(set(class_ids)) != len(class_ids):
        raise HTTPException(422, "Danh sách lớp không hợp lệ hoặc bị trùng")
    announcements = []
    recipients: dict[int, str] = {}
    for class_id in class_ids:
        if db.get(m.TrainingClass, class_id) is None:
            raise HTTPException(422, f"Không tìm thấy lớp {class_id}")
        row = ClassAnnouncement(class_id=class_id, title=title, body=body, created_by=user.id)
        db.add(row)
        db.flush()
        enrollments = db.scalars(select(s34.StudentEnrollment).where(
            s34.StudentEnrollment.class_id == class_id, s34.StudentEnrollment.status == "active",
            s34.StudentEnrollment.effective_to.is_(None))).all()
        for enrollment in enrollments:
            student = db.get(s34.StudentProfile, enrollment.student_id)
            if student:
                s34._notice(db, student.user_id, title, body)
                recipients[student.user_id] = student.email
        announcements.append(row)
    db.commit()
    email_sent = 0
    email_failed = 0
    email_skipped = 0
    if m.smtp_configured():
        for email in recipients.values():
            message = EmailMessage()
            message["To"] = email
            message["Subject"] = title
            message["From"] = m.SMTP_FROM
            message.set_content(body)
            try:
                if m.send_email(message):
                    email_sent += 1
                else:
                    email_failed += 1
            except (OSError, smtplib.SMTPException):
                logger.exception("Class announcement email delivery failed")
                email_failed += 1
    else:
        email_skipped = len(recipients)
    return {"items": [{"id": row.id, "class_id": row.class_id, "title": row.title} for row in announcements],
        "emails_sent": email_sent, "emails_failed": email_failed, "emails_skipped": email_skipped}


@m.app.get("/announcements")
def list_announcements(user: m.CurrentUser, db: m.DbSession, class_id: int | None = None) -> list[dict[str, Any]]:
    student_id = db.scalar(select(s34.StudentProfile.id).where(s34.StudentProfile.user_id == user.id))
    statement = select(ClassAnnouncement)
    if student_id:
        statement = statement.join(s34.StudentEnrollment, s34.StudentEnrollment.class_id == ClassAnnouncement.class_id).where(
            s34.StudentEnrollment.student_id == student_id, s34.StudentEnrollment.status == "active")
    elif not m.permission_allows(m.assigned_roles(db, user), "materials", "full"):
        assigned = select(s34.ClassSubject.class_id).outerjoin(s34.ClassSubjectTA, s34.ClassSubjectTA.class_subject_id == s34.ClassSubject.id).where(
            or_(s34.ClassSubject.instructor_id == user.id, s34.ClassSubjectTA.user_id == user.id))
        statement = statement.where(ClassAnnouncement.class_id.in_(assigned))
    if class_id:
        statement = statement.where(ClassAnnouncement.class_id == class_id)
    rows = db.scalars(statement.order_by(ClassAnnouncement.created_at.desc()).limit(300)).all()
    return [{"id": row.id, "class_id": row.class_id, "title": row.title, "body": row.body,
        "created_at": row.created_at.isoformat(),
        "read": db.scalar(select(AnnouncementRead.id).where(AnnouncementRead.announcement_id == row.id, AnnouncementRead.user_id == user.id)) is not None}
        for row in rows]


@m.app.post("/announcements/{announcement_id}/read")
def mark_announcement_read(announcement_id: int, user: m.CurrentUser, db: m.DbSession) -> dict[str, Any]:
    row = db.get(ClassAnnouncement, announcement_id)
    if row is None:
        raise HTTPException(404, "Không tìm thấy thông báo lớp")
    visible = list_announcements(user, db, row.class_id)
    if not any(item["id"] == row.id for item in visible):
        raise HTTPException(403, "Bạn không có quyền xem thông báo này")
    existing = db.scalar(select(AnnouncementRead).where(AnnouncementRead.announcement_id == row.id, AnnouncementRead.user_id == user.id))
    if existing is None:
        db.add(AnnouncementRead(announcement_id=row.id, user_id=user.id))
        db.commit()
    return {"id": row.id, "read": True}


@m.app.post("/notifications/read-all")
def mark_all_notifications_read(user: m.CurrentUser, db: m.DbSession) -> dict[str, int]:
    rows = db.scalars(select(s34.InAppNotice).where(s34.InAppNotice.user_id == user.id, s34.InAppNotice.read_at.is_(None))).all()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for row in rows:
        row.read_at = now
    db.commit()
    return {"updated_count": len(rows)}


@m.app.post("/notifications/{notice_id}/read")
def mark_notification_read(notice_id: int, user: m.CurrentUser, db: m.DbSession) -> dict[str, Any]:
    row = db.get(s34.InAppNotice, notice_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(404, "Không tìm thấy thông báo")
    row.read_at = row.read_at or datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return {"id": row.id, "read_at": row.read_at.isoformat()}
