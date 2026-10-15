"""Sprint 7 and 8 billing, final results, surveys, and operational dashboards."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Any

from fastapi import Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, and_, func, or_, select
from sqlalchemy.orm import Mapped, mapped_column

import main as m
import sprint34 as s34
import sprint56 as s56

logger = logging.getLogger(__name__)
VIETNAM_TZ = timezone(timedelta(hours=7))


class FeeSchedule(m.Base):
    __tablename__ = "fee_schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("training_programs.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    amount: Mapped[int] = mapped_column(Integer)
    effective_from: Mapped[date] = mapped_column(Date, index=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class BillingPlan(m.Base):
    __tablename__ = "billing_plans"
    __table_args__ = (UniqueConstraint("student_id", "class_id", name="uq_billing_student_class"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id", ondelete="RESTRICT"), index=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("training_classes.id", ondelete="RESTRICT"), index=True)
    fee_schedule_id: Mapped[int | None] = mapped_column(ForeignKey("fee_schedules.id", ondelete="SET NULL"), nullable=True)
    tuition_amount: Mapped[int] = mapped_column(Integer)
    discount_amount: Mapped[int] = mapped_column(Integer, default=0)
    discount_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    discount_status: Mapped[str] = mapped_column(String(20), default="none")
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class Installment(m.Base):
    __tablename__ = "billing_installments"
    __table_args__ = (UniqueConstraint("plan_id", "sequence", name="uq_billing_plan_sequence"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("billing_plans.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    amount: Mapped[int] = mapped_column(Integer)
    due_date: Mapped[date] = mapped_column(Date, index=True)


class Payment(m.Base):
    __tablename__ = "billing_payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    installment_id: Mapped[int] = mapped_column(ForeignKey("billing_installments.id", ondelete="RESTRICT"), index=True)
    receipt_code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    amount: Mapped[int] = mapped_column(Integer)
    method: Mapped[str] = mapped_column(String(30))
    paid_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    received_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class DiscountRequest(m.Base):
    __tablename__ = "billing_discount_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("billing_plans.id", ondelete="CASCADE"), index=True)
    discount_amount: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class BillingReminderLog(m.Base):
    __tablename__ = "billing_reminder_logs"
    __table_args__ = (UniqueConstraint("installment_id", "reminder_date", "kind", name="uq_billing_reminder_day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    installment_id: Mapped[int] = mapped_column(ForeignKey("billing_installments.id", ondelete="CASCADE"), index=True)
    reminder_date: Mapped[date] = mapped_column(Date, index=True)
    kind: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class FinalGradeConfig(m.Base):
    __tablename__ = "final_grade_configs"
    __table_args__ = (UniqueConstraint("program_id", "subject_id", "class_id", name="uq_final_grade_scope"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("training_programs.id", ondelete="CASCADE"), index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("training_subjects.id", ondelete="RESTRICT"), index=True)
    class_id: Mapped[int | None] = mapped_column(ForeignKey("training_classes.id", ondelete="CASCADE"), nullable=True, index=True)
    passing_score: Mapped[float] = mapped_column(Float, default=5)
    critical_score: Mapped[float] = mapped_column(Float, default=0)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class FinalGradeComponent(m.Base):
    __tablename__ = "final_grade_components"

    id: Mapped[int] = mapped_column(primary_key=True)
    config_id: Mapped[int] = mapped_column(ForeignKey("final_grade_configs.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    weight_percent: Mapped[float] = mapped_column(Float)
    required: Mapped[bool] = mapped_column(default=True)
    sequence: Mapped[int] = mapped_column(Integer)


class AssignmentComponentLink(m.Base):
    __tablename__ = "assignment_component_links"
    __table_args__ = (UniqueConstraint("assignment_id", name="uq_assignment_final_component"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("training_assignments.id", ondelete="CASCADE"), index=True)
    component_id: Mapped[int] = mapped_column(ForeignKey("final_grade_components.id", ondelete="CASCADE"), index=True)


class FinalGrade(m.Base):
    __tablename__ = "final_grades"
    __table_args__ = (UniqueConstraint("class_id", "subject_id", "student_id", name="uq_final_grade_student_subject"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("training_classes.id", ondelete="CASCADE"), index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("training_subjects.id", ondelete="RESTRICT"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id", ondelete="RESTRICT"), index=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    state: Mapped[str] = mapped_column(String(20), default="incomplete")
    breakdown_json: Mapped[str] = mapped_column(Text, default="[]")
    is_locked: Mapped[bool] = mapped_column(default=False)
    locked_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class Survey(m.Base):
    __tablename__ = "course_surveys"
    __table_args__ = (UniqueConstraint("class_id", name="uq_course_survey_class"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("training_classes.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    questions_json: Mapped[str] = mapped_column(Text)
    due_at: Mapped[datetime] = mapped_column(DateTime)
    state: Mapped[str] = mapped_column(String(20), default="open")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class SurveyResponse(m.Base):
    __tablename__ = "course_survey_responses"
    __table_args__ = (UniqueConstraint("survey_id", "student_id", name="uq_survey_student"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    survey_id: Mapped[int] = mapped_column(ForeignKey("course_surveys.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id", ondelete="RESTRICT"), index=True)
    answers_json: Mapped[str] = mapped_column(Text)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class GraduationRecord(m.Base):
    __tablename__ = "graduation_records"
    __table_args__ = (UniqueConstraint("class_id", "student_id", name="uq_graduation_student_class"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("training_classes.id", ondelete="RESTRICT"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id", ondelete="RESTRICT"), index=True)
    graduated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    confirmed_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))


class FeeScheduleInput(BaseModel):
    program_id: int
    name: str = Field(min_length=2, max_length=160)
    amount: int = Field(gt=0, le=2_000_000_000)
    effective_from: date
    effective_to: date | None = None


class InstallmentInput(BaseModel):
    sequence: int = Field(ge=1, le=24)
    amount: int = Field(gt=0, le=2_000_000_000)
    due_date: date


class PlanInput(BaseModel):
    student_id: int
    class_id: int
    fee_schedule_id: int | None = None
    tuition_amount: int = Field(gt=0, le=2_000_000_000)
    installments: list[InstallmentInput] = Field(min_length=1, max_length=24)


class PaymentInput(BaseModel):
    amount: int = Field(gt=0, le=2_000_000_000)
    method: str = Field(pattern="^(cash|bank_transfer)$")
    paid_at: datetime
    note: str = Field(default="", max_length=1000)


class DiscountInput(BaseModel):
    amount: int | None = Field(default=None, gt=0)
    percent: float | None = Field(default=None, gt=0, le=100)
    reason: str = Field(min_length=2, max_length=1000)


class GradeComponentInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    weight_percent: float = Field(gt=0, le=100)
    required: bool = True


class GradeConfigInput(BaseModel):
    program_id: int
    subject_id: int
    class_id: int | None = None
    passing_score: float = Field(ge=0, le=100)
    critical_score: float = Field(ge=0, le=100)
    components: list[GradeComponentInput] = Field(min_length=1, max_length=20)


class SurveyInput(BaseModel):
    class_id: int
    title: str = Field(min_length=2, max_length=200)
    due_at: datetime
    questions: list[dict[str, Any]] = Field(min_length=1, max_length=40)


def _need(user: m.User, db: m.Session, module: str, action: str) -> None:
    if not m.permission_allows(m.assigned_roles(db, user), module, action):
        raise HTTPException(403, "Bạn không có quyền truy cập chức năng này")


def _student(db: m.Session, user: m.User) -> s34.StudentProfile:
    result = db.scalar(select(s34.StudentProfile).where(s34.StudentProfile.user_id == user.id))
    if result is None:
        raise HTTPException(403, "Không tìm thấy hồ sơ học viên")
    return result


def _class_visible(db: m.Session, user: m.User, class_id: int, module: str, action: str = "read") -> bool:
    roles = m.assigned_roles(db, user)
    if m.permission_allows(roles, module, "full"):
        return True
    if module == "grades" and m.permission_allows(roles, module, action):
        return s34._can_manage_class(db, user, class_id)
    if module == "billing":
        return False
    return s34._can_manage_class(db, user, class_id)


def _paid_amount(db: m.Session, installment_id: int) -> int:
    return int(db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.installment_id == installment_id)) or 0)


def _rebalance_installments(db: m.Session, plan: BillingPlan, discounted_total: int) -> None:
    installments = db.scalars(select(Installment).where(
        Installment.plan_id == plan.id
    ).order_by(Installment.sequence)).all()
    original_total = sum(item.amount for item in installments)
    if original_total <= 0 or discounted_total <= 0:
        raise HTTPException(409, "Kế hoạch thanh toán không hợp lệ sau giảm giá")
    allocated = 0
    for index, item in enumerate(installments):
        if index == len(installments) - 1:
            item.amount = discounted_total - allocated
        else:
            item.amount = int(discounted_total * item.amount / original_total)
            allocated += item.amount


def _plan_json(db: m.Session, plan: BillingPlan) -> dict[str, Any]:
    student = db.get(s34.StudentProfile, plan.student_id)
    training_class = db.get(m.TrainingClass, plan.class_id)
    installments = db.scalars(select(Installment).where(Installment.plan_id == plan.id).order_by(Installment.sequence)).all()
    rows = []
    for item in installments:
        paid = _paid_amount(db, item.id)
        rows.append({"id": item.id, "sequence": item.sequence, "amount": item.amount, "paid": paid,
            "remaining": max(0, item.amount - paid), "due_date": item.due_date.isoformat(),
            "status": "paid" if paid >= item.amount else "partial" if paid else "overdue" if item.due_date < date.today() else "unpaid"})
    approved_discount = plan.discount_amount if plan.discount_status == "approved" else 0
    return {"id": plan.id, "student_id": plan.student_id, "student_name": student.full_name if student else "",
        "student_code": student.student_code if student else "", "class_id": plan.class_id,
        "class_name": training_class.name if training_class else "", "tuition_amount": plan.tuition_amount,
        "discount_amount": approved_discount, "discount_reason": plan.discount_reason,
        "discount_status": plan.discount_status, "amount_due": plan.tuition_amount - approved_discount,
        "installments": rows, "received": sum(item["paid"] for item in rows),
        "remaining": sum(item["remaining"] for item in rows)}


@m.app.get("/billing/fee-schedules")
def list_fee_schedules(user: m.Annotated[m.User, Depends(m.require_permission("billing", "read"))], db: m.DbSession) -> list[dict[str, Any]]:
    return [{"id": row.id, "program_id": row.program_id, "program_name": db.get(m.TrainingProgram, row.program_id).name,
        "name": row.name, "amount": row.amount, "effective_from": row.effective_from.isoformat(),
        "effective_to": row.effective_to.isoformat() if row.effective_to else None}
        for row in db.scalars(select(FeeSchedule).order_by(FeeSchedule.effective_from.desc())).all()]


@m.app.post("/billing/fee-schedules", status_code=201)
def create_fee_schedule(payload: FeeScheduleInput, user: m.Annotated[m.User, Depends(m.require_permission("billing", "full"))],
                        db: m.DbSession) -> dict[str, Any]:
    if db.get(m.TrainingProgram, payload.program_id) is None:
        raise HTTPException(404, "Không tìm thấy chương trình")
    if payload.effective_to and payload.effective_to < payload.effective_from:
        raise HTTPException(422, "Ngày kết thúc phải bằng hoặc sau ngày hiệu lực")
    row = FeeSchedule(**payload.model_dump(), created_by=user.id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "program_id": row.program_id, "name": row.name, "amount": row.amount,
        "effective_from": row.effective_from.isoformat(), "effective_to": row.effective_to.isoformat() if row.effective_to else None}


@m.app.post("/billing/plans", status_code=201)
def create_billing_plan(payload: PlanInput, user: m.Annotated[m.User, Depends(m.require_permission("billing", "full"))],
                        db: m.DbSession) -> dict[str, Any]:
    student = db.get(s34.StudentProfile, payload.student_id)
    training_class = db.get(m.TrainingClass, payload.class_id)
    if student is None or training_class is None:
        raise HTTPException(404, "Không tìm thấy học viên hoặc lớp")
    if db.scalar(select(BillingPlan.id).where(BillingPlan.student_id == student.id, BillingPlan.class_id == training_class.id)):
        raise HTTPException(409, "Kế hoạch thanh toán cho học viên/lớp này đã tồn tại")
    if len({item.sequence for item in payload.installments}) != len(payload.installments):
        raise HTTPException(422, "Thứ tự đợt thanh toán không được trùng")
    if sum(item.amount for item in payload.installments) != payload.tuition_amount:
        raise HTTPException(422, "Tổng các đợt phải bằng học phí trước giảm giá")
    if payload.fee_schedule_id:
        fee = db.get(FeeSchedule, payload.fee_schedule_id)
        if fee is None or fee.program_id != training_class.program_id:
            raise HTTPException(422, "Biểu phí không thuộc chương trình của lớp")
    plan = BillingPlan(student_id=student.id, class_id=training_class.id,
        fee_schedule_id=payload.fee_schedule_id, tuition_amount=payload.tuition_amount, created_by=user.id)
    db.add(plan)
    db.flush()
    db.add_all([Installment(plan_id=plan.id, **item.model_dump()) for item in payload.installments])
    db.commit()
    db.refresh(plan)
    return _plan_json(db, plan)


@m.app.post("/billing/plans/bulk", status_code=201)
def create_bulk_billing_plans(user: m.Annotated[m.User, Depends(m.require_permission("billing", "full"))],
                              db: m.DbSession, payload: dict[str, Any]) -> dict[str, int]:
    class_id, student_ids = payload.get("class_id"), payload.get("student_ids")
    schedule_id, amounts, dates = payload.get("fee_schedule_id"), payload.get("amounts"), payload.get("due_dates")
    if not isinstance(class_id, int) or not isinstance(student_ids, list) or not student_ids or len(student_ids) > 500 or not isinstance(amounts, list) or not isinstance(dates, list) or not amounts or len(amounts) != len(dates):
        raise HTTPException(422, "Cần lớp, danh sách học viên và các đợt thanh toán hợp lệ")
    try:
        installment_values = [InstallmentInput(sequence=index + 1, amount=int(amount), due_date=date.fromisoformat(day))
            for index, (amount, day) in enumerate(zip(amounts, dates))]
    except (TypeError, ValueError) as error:
        raise HTTPException(422, "Số tiền hoặc ngày đến hạn không hợp lệ") from error
    class_row = db.get(m.TrainingClass, class_id)
    fee = db.get(FeeSchedule, schedule_id) if schedule_id else None
    if class_row is None or (fee and fee.program_id != class_row.program_id):
        raise HTTPException(422, "Lớp hoặc biểu phí không hợp lệ")
    valid_students = set(db.scalars(select(s34.StudentProfile.id).where(s34.StudentProfile.id.in_(set(student_ids)))).all())
    if valid_students != set(student_ids):
        raise HTTPException(422, "Danh sách có học viên không tồn tại hoặc bị trùng")
    if fee is None and not isinstance(payload.get("tuition_amount"), int):
        raise HTTPException(422, "Cần biểu phí hoặc tuition_amount")
    tuition = fee.amount if fee else int(payload["tuition_amount"])
    if sum(item.amount for item in installment_values) != tuition:
        raise HTTPException(422, "Tổng các đợt không bằng học phí")
    for student_id in student_ids:
        if db.scalar(select(BillingPlan.id).where(BillingPlan.student_id == student_id, BillingPlan.class_id == class_id)):
            raise HTTPException(409, f"Học viên {student_id} đã có kế hoạch thanh toán")
    for student_id in student_ids:
        plan = BillingPlan(student_id=student_id, class_id=class_id, fee_schedule_id=fee.id if fee else None,
            tuition_amount=tuition, created_by=user.id)
        db.add(plan)
        db.flush()
        db.add_all([Installment(plan_id=plan.id, **item.model_dump()) for item in installment_values])
    db.commit()
    return {"created_count": len(student_ids)}


@m.app.get("/billing/plans")
def list_billing_plans(user: m.CurrentUser, db: m.DbSession, class_id: int | None = None,
                       student_id: int | None = None, overdue: bool = False) -> list[dict[str, Any]]:
    roles = m.assigned_roles(db, user)
    own_student_id = db.scalar(select(s34.StudentProfile.id).where(s34.StudentProfile.user_id == user.id))
    if own_student_id is not None and not m.permission_allows(roles, "billing", "full"):
        student_id = own_student_id
    elif not m.permission_allows(roles, "billing", "read"):
        raise HTTPException(403, "Bạn không có quyền xem khoản nợ")
    statement = select(BillingPlan)
    if class_id:
        statement = statement.where(BillingPlan.class_id == class_id)
    if student_id:
        statement = statement.where(BillingPlan.student_id == student_id)
    plans = db.scalars(statement.order_by(BillingPlan.created_at.desc()).limit(1000)).all()
    result = [_plan_json(db, plan) for plan in plans]
    if overdue:
        result = [plan for plan in result if any(item["status"] == "overdue" for item in plan["installments"])]
    return result


@m.app.get("/billing/plans/{plan_id}")
def get_billing_plan(plan_id: int, user: m.CurrentUser, db: m.DbSession) -> dict[str, Any]:
    row = db.get(BillingPlan, plan_id)
    if row is None:
        raise HTTPException(404, "Không tìm thấy kế hoạch thanh toán")
    student_id = db.scalar(select(s34.StudentProfile.id).where(s34.StudentProfile.user_id == user.id))
    if student_id != row.student_id and not m.permission_allows(m.assigned_roles(db, user), "billing", "read"):
        raise HTTPException(403, "Không có quyền xem kế hoạch thanh toán này")
    return _plan_json(db, row)


@m.app.post("/billing/installments/{installment_id}/payments", status_code=201)
def record_payment(installment_id: int, payload: PaymentInput,
                   user: m.Annotated[m.User, Depends(m.require_permission("billing", "full"))],
                   db: m.DbSession) -> dict[str, Any]:
    installment = db.scalar(
        select(Installment)
        .where(Installment.id == installment_id)
        .with_for_update()
    )
    if installment is None:
        raise HTTPException(404, "Không tìm thấy đợt thanh toán")
    plan = db.get(BillingPlan, installment.plan_id)
    if plan.discount_status == "pending":
        raise HTTPException(409, "Chờ duyệt yêu cầu giảm học phí trước khi thu tiền")
    paid = _paid_amount(db, installment.id)
    if payload.amount > installment.amount - paid:
        raise HTTPException(409, "Số tiền thu vượt khoản nợ còn lại của đợt")
    code = f"PT-{datetime.now().strftime('%Y%m%d')}-{m.secrets.token_hex(5).upper()}"
    row = Payment(installment_id=installment.id, receipt_code=code, amount=payload.amount,
        method=payload.method, paid_at=payload.paid_at.replace(tzinfo=None), received_by=user.id,
        note=payload.note.strip() or None)
    db.add(row)
    db.commit()
    db.refresh(row)
    installment_info = next(item for item in _plan_json(db, plan)["installments"] if item["id"] == installment.id)
    return {"id": row.id, "receipt_code": row.receipt_code, "amount": row.amount,
        "method": row.method, "paid_at": row.paid_at.isoformat(), "installment": installment_info}


@m.app.get("/billing/payments/{payment_id}/receipt")
def get_receipt(payment_id: int, user: m.CurrentUser, db: m.DbSession) -> dict[str, Any]:
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(404, "Không tìm thấy biên lai")
    installment = db.get(Installment, payment.installment_id)
    plan = db.get(BillingPlan, installment.plan_id)
    student = db.get(s34.StudentProfile, plan.student_id)
    if student.user_id != user.id and not m.permission_allows(m.assigned_roles(db, user), "billing", "read"):
        raise HTTPException(403, "Bạn không có quyền xem biên lai này")
    return {"receipt_code": payment.receipt_code, "student_name": student.full_name,
        "student_code": student.student_code, "class_name": db.get(m.TrainingClass, plan.class_id).name,
        "amount": payment.amount, "method": payment.method, "paid_at": payment.paid_at.isoformat(),
        "received_by": db.get(m.User, payment.received_by).full_name, "note": payment.note}


@m.app.post("/billing/plans/{plan_id}/discount")
def request_discount(plan_id: int, payload: DiscountInput,
                     user: m.Annotated[m.User, Depends(m.require_permission("billing", "full"))],
                     db: m.DbSession) -> dict[str, Any]:
    plan = db.get(BillingPlan, plan_id)
    if plan is None:
        raise HTTPException(404, "Không tìm thấy kế hoạch thanh toán")
    installments = db.scalars(select(Installment).where(Installment.plan_id == plan.id)).all()
    if any(_paid_amount(db, item.id) for item in installments):
        raise HTTPException(409, "Không thể áp dụng giảm giá sau khi đã thu tiền")
    if plan.discount_status in {"pending", "approved"}:
        raise HTTPException(409, "Kế hoạch đã có yêu cầu giảm giá đang chờ hoặc đã được duyệt")
    if (payload.percent is None) == (payload.amount is None):
        raise HTTPException(422, "Nhập đúng một trong hai: số tiền hoặc phần trăm giảm")
    discount_amount = round(plan.tuition_amount * payload.percent / 100) if payload.percent is not None else payload.amount
    if discount_amount is None:
        raise HTTPException(422, "Không thể xác định số tiền giảm")
    if discount_amount >= plan.tuition_amount:
        raise HTTPException(422, "Giảm giá phải nhỏ hơn học phí")
    percent = discount_amount * 100 / plan.tuition_amount
    row = DiscountRequest(plan_id=plan.id, discount_amount=discount_amount, reason=payload.reason, requested_by=user.id,
        status="pending" if percent > 30 else "approved")
    if percent <= 30:
        row.decided_by = user.id
        row.decided_at = datetime.now(timezone.utc).replace(tzinfo=None)
        plan.discount_amount = discount_amount
        plan.discount_reason = payload.reason
        plan.discount_status = "approved"
        _rebalance_installments(db, plan, plan.tuition_amount - discount_amount)
    else:
        plan.discount_status = "pending"
    db.add(row)
    db.commit()
    return {"id": row.id, "status": row.status, "discount_amount": row.discount_amount, "requires_manager_approval": percent > 30}


@m.app.get("/billing/discount-requests")
def list_discount_requests(user: m.CurrentUser, db: m.DbSession, status_filter: str | None = None) -> list[dict[str, Any]]:
    roles = m.assigned_roles(db, user)
    if not set(roles).intersection({"accountant", "training_manager", "admin"}):
        raise HTTPException(403, "Bạn không có quyền xem yêu cầu giảm giá")
    statement = select(DiscountRequest)
    if status_filter:
        if status_filter not in {"pending", "approved", "rejected"}:
            raise HTTPException(422, "Trạng thái không hợp lệ")
        statement = statement.where(DiscountRequest.status == status_filter)
    return [{"id": row.id, "plan_id": row.plan_id, "student_name": db.get(s34.StudentProfile, db.get(BillingPlan, row.plan_id).student_id).full_name,
        "discount_amount": row.discount_amount, "reason": row.reason, "status": row.status,
        "created_at": row.created_at.isoformat()} for row in db.scalars(statement.order_by(DiscountRequest.created_at.desc()).limit(300)).all()]


@m.app.post("/billing/discount-requests/{request_id}/decision")
def decide_discount(request_id: int, user: m.CurrentUser, db: m.DbSession, payload: dict[str, Any]) -> dict[str, Any]:
    if not set(m.assigned_roles(db, user)).intersection({"training_manager", "admin"}):
        raise HTTPException(403, "Chỉ Quản lý đào tạo được duyệt giảm giá vượt 30%")
    row = db.get(DiscountRequest, request_id)
    if row is None:
        raise HTTPException(404, "Không tìm thấy yêu cầu giảm giá")
    if row.status != "pending":
        raise HTTPException(409, "Yêu cầu đã được xử lý")
    decision = payload.get("decision")
    if decision not in {"approve", "reject"}:
        raise HTTPException(422, "decision phải là approve hoặc reject")
    row.status = "approved" if decision == "approve" else "rejected"
    row.decided_by = user.id
    row.decided_at = datetime.now(timezone.utc).replace(tzinfo=None)
    plan = db.get(BillingPlan, row.plan_id)
    plan.discount_status = row.status
    if row.status == "approved":
        plan.discount_amount = row.discount_amount
        plan.discount_reason = row.reason
        _rebalance_installments(db, plan, plan.tuition_amount - row.discount_amount)
    else:
        plan.discount_amount = 0
        plan.discount_reason = None
    db.commit()
    return {"id": row.id, "status": row.status}


@m.app.get("/billing/debts.xlsx")
def export_debts(user: m.Annotated[m.User, Depends(m.require_permission("billing", "read"))],
                 db: m.DbSession, class_id: int | None = None) -> StreamingResponse:
    plans = list_billing_plans(user, db, class_id=class_id)
    workbook = m.Workbook()
    sheet = workbook.active
    sheet.title = "Khoản nợ"
    sheet.append(["Mã học viên", "Học viên", "Lớp", "Phải thu", "Đã thu", "Khoản nợ còn lại", "Quá hạn (ngày)"])
    for plan in plans:
        overdue_days = max([ (date.today() - date.fromisoformat(item["due_date"])).days
            for item in plan["installments"] if item["remaining"] and item["due_date"] < date.today().isoformat()] or [0])
        sheet.append([plan["student_code"], plan["student_name"], plan["class_name"],
            plan["amount_due"], plan["received"], plan["remaining"], overdue_days])
    output = m.BytesIO()
    workbook.save(output)
    output.seek(0)
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="billing-debts.xlsx"'})


@m.app.get("/billing/revenue")
def revenue_report(user: m.Annotated[m.User, Depends(m.require_permission("billing", "read"))],
                   db: m.DbSession, from_date: date, to_date: date, group_by: str = "class") -> dict[str, Any]:
    if to_date < from_date or (to_date - from_date).days > 366:
        raise HTTPException(422, "Khoảng thời gian phải hợp lệ và tối đa 366 ngày")
    if group_by not in {"class", "program"}:
        raise HTTPException(422, "group_by phải là class hoặc program")
    payments = db.scalars(select(Payment).where(
        Payment.paid_at >= datetime.combine(from_date, time.min),
        Payment.paid_at < datetime.combine(to_date + timedelta(days=1), time.min),
    ).order_by(Payment.paid_at)).all()
    groups: dict[str, dict[str, int]] = {}
    monthly: dict[str, int] = {}
    received = 0
    for payment in payments:
        installment = db.get(Installment, payment.installment_id)
        plan = db.get(BillingPlan, installment.plan_id)
        training_class = db.get(m.TrainingClass, plan.class_id)
        key = training_class.name
        if group_by == "program":
            program = db.get(m.TrainingProgram, training_class.program_id)
            key = program.name if program else "Không xác định"
        group = groups.setdefault(key, {"received": 0, "remaining": 0})
        group["received"] += payment.amount
        received += payment.amount
        month = payment.paid_at.strftime("%Y-%m")
        monthly[month] = monthly.get(month, 0) + payment.amount
    plans = list_billing_plans(user, db)
    remaining = sum(plan["remaining"] for plan in plans)
    return {"from_date": from_date.isoformat(), "to_date": to_date.isoformat(),
        "received": received, "remaining": remaining, "groups": groups,
        "monthly": [{"month": month, "received": amount} for month, amount in sorted(monthly.items())]}


def _send_reminder_email(email: str, subject: str, body: str) -> None:
    if not m.smtp_configured():
        logger.warning("Billing reminder email not sent because SMTP is not configured")
        return
    message = EmailMessage()
    message["To"] = email
    message["Subject"] = subject
    message.set_content(body)
    message["From"] = m.SMTP_FROM
    if not m.send_email(message):
        logger.error("Billing reminder email delivery failed for configured SMTP")


def _process_due_reminders(db: m.Session, today: date) -> int:
    reminders_sent = 0
    installments = db.scalars(select(Installment).where(Installment.due_date <= today + timedelta(days=3))).all()
    for installment in installments:
        plan = db.get(BillingPlan, installment.plan_id)
        if plan.discount_status == "pending" or _paid_amount(db, installment.id) >= installment.amount:
            continue
        kind = "overdue" if installment.due_date < today else "before_due" if installment.due_date == today + timedelta(days=3) else None
        if kind is None or db.scalar(select(BillingReminderLog.id).where(
            BillingReminderLog.installment_id == installment.id,
            BillingReminderLog.reminder_date == today, BillingReminderLog.kind == kind)):
            continue
        student = db.get(s34.StudentProfile, plan.student_id)
        if student is None:
            continue
        due_text = "đã quá hạn" if kind == "overdue" else "sắp đến hạn sau 3 ngày"
        balance = next(item["remaining"] for item in _plan_json(db, plan)["installments"] if item["id"] == installment.id)
        body = f"Đợt {installment.sequence} học phí của bạn {due_text}. Số tiền còn lại: {balance:,} VND."
        s34._notice(db, student.user_id, "Nhắc hạn học phí", body)
        _send_reminder_email(student.email, "Nhắc hạn thanh toán học phí", body)
        db.add(BillingReminderLog(installment_id=installment.id, reminder_date=today, kind=kind))
        reminders_sent += 1
    db.commit()
    return reminders_sent


@m.app.post("/billing/reminders/run")
def run_billing_reminders(user: m.Annotated[m.User, Depends(m.require_permission("billing", "full"))],
                          db: m.DbSession) -> dict[str, int]:
    return {"sent": _process_due_reminders(db, date.today())}


async def _daily_reminder_worker() -> None:
    while True:
        now = datetime.now(VIETNAM_TZ)
        next_run = (now + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
        if now.hour < 8:
            next_run = now.replace(hour=8, minute=0, second=0, microsecond=0)
        await asyncio.sleep(max(1, (next_run - now).total_seconds()))
        try:
            with m.SessionLocal() as db:
                _process_due_reminders(db, datetime.now(VIETNAM_TZ).date())
        except Exception:
            logger.exception("Daily billing reminder run failed")


@m.app.on_event("startup")
async def start_reminder_worker() -> None:
    app = m.app
    if getattr(app.state, "billing_reminder_task", None) is None:
        app.state.billing_reminder_task = asyncio.create_task(_daily_reminder_worker())


@m.app.on_event("shutdown")
async def stop_reminder_worker() -> None:
    task = getattr(m.app.state, "billing_reminder_task", None)
    if task is not None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        m.app.state.billing_reminder_task = None


@m.app.put("/grades/config")
def save_grade_config(payload: GradeConfigInput,
                      user: m.Annotated[m.User, Depends(m.require_permission("grades", "full"))],
                      db: m.DbSession) -> dict[str, Any]:
    program = db.get(m.TrainingProgram, payload.program_id)
    subject = db.get(m.TrainingSubject, payload.subject_id)
    if program is None or subject is None:
        raise HTTPException(404, "Không tìm thấy chương trình hoặc môn học")
    if payload.class_id:
        training_class = db.get(m.TrainingClass, payload.class_id)
        if training_class is None or training_class.program_id != program.id:
            raise HTTPException(422, "Lớp không thuộc chương trình đã chọn")
        if db.scalar(select(s34.ClassSubject.id).where(
            s34.ClassSubject.class_id == training_class.id, s34.ClassSubject.subject_id == subject.id)) is None:
            raise HTTPException(422, "Môn học không thuộc lớp")
    if sum(item.weight_percent for item in payload.components) != 100:
        raise HTTPException(422, "Tổng trọng số các thành phần phải bằng 100%")
    if payload.critical_score > payload.passing_score:
        raise HTTPException(422, "Điểm liệt không được lớn hơn điểm đạt")
    row = db.scalar(select(FinalGradeConfig).where(
        FinalGradeConfig.program_id == program.id, FinalGradeConfig.subject_id == subject.id,
        FinalGradeConfig.class_id == payload.class_id))
    if row is None:
        row = FinalGradeConfig(program_id=program.id, subject_id=subject.id, class_id=payload.class_id,
            passing_score=payload.passing_score, critical_score=payload.critical_score, created_by=user.id)
        db.add(row)
        db.flush()
    else:
        row.passing_score = payload.passing_score
        row.critical_score = payload.critical_score
    db.query(FinalGradeComponent).filter(FinalGradeComponent.config_id == row.id).delete()
    db.add_all([FinalGradeComponent(config_id=row.id, name=item.name, weight_percent=item.weight_percent,
        required=item.required, sequence=index + 1) for index, item in enumerate(payload.components)])
    db.commit()
    db.refresh(row)
    return _grade_config_json(db, row)


def _grade_config_json(db: m.Session, row: FinalGradeConfig) -> dict[str, Any]:
    return {"id": row.id, "program_id": row.program_id, "subject_id": row.subject_id, "class_id": row.class_id,
        "passing_score": row.passing_score, "critical_score": row.critical_score,
        "components": [{"id": item.id, "name": item.name, "weight_percent": item.weight_percent,
            "required": item.required, "sequence": item.sequence}
            for item in db.scalars(select(FinalGradeComponent).where(FinalGradeComponent.config_id == row.id).order_by(FinalGradeComponent.sequence)).all()]}


@m.app.get("/grades/config")
def list_grade_configs(user: m.CurrentUser, db: m.DbSession, program_id: int | None = None,
                       class_id: int | None = None) -> list[dict[str, Any]]:
    _need(user, db, "grades", "read")
    statement = select(FinalGradeConfig)
    if program_id:
        statement = statement.where(FinalGradeConfig.program_id == program_id)
    if class_id is not None:
        statement = statement.where(or_(FinalGradeConfig.class_id == class_id, FinalGradeConfig.class_id.is_(None)))
    return [_grade_config_json(db, row) for row in db.scalars(statement.order_by(FinalGradeConfig.program_id, FinalGradeConfig.subject_id)).all()]


@m.app.post("/grades/components/{component_id}/assignments")
def link_assignment_component(component_id: int, user: m.Annotated[m.User, Depends(m.require_permission("grades", "full"))],
                              db: m.DbSession, payload: dict[str, Any]) -> dict[str, Any]:
    component = db.get(FinalGradeComponent, component_id)
    assignment = db.get(s56.Assignment, payload.get("assignment_id"))
    config = db.get(FinalGradeConfig, component.config_id) if component else None
    if component is None or assignment is None or config is None:
        raise HTTPException(404, "Không tìm thấy thành phần điểm hoặc bài tập")
    training_class = db.get(m.TrainingClass, assignment.class_id)
    if assignment.subject_id != config.subject_id or training_class.program_id != config.program_id or (config.class_id is not None and assignment.class_id != config.class_id):
        raise HTTPException(422, "Bài tập không thuộc phạm vi thành phần điểm")
    existing = db.scalar(select(AssignmentComponentLink).where(AssignmentComponentLink.assignment_id == assignment.id))
    if existing:
        existing.component_id = component.id
    else:
        db.add(AssignmentComponentLink(assignment_id=assignment.id, component_id=component.id))
    db.commit()
    return {"assignment_id": assignment.id, "component_id": component.id}


def _recalculate_final_grade(db: m.Session, class_id: int, student_id: int, config: FinalGradeConfig) -> FinalGrade:
    components = db.scalars(select(FinalGradeComponent).where(FinalGradeComponent.config_id == config.id)).all()
    values = []
    incomplete = False
    for component in components:
        assignment_ids = select(AssignmentComponentLink.assignment_id).where(AssignmentComponentLink.component_id == component.id)
        scores = db.execute(
            select(s56.SubmissionGrade.score, s56.Assignment.max_score)
            .join(s56.AssignmentSubmission, s56.AssignmentSubmission.id == s56.SubmissionGrade.submission_id)
            .join(s56.Assignment, s56.Assignment.id == s56.AssignmentSubmission.assignment_id)
            .where(s56.AssignmentSubmission.student_id == student_id,
                s56.AssignmentSubmission.current_version == s56.SubmissionGrade.version_number,
                s56.SubmissionGrade.published_at.is_not(None), s56.Assignment.id.in_(assignment_ids),
                s56.Assignment.class_id == class_id)
        ).all()
        if not scores:
            if component.required:
                incomplete = True
            values.append({"component_id": component.id, "name": component.name,
                "weight_percent": component.weight_percent, "score": None})
            continue
        average = sum(float(score) / float(max_score) * 100 for score, max_score in scores) / len(scores)
        values.append({"component_id": component.id, "name": component.name,
            "weight_percent": component.weight_percent, "score": round(average, 2)})
    score = None if incomplete else round(sum(item["score"] * item["weight_percent"] / 100 for item in values if item["score"] is not None), 2)
    failed_critical = any(item["score"] is not None and item["score"] < config.critical_score for item in values)
    state = "incomplete" if score is None else "failed" if score < config.passing_score or failed_critical else "passed"
    row = db.scalar(select(FinalGrade).where(
        FinalGrade.class_id == class_id, FinalGrade.subject_id == config.subject_id, FinalGrade.student_id == student_id))
    if row is None:
        row = FinalGrade(class_id=class_id, subject_id=config.subject_id, student_id=student_id)
        db.add(row)
    if not row.is_locked:
        row.score = score
        row.state = state
        row.breakdown_json = json.dumps(values, ensure_ascii=False)
    return row


@m.app.post("/grades/classes/{class_id}/subjects/{subject_id}/recalculate")
def recalculate_subject_grades(class_id: int, subject_id: int, user: m.CurrentUser, db: m.DbSession) -> dict[str, Any]:
    if not _class_visible(db, user, class_id, "grades", "write"):
        raise HTTPException(403, "Bạn chưa được phân công vào lớp này")
    training_class = db.get(m.TrainingClass, class_id)
    if training_class is None or db.scalar(select(s34.ClassSubject.id).where(
        s34.ClassSubject.class_id == class_id, s34.ClassSubject.subject_id == subject_id)) is None:
        raise HTTPException(404, "Không tìm thấy môn học trong lớp")
    config = db.scalar(select(FinalGradeConfig).where(
        FinalGradeConfig.program_id == training_class.program_id, FinalGradeConfig.subject_id == subject_id,
        FinalGradeConfig.class_id == class_id))
    config = config or db.scalar(select(FinalGradeConfig).where(
        FinalGradeConfig.program_id == training_class.program_id, FinalGradeConfig.subject_id == subject_id,
        FinalGradeConfig.class_id.is_(None)))
    if config is None:
        raise HTTPException(409, "Chưa cấu hình cách tính điểm môn")
    enrollments = db.scalars(select(s34.StudentEnrollment).where(
        s34.StudentEnrollment.class_id == class_id, s34.StudentEnrollment.status == "active",
        s34.StudentEnrollment.effective_from <= date.today(),
        or_(s34.StudentEnrollment.effective_to.is_(None), s34.StudentEnrollment.effective_to > date.today()))).all()
    for enrollment in enrollments:
        _recalculate_final_grade(db, class_id, enrollment.student_id, config)
    db.commit()
    return {"class_id": class_id, "subject_id": subject_id, "student_count": len(enrollments)}


@m.app.post("/grades/classes/{class_id}/subjects/{subject_id}/lock")
def lock_subject_grades(class_id: int, subject_id: int,
                        user: m.Annotated[m.User, Depends(m.require_permission("grades", "write"))],
                        db: m.DbSession) -> dict[str, int]:
    if not _class_visible(db, user, class_id, "grades", "write"):
        raise HTTPException(403, "Bạn chưa được phân công vào lớp này")
    rows = db.scalars(select(FinalGrade).where(FinalGrade.class_id == class_id, FinalGrade.subject_id == subject_id)).all()
    if not rows or any(row.score is None for row in rows):
        raise HTTPException(409, "Cần tính đủ điểm cho toàn bộ học viên trước khi chốt")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for row in rows:
        row.is_locked = True
        row.locked_by = user.id
        row.locked_at = now
    db.commit()
    return {"locked_count": len(rows)}


@m.app.post("/grades/classes/{class_id}/subjects/{subject_id}/unlock")
def unlock_subject_grades(class_id: int, subject_id: int,
                          user: m.Annotated[m.User, Depends(m.require_permission("grades", "full"))],
                          db: m.DbSession) -> dict[str, int]:
    rows = db.scalars(select(FinalGrade).where(FinalGrade.class_id == class_id, FinalGrade.subject_id == subject_id)).all()
    for row in rows:
        row.is_locked = False
        row.locked_by = None
        row.locked_at = None
    db.commit()
    return {"unlocked_count": len(rows)}


def _attendance_is_over_threshold(db: m.Session, class_id: int, student_id: int) -> bool:
    training_class = db.get(m.TrainingClass, class_id)
    if training_class is None:
        return False
    policy = db.scalar(select(s56.AttendancePolicy).where(s56.AttendancePolicy.program_id == training_class.program_id))
    threshold = policy.absence_threshold_percent if policy else 20
    lessons = db.scalars(select(s34.TrainingLesson).where(s34.TrainingLesson.class_id == class_id,
        s34.TrainingLesson.status == "scheduled", s34.TrainingLesson.ends_at <= datetime.now())).all()
    if not lessons:
        return False
    absences = db.scalar(select(func.count(s34.Attendance.id)).where(
        s34.Attendance.student_id == student_id, s34.Attendance.lesson_id.in_([item.id for item in lessons]),
        s34.Attendance.status.in_(["unexcused", "excused"]))) or 0
    return absences * 100 / len(lessons) >= threshold


@m.app.get("/grades/transcript")
def get_transcript(user: m.CurrentUser, db: m.DbSession, student_id: int | None = None) -> dict[str, Any]:
    own = db.scalar(select(s34.StudentProfile.id).where(s34.StudentProfile.user_id == user.id))
    roles = m.assigned_roles(db, user)
    if own is not None and not m.permission_allows(roles, "grades", "full"):
        student_id = own
    elif student_id is None:
        raise HTTPException(422, "Cần student_id")
    elif not m.permission_allows(roles, "grades", "read"):
        raise HTTPException(403, "Bạn không có quyền xem bảng điểm")
    student = db.get(s34.StudentProfile, student_id)
    if student is None:
        raise HTTPException(404, "Không tìm thấy học viên")
    enrollments = db.scalars(select(s34.StudentEnrollment).where(s34.StudentEnrollment.student_id == student_id).order_by(s34.StudentEnrollment.enrolled_at)).all()
    entries = []
    weighted: list[tuple[float, float]] = []
    for enrollment in enrollments:
        training_class = db.get(m.TrainingClass, enrollment.class_id)
        for link in s34._class_subjects(db, enrollment.class_id):
            subject = db.get(m.TrainingSubject, link.subject_id)
            final = db.scalar(select(FinalGrade).where(FinalGrade.class_id == enrollment.class_id,
                FinalGrade.subject_id == link.subject_id, FinalGrade.student_id == student_id))
            entries.append({"class_id": enrollment.class_id, "class_name": training_class.name if training_class else "",
                "subject_id": link.subject_id, "subject_name": subject.name if subject else "",
                "score": final.score if final else None, "result": final.state if final else "incomplete"})
            if final and final.score is not None:
                weight = float(subject.weight) if subject else 1.0
                weighted.append((final.score, weight))
    average = round(sum(score * weight for score, weight in weighted) / sum(weight for _, weight in weighted), 2) if weighted else None
    return {"student_id": student.id, "student_code": student.student_code, "student_name": student.full_name,
        "average": average, "subjects": entries}


@m.app.get("/grades/classes/{class_id}/graduation")
def graduation_eligibility(class_id: int,
                           user: m.Annotated[m.User, Depends(m.require_permission("grades", "full"))],
                           db: m.DbSession) -> dict[str, Any]:
    training_class = db.get(m.TrainingClass, class_id)
    if training_class is None:
        raise HTTPException(404, "Không tìm thấy lớp")
    links = s34._class_subjects(db, class_id)
    enrollments = db.scalars(select(s34.StudentEnrollment).where(
        s34.StudentEnrollment.class_id == class_id, s34.StudentEnrollment.status == "active",
        s34.StudentEnrollment.effective_to.is_(None))).all()
    eligible, ineligible = [], []
    for enrollment in enrollments:
        student = db.get(s34.StudentProfile, enrollment.student_id)
        reasons = []
        if student is None:
            continue
        if any((grade := db.scalar(select(FinalGrade).where(
            FinalGrade.class_id == class_id, FinalGrade.subject_id == link.subject_id,
            FinalGrade.student_id == student.id))) is None or grade.state != "passed" for link in links):
            reasons.append("Chưa đạt đủ các môn")
        if _attendance_is_over_threshold(db, class_id, student.id):
            reasons.append("Vắng vượt ngưỡng chuyên cần")
        plan = db.scalar(select(BillingPlan).where(BillingPlan.class_id == class_id, BillingPlan.student_id == student.id))
        if plan and _plan_json(db, plan)["remaining"] > 0:
            reasons.append("Còn khoản nợ học phí")
        if plan is None:
            reasons.append("Chưa có kế hoạch học phí")
        record = {"student_id": student.id, "student_code": student.student_code, "student_name": student.full_name,
            "eligible": not reasons, "reasons": reasons}
        (eligible if not reasons else ineligible).append(record)
    return {"class_id": class_id, "class_name": training_class.name, "eligible": eligible, "ineligible": ineligible}


@m.app.post("/grades/classes/{class_id}/graduation/confirm")
def confirm_graduation(class_id: int,
                       user: m.Annotated[m.User, Depends(m.require_permission("grades", "full"))],
                       db: m.DbSession, payload: dict[str, Any]) -> dict[str, int]:
    student_ids = payload.get("student_ids")
    if not isinstance(student_ids, list) or not student_ids or len(student_ids) > 500 or len(student_ids) != len(set(student_ids)):
        raise HTTPException(422, "Chọn ít nhất một học viên, không lặp")
    eligibility = graduation_eligibility(class_id, user, db)
    eligible_ids = {row["student_id"] for row in eligibility["eligible"]}
    if not set(student_ids).issubset(eligible_ids):
        raise HTTPException(409, "Chỉ xác nhận được học viên đủ điều kiện")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for student_id in student_ids:
        if db.scalar(select(GraduationRecord.id).where(GraduationRecord.class_id == class_id, GraduationRecord.student_id == student_id)):
            continue
        db.add(GraduationRecord(class_id=class_id, student_id=student_id, confirmed_by=user.id, graduated_at=now))
        student = db.get(s34.StudentProfile, student_id)
        if student:
            student.status = "graduated"
            m_user = db.get(m.User, student.user_id)
            if m_user:
                s34._notice(db, m_user.id, "Chúc mừng tốt nghiệp", f"Bạn đã hoàn thành lớp {eligibility['class_name']}.")
    db.commit()
    return {"graduated_count": len(student_ids)}


@m.app.get("/grades/transcript/export")
def transcript_export(user: m.CurrentUser, db: m.DbSession, student_id: int | None = None) -> StreamingResponse:
    transcript = get_transcript(user, db, student_id)
    workbook = m.Workbook()
    sheet = workbook.active
    sheet.title = "Bảng điểm"
    sheet.append(["Mã học viên", transcript["student_code"]])
    sheet.append(["Họ tên", transcript["student_name"]])
    sheet.append(["Điểm trung bình", transcript["average"]])
    sheet.append([])
    sheet.append(["Lớp", "Môn học", "Điểm", "Kết quả"])
    for row in transcript["subjects"]:
        sheet.append([row["class_name"], row["subject_name"], row["score"], row["result"]])
    output = m.BytesIO()
    workbook.save(output)
    output.seek(0)
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="transcript-{transcript["student_code"]}.xlsx"'})


@m.app.post("/surveys", status_code=201)
def create_survey(payload: SurveyInput,
                  user: m.Annotated[m.User, Depends(m.require_permission("surveys", "full"))],
                  db: m.DbSession) -> dict[str, Any]:
    training_class = db.get(m.TrainingClass, payload.class_id)
    if training_class is None:
        raise HTTPException(404, "Không tìm thấy lớp")
    if db.scalar(select(Survey.id).where(Survey.class_id == payload.class_id)):
        raise HTTPException(409, "Lớp này đã có khảo sát")
    if payload.due_at.replace(tzinfo=None) <= datetime.now():
        raise HTTPException(422, "Hạn khảo sát phải ở tương lai")
    for question in payload.questions:
        if not str(question.get("text", "")).strip() or question.get("type") not in {"rating", "text"}:
            raise HTTPException(422, "Mỗi câu hỏi cần nội dung và loại rating hoặc text")
    row = Survey(class_id=payload.class_id, title=payload.title,
        questions_json=json.dumps(payload.questions, ensure_ascii=False),
        due_at=payload.due_at.replace(tzinfo=None), created_by=user.id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "class_id": row.class_id, "title": row.title,
        "questions": json.loads(row.questions_json), "due_at": row.due_at.isoformat(), "state": row.state}


@m.app.get("/surveys")
def list_surveys(user: m.CurrentUser, db: m.DbSession) -> list[dict[str, Any]]:
    roles = m.assigned_roles(db, user)
    student_id = db.scalar(select(s34.StudentProfile.id).where(s34.StudentProfile.user_id == user.id))
    statement = select(Survey)
    if student_id and not m.permission_allows(roles, "surveys", "full"):
        classes = select(s34.StudentEnrollment.class_id).where(
            s34.StudentEnrollment.student_id == student_id, s34.StudentEnrollment.status == "active")
        statement = statement.where(Survey.class_id.in_(classes))
    elif not m.permission_allows(roles, "surveys", "full"):
        assigned = select(s34.ClassSubject.class_id).outerjoin(s34.ClassSubjectTA, s34.ClassSubjectTA.class_subject_id == s34.ClassSubject.id).where(
            or_(s34.ClassSubject.instructor_id == user.id, s34.ClassSubjectTA.user_id == user.id))
        statement = statement.where(Survey.class_id.in_(assigned))
    result = []
    for survey in db.scalars(statement.order_by(Survey.due_at.desc()).limit(300)).all():
        responded = bool(student_id and db.scalar(select(SurveyResponse.id).where(SurveyResponse.survey_id == survey.id, SurveyResponse.student_id == student_id)))
        result.append({"id": survey.id, "class_id": survey.class_id,
            "class_name": db.get(m.TrainingClass, survey.class_id).name, "title": survey.title,
            "questions": json.loads(survey.questions_json), "due_at": survey.due_at.isoformat(),
            "state": survey.state, "responded": responded})
    return result


@m.app.post("/surveys/{survey_id}/responses", status_code=201)
def submit_survey_response(survey_id: int, user: m.Annotated[m.User, Depends(m.require_permission("surveys", "write"))],
                           db: m.DbSession, payload: dict[str, Any]) -> dict[str, Any]:
    survey = db.get(Survey, survey_id)
    student = _student(db, user)
    if survey is None:
        raise HTTPException(404, "Không tìm thấy khảo sát")
    if survey.state != "open" or survey.due_at < datetime.now():
        raise HTTPException(409, "Khảo sát đã đóng hoặc hết hạn")
    if db.scalar(select(s34.StudentEnrollment.id).where(
        s34.StudentEnrollment.student_id == student.id, s34.StudentEnrollment.class_id == survey.class_id,
        s34.StudentEnrollment.status == "active")) is None:
        raise HTTPException(403, "Khảo sát không thuộc lớp của bạn")
    if db.scalar(select(SurveyResponse.id).where(SurveyResponse.survey_id == survey.id, SurveyResponse.student_id == student.id)):
        raise HTTPException(409, "Bạn đã trả lời khảo sát này")
    answers = payload.get("answers")
    questions = json.loads(survey.questions_json)
    if not isinstance(answers, list) or len(answers) != len(questions):
        raise HTTPException(422, "Cần trả lời đủ các câu hỏi")
    for question, answer in zip(questions, answers):
        value = answer.get("value") if isinstance(answer, dict) else answer
        if question["type"] == "rating" and (not isinstance(value, (int, float)) or not 1 <= value <= 5):
            raise HTTPException(422, "Câu hỏi thang điểm cần giá trị từ 1 đến 5")
        if question["type"] == "text" and (not isinstance(value, str) or len(value) > 4000):
            raise HTTPException(422, "Câu trả lời tự luận không hợp lệ")
    db.add(SurveyResponse(survey_id=survey.id, student_id=student.id,
        answers_json=json.dumps(answers, ensure_ascii=False)))
    db.commit()
    return {"survey_id": survey.id, "submitted": True}


@m.app.get("/surveys/{survey_id}/results")
def survey_results(survey_id: int, user: m.Annotated[m.User, Depends(m.require_permission("surveys", "full"))],
                   db: m.DbSession) -> dict[str, Any]:
    survey = db.get(Survey, survey_id)
    if survey is None:
        raise HTTPException(404, "Không tìm thấy khảo sát")
    questions = json.loads(survey.questions_json)
    responses = db.scalars(select(SurveyResponse).where(SurveyResponse.survey_id == survey_id).order_by(SurveyResponse.submitted_at)).all()
    results = []
    for index, question in enumerate(questions):
        answers = [json.loads(row.answers_json)[index]["value"] if isinstance(json.loads(row.answers_json)[index], dict)
            else json.loads(row.answers_json)[index] for row in responses]
        if question["type"] == "rating":
            numeric = [float(value) for value in answers if isinstance(value, (int, float))]
            results.append({"question": question["text"], "type": "rating",
                "average": round(sum(numeric) / len(numeric), 2) if numeric else None, "responses": len(numeric)})
        else:
            results.append({"question": question["text"], "type": "text", "answers": answers})
    return {"survey_id": survey.id, "class_id": survey.class_id,
        "class_name": db.get(m.TrainingClass, survey.class_id).name,
        "response_count": len(responses), "results": results}


@m.app.get("/reports/dashboard")
def operational_dashboard(user: m.CurrentUser, db: m.DbSession) -> dict[str, Any]:
    roles = m.assigned_roles(db, user)
    is_manager = m.permission_allows(roles, "reports", "full")
    student_id = db.scalar(select(s34.StudentProfile.id).where(s34.StudentProfile.user_id == user.id))
    if student_id is not None and not is_manager:
        classes = select(s34.StudentEnrollment.class_id).where(
            s34.StudentEnrollment.student_id == student_id, s34.StudentEnrollment.status == "active")
        assignments = db.scalars(select(s56.Assignment).where(s56.Assignment.class_id.in_(classes), s56.Assignment.state == "published").order_by(s56.Assignment.due_at).limit(10)).all()
        submissions = db.scalars(select(s56.AssignmentSubmission).where(s56.AssignmentSubmission.student_id == student_id)).all()
        submitted_assignment_ids = {item.assignment_id for item in submissions}
        return {"role": "student", "assignments_due": [{"id": item.id, "title": item.title, "due_at": item.due_at.isoformat(),
            "submitted": item.id in submitted_assignment_ids} for item in assignments],
            "unread_notifications": db.scalar(select(func.count(s34.InAppNotice.id)).where(s34.InAppNotice.user_id == user.id, s34.InAppNotice.read_at.is_(None))) or 0}
    if not is_manager and not m.permission_allows(roles, "reports", "read"):
        raise HTTPException(403, "Bạn không có quyền xem dashboard")
    if "instructor" in roles or "ta" in roles:
        assigned = select(s34.ClassSubject.class_id).outerjoin(s34.ClassSubjectTA, s34.ClassSubjectTA.class_subject_id == s34.ClassSubject.id).where(
            or_(s34.ClassSubject.instructor_id == user.id, s34.ClassSubjectTA.user_id == user.id))
        class_ids = set(db.scalars(assigned).all())
    else:
        class_ids = set(db.scalars(select(m.TrainingClass.id)).all()) if is_manager else set()
    classes = db.scalars(select(m.TrainingClass).where(m.TrainingClass.id.in_(class_ids or {-1}))).all()
    enrollment_query = select(func.count(s34.StudentEnrollment.id)).where(
        s34.StudentEnrollment.class_id.in_(class_ids or {-1}), s34.StudentEnrollment.status == "active", s34.StudentEnrollment.effective_to.is_(None))
    active_leads = db.scalar(select(func.count(m.Lead.id)).where(m.Lead.status.in_(["new", "contacted", "consulting", "trial"]))) or 0
    debt_total = sum(plan["remaining"] for plan in list_billing_plans(user, db) if plan["class_id"] in class_ids) if m.permission_allows(roles, "billing", "read") else None
    risk_students = []
    for training_class in classes:
        summary = s56.attendance_summary(training_class.id, user, db)
        risk_students.extend({"class_id": training_class.id, "class_name": training_class.name,
            "student_id": row["student_id"], "student_name": row["student_name"],
            "absence_percent": row["absence_percent"]}
            for row in summary["items"] if row["at_risk"])
    return {"role": "training_manager" if is_manager else "instructor",
        "running_classes": len([item for item in classes if item.status == "running"]),
        "active_students": int(db.scalar(enrollment_query) or 0),
        "active_leads": active_leads, "overdue_debt": debt_total,
        "high_risk_students": sorted(risk_students, key=lambda item: item["absence_percent"], reverse=True)[:100],
        "classes": [{"id": item.id, "name": item.name, "status": item.status} for item in classes]}


@m.app.get("/reports/attendance-risk")
def attendance_risk_report(user: m.CurrentUser, db: m.DbSession, class_id: int | None = None) -> list[dict[str, Any]]:
    _need(user, db, "reports", "read")
    class_ids = [class_id] if class_id else list(db.scalars(select(m.TrainingClass.id)).all())
    risk = []
    for current_class_id in class_ids:
        if not s56._class_access(db, user, current_class_id, "attendance", "read"):
            continue
        summary = s56.attendance_summary(current_class_id, user, db)
        risk.extend({"class_id": current_class_id, "class_name": summary["class_name"],
            "student_id": row["student_id"], "student_name": row["student_name"],
            "absence_percent": row["absence_percent"], "threshold_percent": row["threshold_percent"]}
            for row in summary["items"] if row["at_risk"])
    return sorted(risk, key=lambda item: item["absence_percent"], reverse=True)
