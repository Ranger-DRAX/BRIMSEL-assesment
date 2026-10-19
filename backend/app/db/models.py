"""SQLAlchemy ORM models for the application."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def gen_uuid() -> str:
    return str(uuid.uuid4())


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    nickname: Mapped[str | None] = mapped_column(String(50), nullable=True)
    level: Mapped[str] = mapped_column(String(2), default="L1", nullable=False)
    # JSON-encoded compact skill progress: {"vocabulary": 5, "grammar": 3, ...}
    skill_progress: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    promotion_offered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    promotion_declined: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    sessions: Mapped[list["Session"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    activity_attempts: Mapped[list["ActivityAttempt"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    credential_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    mode: Mapped[str] = mapped_column(String(20), default="conversation", nullable=False)
    active_activity_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    active_activity_instance_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    consecutive_teaching_turns: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # JSON-encoded recent messages: [{"role": "user"|"assistant", "content": "..."}]
    recent_messages: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    profile: Mapped["Profile"] = relationship(back_populates="sessions")
    turns: Mapped[list["Turn"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_sessions_credential_hash", "credential_hash"),)


class ActivityAttempt(Base):
    __tablename__ = "activity_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    activity_id: Mapped[str] = mapped_column(String(50), nullable=False)
    instance_id: Mapped[str] = mapped_column(String(36), nullable=False)
    result: Mapped[str] = mapped_column(String(20), nullable=False)  # correct, incorrect, skipped
    assisted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    skill: Mapped[str] = mapped_column(String(50), nullable=False)
    level: Mapped[str] = mapped_column(String(2), nullable=False)
    turn_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    profile: Mapped["Profile"] = relationship(back_populates="activity_attempts")

    __table_args__ = (
        Index("ix_activity_attempts_profile_level", "profile_id", "level"),
        # Prevent duplicate scoring for the same instance
        UniqueConstraint("instance_id", "profile_id", name="uq_attempt_instance_profile"),
    )


class Turn(Base):
    __tablename__ = "turns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )  # pending, completed, failed, abandoned
    response: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON-encoded response
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped["Session"] = relationship(back_populates="turns")

    __table_args__ = (
        UniqueConstraint("request_id", "session_id", name="uq_turn_request_session"),
        Index("ix_turns_session_status", "session_id", "status"),
    )
