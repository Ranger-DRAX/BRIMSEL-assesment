"""Chat orchestration service - the core turn handler."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.curriculum.loader import Curriculum, check_answer
from app.db.models import Session as DBSession, Turn
from app.db.repository import SessionRepository
from app.providers.groq_provider import ProviderError
from app.providers.interface import (
    SAFETY_RESPONSE,
    GenerationContext,
    LLMProvider,
    detect_safety_concern,
    redact_pii,
)
from app.schemas.api import (
    Action,
    ActivityPayload,
    ChatRequest,
    ChatResponse,
    Source,
)
from app.services.fallbacks import get_fallback_response
from app.services.mode_policy import (
    get_permitted_modes,
    resolve_mode,
)
from app.services.progress import (
    check_promotion_eligibility,
    get_next_level,
    should_offer_hint,
)

logger = logging.getLogger(__name__)


def compute_input_fingerprint(request: ChatRequest) -> str:
    """Compute a fingerprint of the input for idempotency checks."""
    data = json.dumps({
        "message": request.message,
        "action": request.action.value if request.action else None,
        "activity_instance_id": request.activity_instance_id,
        "answer_option_id": request.answer_option_id,
    }, sort_keys=True)
    return hashlib.sha256(data.encode()).hexdigest()


class ChatService:
    """Orchestrates the full chat turn lifecycle."""

    def __init__(
        self,
        settings: Settings,
        provider: LLMProvider,
        curriculum: Curriculum,
    ):
        self.settings = settings
        self.provider = provider
        self.curriculum = curriculum

    async def handle_turn(
        self,
        db: AsyncSession,
        session: DBSession,
        request: ChatRequest,
    ) -> ChatResponse:
        """Handle a complete chat turn with idempotency, deadlines, and atomic commits."""
        repo = SessionRepository(db)
        start_time = time.monotonic()

        # --- Idempotency check ---
        existing_turn = await repo.find_turn_by_request_id(session.id, request.request_id)
        if existing_turn:
            # Check fingerprint match
            expected_fp = compute_input_fingerprint(request)
            if existing_turn.input_fingerprint != expected_fp:
                raise ConflictError(
                    "Request ID already used with different input",
                    status_code=409,
                )
            # Return cached response
            if existing_turn.status == "completed" and existing_turn.response:
                cached = json.loads(existing_turn.response)
                return ChatResponse(**cached)
            elif existing_turn.status == "pending":
                raise ConflictError(
                    "Request is still being processed",
                    status_code=409,
                )
            elif existing_turn.status in ("failed", "abandoned"):
                # Allow retry with same request ID after failure
                pass

        # --- Revision check ---
        if request.expected_revision != session.revision:
            raise ConflictError(
                f"Stale revision: expected {request.expected_revision}, "
                f"current is {session.revision}. Please refresh session state.",
                status_code=409,
                resync=True,
            )

        # --- Check for in-flight turns ---
        if await repo.has_pending_turn(session.id):
            # Abandon stale pending turns
            await repo.abandon_pending_turns(session.id)

        # --- Create turn record (outside provider call) ---
        fingerprint = compute_input_fingerprint(request)
        turn = await repo.create_turn(
            session.id, request.request_id, fingerprint, session.revision
        )
        await db.commit()  # Commit turn creation separately

        turn_id = turn.id
        saved_session_id = session.id
        saved_mode = session.mode
        saved_revision = session.revision

        try:
            # --- Process the turn ---
            response = await self._process_turn(
                db, repo, session, request, start_time
            )

            # --- Atomic commit: response + state changes ---
            response_json = response.model_dump_json()
            await repo.complete_turn(turn, response_json)
            session.revision += 1
            await db.commit()

            return response

        except asyncio.TimeoutError:
            logger.warning(f"turn_timeout request_id={request.request_id}")
            await db.rollback()
            fallback = self._build_fallback_response(
                request, saved_mode, saved_revision, fallback_reason="timeout"
            )
            await repo.complete_turn_by_id_and_advance(
                saved_session_id,
                turn_id,
                fallback.model_dump_json(),
                user_msg=request.message,
                assistant_msg=fallback.reply,
            )
            await db.commit()
            return fallback

        except ProviderError as e:
            logger.warning(
                f"provider_error request_id={request.request_id} "
                f"type={e.error_type}"
            )
            await db.rollback()
            fallback = self._build_fallback_response(
                request, saved_mode, saved_revision, fallback_reason=e.error_type
            )
            await repo.complete_turn_by_id_and_advance(
                saved_session_id,
                turn_id,
                fallback.model_dump_json(),
                user_msg=request.message,
                assistant_msg=fallback.reply,
            )
            await db.commit()
            return fallback

        except Exception as e:
            logger.error(
                f"turn_error request_id={request.request_id} "
                f"type={type(e).__name__}"
            )
            await db.rollback()
            await repo.fail_turn_by_id(turn_id)
            await db.commit()
            raise

    async def _process_turn(
        self,
        db: AsyncSession,
        repo: SessionRepository,
        session: DBSession,
        request: ChatRequest,
        start_time: float,
    ) -> ChatResponse:
        """Process the turn: mode resolution, activity handling, provider call."""
        profile = await repo.get_profile(session.profile_id)
        if not profile:
            raise ValueError("Profile not found")

        message = request.message or ""
        action = request.action

        # --- PII redaction for provider ---
        redacted_message = redact_pii(message)

        # --- Safety check ---
        safety_concern = detect_safety_concern(message)
        if safety_concern:
            reply = SAFETY_RESPONSE
            await repo.append_messages(session, redacted_message, reply)
            session.mode = "support"
            return ChatResponse(
                request_id=request.request_id,
                revision=session.revision + 1,
                reply=reply,
                mode="support",
                level=profile.level,
                suggested_replies=["Take a break", "I'm okay", "Talk to a grown-up"],
                activity=None,
                source=Source.FALLBACK.value,
                fallback_reason=None,
            )

        # --- Mode resolution ---
        has_active = session.active_activity_id is not None
        mode, should_stop = resolve_mode(
            action, message, session.mode, has_active,
            session.consecutive_teaching_turns,
        )

        # Handle stop/break
        if should_stop and action != Action.SKIP:
            session.active_activity_id = None
            session.active_activity_instance_id = None
            session.consecutive_teaching_turns = 0
            session.mode = mode

            if action in (Action.STOP, Action.BREAK):
                if action == Action.BREAK:
                    reply = "Great idea to take a break! Come back whenever you're ready! 🌈"
                    suggestions = ["I'm back!", "Let's learn!", "Let's play!"]
                else:
                    reply = "Okay! We'll stop here. What would you like to do? 😊"
                    suggestions = ["Let's chat", "Start learning", "Play a game"]

                await repo.append_messages(session, redacted_message, reply)
                return ChatResponse(
                    request_id=request.request_id,
                    revision=session.revision + 1,
                    reply=reply,
                    mode=mode,
                    level=profile.level,
                    suggested_replies=suggestions,
                    activity=None,
                    source=Source.CURRICULUM.value,
                )

        # --- Promotion handling ---
        if action == Action.ACCEPT_PROMOTION:
            next_level = get_next_level(profile.level)
            if next_level and profile.promotion_offered:
                profile.level = next_level
                profile.promotion_offered = False
                profile.promotion_declined = False
                reply = f"Congratulations! You've moved up to {next_level}! 🎉🌟 Let's try some new activities!"
                await repo.append_messages(session, redacted_message, reply)
                session.mode = "learning"
                return ChatResponse(
                    request_id=request.request_id,
                    revision=session.revision + 1,
                    reply=reply,
                    mode="learning",
                    level=next_level,
                    suggested_replies=["Let's start!", "Show me!", "I'm ready!"],
                    activity=None,
                    source=Source.CURRICULUM.value,
                )

        if action == Action.DECLINE_PROMOTION:
            if profile.promotion_offered:
                profile.promotion_offered = False
                profile.promotion_declined = True
                reply = "That's totally fine! Let's keep practicing at this level. You're doing great! 🌟"
                await repo.append_messages(session, redacted_message, reply)
                return ChatResponse(
                    request_id=request.request_id,
                    revision=session.revision + 1,
                    reply=reply,
                    mode=session.mode,
                    level=profile.level,
                    suggested_replies=["Let's learn!", "Let's chat", "Play a game"],
                    activity=None,
                    source=Source.CURRICULUM.value,
                )

        # --- Hint handling ---
        is_hint = action == Action.HINT or (
            session.active_activity_id is not None
            and any(
                h in (message or "").lower().strip()
                for h in ["help me", "hint", "give me a hint", "need a hint", "clue", "i don't know", "i dont know"]
            )
        )
        if is_hint and session.active_activity_id:
            activity = self.curriculum.get_activity(session.active_activity_id)
            if activity:
                reply = f"Here's a hint: {activity.hint} 💡"
                await repo.append_messages(session, redacted_message, reply)

                activity_payload = ActivityPayload(
                    activity_id=activity.id,
                    instance_id=session.active_activity_instance_id or "",
                    activity_type=activity.type,
                    prompt=activity.prompt,
                    choices=[{"id": c.id, "text": c.text} for c in (activity.choices or [])],
                    skill=activity.skill,
                    level=activity.level,
                )
                return ChatResponse(
                    request_id=request.request_id,
                    revision=session.revision + 1,
                    reply=reply,
                    mode="learning",
                    level=profile.level,
                    suggested_replies=["I think I know!", "Another hint?", "Skip this one"],
                    activity=activity_payload,
                    source=Source.CURRICULUM.value,
                )

        # --- Skip handling ---
        if action == Action.SKIP:
            session.active_activity_id = None
            session.active_activity_instance_id = None
            # Pick a new activity
            return await self._start_new_activity(
                repo, session, profile, request, redacted_message
            )

        # --- Activity answer handling ---
        is_learn_request = action == Action.LEARN or (
            any(k in (message or "").lower() for k in ["teach me", "let's learn", "learn again", "start learning", "new lesson"])
        )
        if (
            has_active
            and mode == "learning"
            and not is_learn_request
            and (message or request.answer_option_id)
        ):
            return await self._handle_activity_answer(
                db, repo, session, profile, request, redacted_message
            )

        # --- Start learning activity ---
        if action == Action.LEARN or is_learn_request or (mode == "learning" and not has_active):
            return await self._start_new_activity(
                repo, session, profile, request, redacted_message
            )

        # --- Engagement ---
        is_play_request = action == Action.PLAY or (
            any(k in (message or "").lower() for k in ["let's play", "play a game", "play game", "new game", "another game"])
        )
        if is_play_request:
            game = self.curriculum.pick_game()
            session.mode = "engagement"
            session.active_activity_id = None
            session.active_activity_instance_id = None
            reply = f"Let's play! 🎮 {game.prompt}"
            await repo.append_messages(session, redacted_message, reply)
            return ChatResponse(
                request_id=request.request_id,
                revision=session.revision + 1,
                reply=reply,
                mode="engagement",
                level=profile.level,
                suggested_replies=["I know!", "Give me a clue!", "Different game"],
                activity=None,
                source=Source.CURRICULUM.value,
            )

        # --- Placement ---
        if action == Action.PLACEMENT:
            placement = self.curriculum.get_placement_activities()
            if placement:
                activity = placement[0]
                instance_id = self.curriculum.generate_instance_id()
                session.active_activity_id = activity.id
                session.active_activity_instance_id = instance_id
                session.mode = "learning"

                activity_payload = ActivityPayload(
                    activity_id=activity.id,
                    instance_id=instance_id,
                    activity_type=activity.type,
                    prompt=activity.prompt,
                    choices=[{"id": c.id, "text": c.text} for c in (activity.choices or [])],
                    skill=activity.skill,
                    level=activity.level,
                )

                reply = "Let's see what you already know! Here's a quick question 🌟"
                await repo.append_messages(session, redacted_message, reply)
                return ChatResponse(
                    request_id=request.request_id,
                    revision=session.revision + 1,
                    reply=reply,
                    mode="learning",
                    level=profile.level,
                    suggested_replies=[],
                    activity=activity_payload,
                    source=Source.CURRICULUM.value,
                )

        # --- Provider-based conversation ---
        deadline_s = self.settings.chat_deadline_ms / 1000.0
        elapsed = time.monotonic() - start_time
        remaining = max(0.1, deadline_s - elapsed)

        recent_messages = await repo.get_recent_messages(
            session, self.settings.max_history_messages
        )

        context = GenerationContext(
            level=profile.level,
            mode=mode,
            permitted_modes=get_permitted_modes(mode),
            recent_messages=recent_messages,
            new_message=redacted_message,
            skill_progress=json.loads(profile.skill_progress or "{}"),
            consecutive_teaching_turns=session.consecutive_teaching_turns,
            nickname=profile.nickname,
        )

        try:
            result = await asyncio.wait_for(
                self.provider.generate_reply(context),
                timeout=remaining,
            )

            # Backend controls the mode strictly based on mode_policy resolution
            final_mode = mode
            session.mode = final_mode
            session.consecutive_teaching_turns = 0

            await repo.append_messages(session, redacted_message, result.reply)

            return ChatResponse(
                request_id=request.request_id,
                revision=session.revision + 1,
                reply=result.reply,
                mode=final_mode,
                level=profile.level,
                suggested_replies=result.suggested_replies,
                activity=None,
                source=result.source,
            )
        except (asyncio.TimeoutError, ProviderError):
            raise

    async def _start_new_activity(
        self,
        repo: SessionRepository,
        session: DBSession,
        profile,
        request: ChatRequest,
        redacted_message: str,
    ) -> ChatResponse:
        """Start a new learning activity."""
        activity = self.curriculum.pick_activity(profile.level)
        instance_id = self.curriculum.generate_instance_id()

        session.active_activity_id = activity.id
        session.active_activity_instance_id = instance_id
        session.mode = "learning"
        session.consecutive_teaching_turns += 1

        activity_payload = ActivityPayload(
            activity_id=activity.id,
            instance_id=instance_id,
            activity_type=activity.type,
            prompt=activity.prompt,
            choices=[{"id": c.id, "text": c.text} for c in (activity.choices or [])],
            skill=activity.skill,
            level=activity.level,
        )

        reply = f"Here's a question for you! 📚 {activity.prompt}"
        await repo.append_messages(session, redacted_message, reply)

        return ChatResponse(
            request_id=request.request_id,
            revision=session.revision + 1,
            reply=reply,
            mode="learning",
            level=profile.level,
            suggested_replies=[],
            activity=activity_payload,
            source=Source.CURRICULUM.value,
        )

    async def _handle_activity_answer(
        self,
        db: AsyncSession,
        repo: SessionRepository,
        session: DBSession,
        profile,
        request: ChatRequest,
        redacted_message: str,
    ) -> ChatResponse:
        if not session.active_activity_id:
            return await self._start_new_activity(
                repo, session, profile, request, redacted_message
            )
        activity = self.curriculum.get_activity(session.active_activity_id)
        if not activity:
            session.active_activity_id = None
            session.active_activity_instance_id = None
            return await self._start_new_activity(
                repo, session, profile, request, redacted_message
            )

        # Validate instance ID if provided
        if (
            request.activity_instance_id
            and request.activity_instance_id != session.active_activity_instance_id
        ):
            raise ConflictError(
                "Stale activity instance. The activity may have changed.",
                status_code=409,
                resync=True,
            )

        # Determine the answer
        answer = request.answer_option_id or request.message or ""

        # Check the answer
        is_correct, is_recognized = check_answer(activity, answer)

        # Determine if this attempt was assisted (hint was used for this activity instance)
        hint_stmt = select(Turn).where(
            Turn.session_id == session.id,
            Turn.response.contains(session.active_activity_instance_id or ""),
            Turn.response.contains("Here's a hint:")
        )
        hint_res = await db.execute(hint_stmt)
        assisted = hint_res.scalars().first() is not None

        if is_recognized:
            result_str = "correct" if is_correct else "incorrect"

            # Record attempt (prevents duplicates via unique constraint)
            await repo.record_attempt(
                profile_id=profile.id,
                activity_id=activity.id,
                instance_id=session.active_activity_instance_id or "",
                result=result_str,
                assisted=assisted,
                skill=activity.skill,
                level=activity.level,
                turn_id=request.request_id,
            )

            if is_correct:
                reply = activity.feedback_correct
                session.active_activity_id = None
                session.active_activity_instance_id = None

                # Check promotion eligibility
                qualifying = await repo.get_qualifying_attempts(profile.id, profile.level)
                eligible, reason = check_promotion_eligibility(qualifying, profile.level)

                if eligible and not profile.promotion_offered and not profile.promotion_declined:
                    next_level = get_next_level(profile.level)
                    profile.promotion_offered = True
                    reply += f" 🎊 You've been doing amazing! Would you like to try {next_level} level activities?"
                    return ChatResponse(
                        request_id=request.request_id,
                        revision=session.revision + 1,
                        reply=reply,
                        mode="learning",
                        level=profile.level,
                        suggested_replies=["Yes, let's try!", "No, I'll stay here", "Maybe later"],
                        activity=None,
                        source=Source.CURRICULUM.value,
                    )

                suggestions = ["Next question!", "Let's chat", "Play a game"]
                await repo.append_messages(session, redacted_message, reply)

                return ChatResponse(
                    request_id=request.request_id,
                    revision=session.revision + 1,
                    reply=reply,
                    mode="learning",
                    level=profile.level,
                    suggested_replies=suggestions,
                    activity=None,
                    source=Source.CURRICULUM.value,
                )
            else:
                reply = activity.feedback_incorrect

                # Check if we should offer a hint
                recent = await repo.get_qualifying_attempts(profile.id, profile.level, limit=3)
                if should_offer_hint(recent):
                    reply += " Would you like a hint? 💡"

                activity_payload = ActivityPayload(
                    activity_id=activity.id,
                    instance_id=session.active_activity_instance_id or "",
                    activity_type=activity.type,
                    prompt=activity.prompt,
                    choices=[{"id": c.id, "text": c.text} for c in (activity.choices or [])],
                    skill=activity.skill,
                    level=activity.level,
                )

                await repo.append_messages(session, redacted_message, reply)
                return ChatResponse(
                    request_id=request.request_id,
                    revision=session.revision + 1,
                    reply=reply,
                    mode="learning",
                    level=profile.level,
                    suggested_replies=["Try again", "Give me a hint", "Skip"],
                    activity=activity_payload,
                    source=Source.CURRICULUM.value,
                )
        else:
            # Unrecognized free-form response
            reply = "I'm not sure about that answer. Could you try picking one of the choices? 🤔"
            activity_payload = ActivityPayload(
                activity_id=activity.id,
                instance_id=session.active_activity_instance_id or "",
                activity_type=activity.type,
                prompt=activity.prompt,
                choices=[{"id": c.id, "text": c.text} for c in (activity.choices or [])],
                skill=activity.skill,
                level=activity.level,
            )

            await repo.append_messages(session, redacted_message, reply)
            return ChatResponse(
                request_id=request.request_id,
                revision=session.revision + 1,
                reply=reply,
                mode="learning",
                level=profile.level,
                suggested_replies=["Try again", "Give me a hint", "Skip"],
                activity=activity_payload,
                source=Source.CURRICULUM.value,
            )

    def _build_fallback_response(
        self,
        request: ChatRequest,
        mode: str,
        revision: int,
        fallback_reason: Optional[str] = None,
    ) -> ChatResponse:
        """Build a fallback response when the provider fails."""
        reply, suggestions = get_fallback_response(mode)
        return ChatResponse(
            request_id=request.request_id,
            revision=revision + 1,
            reply=reply,
            mode=mode,
            level="L1",  # Safe default
            suggested_replies=suggestions,
            activity=None,
            source=Source.FALLBACK.value,
            fallback_reason=fallback_reason or "provider_error",
        )


class ConflictError(Exception):
    """Raised for revision/idempotency conflicts."""

    def __init__(self, message: str, status_code: int = 409, resync: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.resync = resync
