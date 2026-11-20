"""Multi-user academy platform: accounts, roles, administration, content management,
and the foundations for teachers, classes, groups, organisations, subscriptions and payments.

The learning records themselves (activity, mistakes, conversations, cards, assessments…) stay in
models.py and hang off `profiles`; every profile belongs to exactly one user in server mode.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (JSON, Boolean, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def now() -> datetime:
    return datetime.utcnow()


# ------------------------------------------------------------------ organisations (multi-tenant ready)
class Organization(Base):
    """A company, bank, university or school buying training. Null organisation = individual learner."""

    __tablename__ = "organizations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(30), default="company")  # company|bank|university|college|school|government|association
    country: Mapped[str | None] = mapped_column(String(80), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    seat_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)  # configurable enrolment limit
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


# ------------------------------------------------------------------ users, roles, permissions
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)  # stored lower-case
    password_hash: Mapped[str] = mapped_column(String(255))
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80))
    country: Mapped[str | None] = mapped_column(String(80), nullable=True)
    preferred_language: Mapped[str] = mapped_column(String(10), default="fr")
    objectives: Mapped[list | None] = mapped_column(JSON, nullable=True)
    role: Mapped[str] = mapped_column(String(20), ForeignKey("roles.name"), default="learner", index=True)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)  # active|inactive|suspended
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    notification_prefs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)


class Role(Base):
    __tablename__ = "roles"
    name: Mapped[str] = mapped_column(String(20), primary_key=True)  # super_admin|admin|teacher|learner
    label: Mapped[str] = mapped_column(String(60))
    description: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)  # teacher role exists but is inactive until the teacher portal is switched on


class Permission(Base):
    __tablename__ = "permissions"
    code: Mapped[str] = mapped_column(String(60), primary_key=True)  # e.g. learners.view
    description: Mapped[str] = mapped_column(String(200))


class RolePermission(Base):
    __tablename__ = "role_permissions"
    role: Mapped[str] = mapped_column(String(20), ForeignKey("roles.name"), primary_key=True)
    permission: Mapped[str] = mapped_column(String(60), ForeignKey("permissions.code"), primary_key=True)


class AuthSession(Base):
    """Opaque bearer tokens; only a SHA-256 of the token is stored."""

    __tablename__ = "auth_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    last_used_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AccountToken(Base):
    """Single-use tokens for email verification and password reset (hash stored)."""

    __tablename__ = "account_tokens"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(20))  # verify_email|reset_password
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)  # admin-initiated resets
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(60), index=True)
    target_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    route: Mapped[str | None] = mapped_column(String(200), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    emailed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)


class EmailOutbox(Base):
    """Every email the platform tries to send, with its delivery status (no secrets stored)."""

    __tablename__ = "email_outbox"
    id: Mapped[int] = mapped_column(primary_key=True)
    to_email: Mapped[str] = mapped_column(String(254))
    subject: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20))  # sent|failed|not_configured
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


# ------------------------------------------------------------------ platform configuration
class PlatformSetting(Base):
    __tablename__ = "platform_settings"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class PlatformSecret(Base):
    """API keys entered in the admin portal, encrypted with a key derived from EMA_SECRET_KEY."""

    __tablename__ = "platform_secrets"
    name: Mapped[str] = mapped_column(String(40), primary_key=True)
    ciphertext: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)


# ------------------------------------------------------------------ learning progress & content
class LessonProgress(Base):
    __tablename__ = "lesson_progress"
    __table_args__ = (UniqueConstraint("profile_id", "item_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    item_key: Mapped[str] = mapped_column(String(80))  # curriculum key, e.g. "a1-to-be", "conv-a1_intro"
    kind: Mapped[str] = mapped_column(String(20))
    level: Mapped[str | None] = mapped_column(String(10), nullable=True)  # A1..C2 or "business"
    title: Mapped[str] = mapped_column(String(200), default="")
    route: Mapped[str | None] = mapped_column(String(300), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="in_progress")  # in_progress|completed
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class StudyTime(Base):
    """Minutes the learner actually had the app open and visible (heartbeats)."""

    __tablename__ = "study_time"
    __table_args__ = (UniqueConstraint("profile_id", "day"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    day: Mapped[str] = mapped_column(String(10))  # YYYY-MM-DD (UTC)
    seconds: Mapped[int] = mapped_column(Integer, default=0)


class ContentLesson(Base):
    """Admin-created lessons, or admin edits/unpublishing of built-in lessons (same id overrides)."""

    __tablename__ = "content_lessons"
    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    collection: Mapped[str] = mapped_column(String(20), default="lessons")  # grammar|lessons|business
    data: Mapped[dict] = mapped_column(JSON)
    published: Mapped[bool] = mapped_column(Boolean, default=True)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class ContentDocument(Base):
    """Admin-edited versions of whole content documents (curriculum, placement)."""

    __tablename__ = "content_documents"
    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class MediaAsset(Base):
    """Audio/video/documents added by administrators: uploaded (stored in the database) or linked (YouTube/URL)."""

    __tablename__ = "media_assets"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20))  # audio|video|document
    level: Mapped[str | None] = mapped_column(String(10), nullable=True)
    category: Mapped[str | None] = mapped_column(String(40), nullable=True)  # business category id
    description: Mapped[str] = mapped_column(Text, default="")
    mime: Mapped[str | None] = mapped_column(String(80), nullable=True)
    size: Mapped[int] = mapped_column(Integer, default=0)
    data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True, deferred=True)
    youtube_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    external_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    subtitles: Mapped[list | None] = mapped_column(JSON, nullable=True)  # [{start,end,text}]
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    questions: Mapped[list | None] = mapped_column(JSON, nullable=True)  # comprehension questions
    published: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


# ------------------------------------------------------------------ teachers, classes, groups (foundations)
class TeacherProfile(Base):
    __tablename__ = "teacher_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    bio: Mapped[str] = mapped_column(Text, default="")
    specialties: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|approved|suspended
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Course(Base):
    """A sellable/assignable course (e.g. 'General English B2', 'IELTS prep'). Maps onto curriculum levels/categories."""

    __tablename__ = "courses"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    track: Mapped[str] = mapped_column(String(20))  # general|business|exam
    level: Mapped[str | None] = mapped_column(String(10), nullable=True)
    curriculum_ref: Mapped[str | None] = mapped_column(String(60), nullable=True)  # "level:B2" | "business:meetings"
    published: Mapped[bool] = mapped_column(Boolean, default=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)


class Classroom(Base):
    __tablename__ = "classes"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    level: Mapped[str | None] = mapped_column(String(10), nullable=True)
    objectives: Mapped[str] = mapped_column(Text, default="")
    schedule: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {"days": ["Mon"], "time": "18:00", "tz": "America/Toronto"}
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="planned")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class TeacherAssignment(Base):
    __tablename__ = "teacher_assignments"
    __table_args__ = (UniqueConstraint("teacher_id", "class_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teacher_profiles.id", ondelete="CASCADE"), index=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20), default="lead")


class LearnerGroup(Base):
    __tablename__ = "learner_groups"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(30))  # beginner|intermediate|advanced|business|ielts|toefl|private|corporate
    class_id: Mapped[int | None] = mapped_column(ForeignKey("classes.id"), nullable=True)
    supervisor_teacher_id: Mapped[int | None] = mapped_column(ForeignKey("teacher_profiles.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class GroupCourse(Base):
    __tablename__ = "group_courses"
    group_id: Mapped[int] = mapped_column(ForeignKey("learner_groups.id", ondelete="CASCADE"), primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True)


class Enrolment(Base):
    """Learner in a class or a group (exactly one of class_id/group_id)."""

    __tablename__ = "enrolments"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    class_id: Mapped[int | None] = mapped_column(ForeignKey("classes.id", ondelete="CASCADE"), nullable=True, index=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("learner_groups.id", ondelete="CASCADE"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    enrolled_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Assignment(Base):
    """Homework / lesson / assessment assigned to a class or group by a teacher."""

    __tablename__ = "assignments"
    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int | None] = mapped_column(ForeignKey("classes.id", ondelete="CASCADE"), nullable=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("learner_groups.id", ondelete="CASCADE"), nullable=True)
    teacher_id: Mapped[int | None] = mapped_column(ForeignKey("teacher_profiles.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(20))  # lesson|homework|assessment|announcement
    item_ref: Mapped[str | None] = mapped_column(String(80), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    instructions: Mapped[str] = mapped_column(Text, default="")
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class ClassSession(Base):
    __tablename__ = "class_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id", ondelete="CASCADE"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime)
    duration_min: Mapped[int] = mapped_column(Integer, default=60)
    meeting_url: Mapped[str | None] = mapped_column(String(500), nullable=True)


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (UniqueConstraint("session_id", "user_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("class_sessions.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20))  # present|absent|late|excused


# ------------------------------------------------------------------ subscriptions & payments (foundations)
class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    price_monthly_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_annual_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="CAD")
    trial_days: Mapped[int] = mapped_column(Integer, default=0)
    features: Mapped[list | None] = mapped_column(JSON, nullable=True)  # feature codes
    limits: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {"lessons_per_week": 5, "seats": 50}
    for_organizations: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort: Mapped[int] = mapped_column(Integer, default=0)


class Subscription(Base):
    """Belongs to a user OR an organisation."""

    __tablename__ = "subscriptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("subscription_plans.id"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    interval: Mapped[str] = mapped_column(String(10), default="month")  # month|year
    status: Mapped[str] = mapped_column(String(20), default="trialing")  # trialing|active|past_due|cancelled|expired
    provider: Mapped[str | None] = mapped_column(String(20), nullable=True)  # stripe|paypal|manual
    provider_subscription_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Payment(Base):
    """Payment records mirrored from the provider's webhooks. Card data never touches this database."""

    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int | None] = mapped_column(ForeignKey("subscriptions.id"), nullable=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(20), default="subscription")  # subscription|one_time|refund
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="CAD")
    status: Mapped[str] = mapped_column(String(20))  # pending|succeeded|failed|refunded
    provider: Mapped[str] = mapped_column(String(20))
    provider_payment_id: Mapped[str | None] = mapped_column(String(120), nullable=True, unique=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Invoice(Base):
    __tablename__ = "invoices"
    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(40), unique=True)
    payment_id: Mapped[int | None] = mapped_column(ForeignKey("payments.id"), nullable=True)
    subscription_id: Mapped[int | None] = mapped_column(ForeignKey("subscriptions.id"), nullable=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    amount_cents: Mapped[int] = mapped_column(Integer)
    tax_cents: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="CAD")
    status: Mapped[str] = mapped_column(String(20), default="open")  # draft|open|paid|void|refunded
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    provider_invoice_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
