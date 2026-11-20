from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def now() -> datetime:
    return datetime.utcnow()


class Profile(Base):
    __tablename__ = "profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    native_language: Mapped[str] = mapped_column(String(10), default="fr")
    target_level: Mapped[str] = mapped_column(String(4), default="C1")
    estimated_level: Mapped[str] = mapped_column(String(4), default="B2")
    daily_minutes: Mapped[int] = mapped_column(Integer, default=60)
    accent_preference: Mapped[str] = mapped_column(String(10), default="en-CA")
    correction_mode: Mapped[str] = mapped_column(String(20), default="after_response")
    french_explanations: Mapped[int] = mapped_column(Integer, default=0)
    reminder_time: Mapped[str | None] = mapped_column(String(5), nullable=True)  # "19:00"
    placement_done_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Mistake(Base):
    """A single detected learner error, used to find recurring weaknesses."""

    __tablename__ = "mistakes"
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"), index=True)
    category: Mapped[str] = mapped_column(String(20))  # grammar|vocabulary|naturalness|pronunciation|fluency
    pattern: Mapped[str] = mapped_column(String(120))  # short label, e.g. "be + verb (am agree)"
    original: Mapped[str] = mapped_column(Text)
    corrected: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(20), default="conversation")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"), index=True)
    mode: Mapped[str] = mapped_column(String(40))
    correction_mode: Mapped[str] = mapped_column(String(20))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(10))  # user|assistant
    content: Mapped[str] = mapped_column(Text)
    feedback: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    speech_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class VocabCard(Base):
    """Spaced-repetition state for one word for one learner (SM-2)."""

    __tablename__ = "vocab_cards"
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"), index=True)
    word_id: Mapped[str] = mapped_column(String(60), index=True)
    ease: Mapped[float] = mapped_column(Float, default=2.5)
    interval_days: Mapped[int] = mapped_column(Integer, default=0)
    repetitions: Mapped[int] = mapped_column(Integer, default=0)
    lapses: Mapped[int] = mapped_column(Integer, default=0)
    due_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ActivityLog(Base):
    """Every graded activity; feeds the dashboard and level estimate."""

    __tablename__ = "activity_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"), index=True)
    skill: Mapped[str] = mapped_column(String(20))  # grammar|vocabulary|speaking|listening|reading|writing|pronunciation
    item_id: Mapped[str] = mapped_column(String(80))
    score: Mapped[float] = mapped_column(Float)  # 0..1
    seconds: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Bookmark(Base):
    __tablename__ = "bookmarks"
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    item_id: Mapped[str] = mapped_column(String(80))
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    route: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class VideoItem(Base):
    """A video in the learner's personal library: a local file or a YouTube embed, plus subtitles."""

    __tablename__ = "video_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    level: Mapped[str] = mapped_column(String(4), default="C1")
    source: Mapped[str] = mapped_column(String(10))  # file | youtube
    youtube_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    filename: Mapped[str | None] = mapped_column(String(200), nullable=True)
    cues: Mapped[list | None] = mapped_column(JSON, nullable=True)  # [{start, end, text}]
    study: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class ExamAttempt(Base):
    __tablename__ = "exam_attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"), index=True)
    exam_id: Mapped[str] = mapped_column(String(60))
    results: Mapped[dict] = mapped_column(JSON, default=dict)
    overall_band: Mapped[float | None] = mapped_column(Float, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
