"""Database repository layer for async data access."""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ActivityAttempt, Profile, Session, Turn


def hash_credential(credential: str) -> str:
    """SHA-256 hash a session credential."""
    return hashlib.sha256(credential.encode()).hexdigest()


def generate_credential() -> str:
    """Generate a cryptographically random session credential."""
    return secrets.token_urlsafe(32)


class SessionRepository:
    """Repository for session and profile operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_profile_and_session(
        self,
        nickname: Optional[str],
        session_ttl_days: int,
        starting_level: str = "L1",
    ) -> tuple[Profile, Session, str]:
        """Create a new profile and session, returning the raw credential."""
        credential = generate_credential()
        credential_h = hash_credential(credential)

        profile = Profile(nickname=nickname, level=starting_level)
        self.db.add(profile)
        await self.db.flush()

        session = Session(
            credential_hash=credential_h,
            profile_id=profile.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=session_ttl_days),
        )
        self.db.add(session)
        await self.db.flush()

        return profile, session, credential

    async def get_session_by_credential(self, credential: str) -> Optional[Session]:
        """Look up a session by its raw credential."""
        credential_h = hash_credential(credential)
        result = await self.db.execute(
            select(Session)
            .where(Session.credential_hash == credential_h)
            .where(Session.expires_at > datetime.now(timezone.utc))
        )
        return result.scalar_one_or_none()

    async def get_profile(self, profile_id: str) -> Optional[Profile]:
        """Get a profile by ID."""
        result = await self.db.execute(select(Profile).where(Profile.id == profile_id))
        return result.scalar_one_or_none()

    async def reset_session(self, session: Session) -> None:
        """Reset learning progress for a session's profile."""
        profile = await self.get_profile(session.profile_id)
        if profile:
            profile.level = "L1"
            profile.skill_progress = "{}"
            profile.promotion_offered = False
            profile.promotion_declined = False

        # Delete activity attempts
        await self.db.execute(
            delete(ActivityAttempt).where(ActivityAttempt.profile_id == session.profile_id)
        )

        session.mode = "conversation"
        session.active_activity_id = None
        session.active_activity_instance_id = None
        session.consecutive_teaching_turns = 0
        session.recent_messages = "[]"
        session.revision += 1

        await self.db.flush()

    async def delete_session_and_profile(self, session: Session) -> None:
        """Delete a session and its associated profile (cascade)."""
        profile = await self.get_profile(session.profile_id)
        if profile:
            await self.db.delete(profile)
        await self.db.flush()

    async def get_recent_messages(self, session: Session, max_messages: int) -> list[dict]:
        """Parse and return bounded recent messages."""
        try:
            parsed = json.loads(session.recent_messages or "[]")
            messages: list[dict] = parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            messages = []
        return list(messages[-max_messages:])

    async def append_messages(
        self, session: Session, user_msg: str, assistant_msg: str, max_retain: int = 20
    ) -> None:
        """Append user and assistant messages, retaining at most max_retain."""
        try:
            messages = json.loads(session.recent_messages or "[]")
        except json.JSONDecodeError:
            messages = []

        messages.append({"role": "user", "content": user_msg})
        messages.append({"role": "assistant", "content": assistant_msg})
        messages = messages[-max_retain:]
        session.recent_messages = json.dumps(messages)

    async def find_turn_by_request_id(
        self, session_id: str, request_id: str
    ) -> Optional[Turn]:
        """Find an existing turn by request_id within a session."""
        result = await self.db.execute(
            select(Turn)
            .where(Turn.session_id == session_id)
            .where(Turn.request_id == request_id)
        )
        return result.scalar_one_or_none()

    async def has_pending_turn(self, session_id: str) -> bool:
        """Check if there's a pending turn for this session."""
        result = await self.db.execute(
            select(Turn)
            .where(Turn.session_id == session_id)
            .where(Turn.status == "pending")
        )
        return result.scalar_one_or_none() is not None

    async def create_turn(
        self, session_id: str, request_id: str, input_fingerprint: str, revision: int
    ) -> Turn:
        """Create a new turn record, or reuse an existing failed/abandoned turn."""
        existing = await self.find_turn_by_request_id(session_id, request_id)
        if existing:
            existing.input_fingerprint = input_fingerprint
            existing.revision = revision
            existing.status = "pending"
            existing.response = None
            existing.completed_at = None
            await self.db.flush()
            return existing

        turn = Turn(
            request_id=request_id,
            session_id=session_id,
            input_fingerprint=input_fingerprint,
            revision=revision,
        )
        self.db.add(turn)
        await self.db.flush()
        return turn

    async def complete_turn(self, turn: Turn, response_json: str) -> None:
        """Mark a turn as completed with a response."""
        turn.status = "completed"
        turn.response = response_json
        turn.completed_at = datetime.now(timezone.utc)
        await self.db.flush()

    async def complete_turn_by_id_and_advance(
        self,
        session_id: str,
        turn_id: str,
        response_json: str,
        user_msg: Optional[str] = None,
        assistant_msg: Optional[str] = None,
        max_retain: int = 20,
    ) -> None:
        """Mark turn completed with fallback response and advance session revision."""
        await self.db.execute(
            update(Turn)
            .where(Turn.id == turn_id)
            .values(
                status="completed",
                response=response_json,
                completed_at=datetime.now(timezone.utc),
            )
        )

        update_values: dict = {
            "revision": Session.revision + 1,
            "updated_at": datetime.now(timezone.utc),
        }

        if user_msg and assistant_msg:
            result = await self.db.execute(
                select(Session.recent_messages).where(Session.id == session_id)
            )
            raw = result.scalar_one_or_none()
            try:
                messages = json.loads(raw or "[]")
                if not isinstance(messages, list):
                    messages = []
            except Exception:
                messages = []
            messages.append({"role": "user", "content": user_msg})
            messages.append({"role": "assistant", "content": assistant_msg})
            messages = messages[-max_retain:]
            update_values["recent_messages"] = json.dumps(messages)

        await self.db.execute(
            update(Session)
            .where(Session.id == session_id)
            .values(**update_values)
        )

    async def fail_turn(self, turn: Turn) -> None:
        """Mark a turn as failed."""
        turn.status = "failed"
        turn.completed_at = datetime.now(timezone.utc)
        await self.db.flush()

    async def fail_turn_by_id(self, turn_id: str) -> None:
        """Mark a turn as failed by its ID without touching expired ORM models."""
        await self.db.execute(
            update(Turn)
            .where(Turn.id == turn_id)
            .values(status="failed", completed_at=datetime.now(timezone.utc))
        )

    async def abandon_pending_turns(self, session_id: str) -> int:
        """Abandon any pending turns for a session (e.g., after restart)."""
        result = await self.db.execute(
            update(Turn)
            .where(Turn.session_id == session_id)
            .where(Turn.status == "pending")
            .values(status="abandoned", completed_at=datetime.now(timezone.utc))
        )
        return result.rowcount

    async def record_attempt(
        self,
        profile_id: str,
        activity_id: str,
        instance_id: str,
        result: str,
        assisted: bool,
        skill: str,
        level: str,
        turn_id: Optional[str] = None,
    ) -> Optional[ActivityAttempt]:
        """Record an activity attempt. Returns None if duplicate instance."""
        # Check for duplicate
        existing = await self.db.execute(
            select(ActivityAttempt)
            .where(ActivityAttempt.instance_id == instance_id)
            .where(ActivityAttempt.profile_id == profile_id)
        )
        if existing.scalar_one_or_none() is not None:
            return None  # Duplicate

        attempt = ActivityAttempt(
            profile_id=profile_id,
            activity_id=activity_id,
            instance_id=instance_id,
            result=result,
            assisted=assisted,
            skill=skill,
            level=level,
            turn_id=turn_id,
        )
        self.db.add(attempt)
        await self.db.flush()
        return attempt

    async def get_qualifying_attempts(
        self, profile_id: str, level: str, limit: int = 10
    ) -> list[ActivityAttempt]:
        """Get the latest qualifying (scored, unassisted) attempts for a level."""
        result = await self.db.execute(
            select(ActivityAttempt)
            .where(ActivityAttempt.profile_id == profile_id)
            .where(ActivityAttempt.level == level)
            .where(ActivityAttempt.assisted == False)  # noqa: E712
            .where(ActivityAttempt.result.in_(["correct", "incorrect"]))
            .order_by(ActivityAttempt.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def cleanup_expired_sessions(self, batch_size: int = 100) -> int:
        """Delete expired sessions (cascades to turns)."""
        result = await self.db.execute(
            delete(Session)
            .where(Session.expires_at <= datetime.now(timezone.utc))
        )
        return result.rowcount
