"""API route handlers."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repository import SessionRepository
from app.schemas.api import (
    ActivityPayload,
    ChatRequest,
    ChatResponse,
    HealthResponse,
    ReadyResponse,
    SessionCreateRequest,
    SessionResponse,
)
from app.services.chat import ChatService, ConflictError

logger = logging.getLogger(__name__)

router = APIRouter()

COOKIE_NAME = "eb_session"


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get a database session."""
    async with request.app.state.session_factory() as session:
        yield session


async def get_session(
    request: Request,
    db: AsyncSession = Depends(get_db),
    eb_session: str | None = Cookie(None),
):
    """Dependency to get the current authenticated session."""
    if not eb_session:
        raise HTTPException(status_code=401, detail="No session cookie")

    repo = SessionRepository(db)
    session = await repo.get_session_by_credential(eb_session)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    return session


def set_session_cookie(response: Response, credential: str, settings) -> None:
    """Set the session cookie with appropriate security attributes."""
    response.set_cookie(
        key=COOKIE_NAME,
        value=credential,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.session_ttl_days * 86400,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    """Clear the session cookie."""
    response.delete_cookie(key=COOKIE_NAME, path="/")


def check_origin(request: Request) -> None:
    """Check Origin header for CSRF protection on mutations."""
    settings = request.app.state.settings
    origin = request.headers.get("origin")
    if origin and origin not in settings.frontend_origins:
        raise HTTPException(status_code=403, detail="Origin mismatch")


# --- Health endpoints ---

@router.get("/health", response_model=HealthResponse)
async def health():
    """Process health check - no secrets."""
    return HealthResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/ready", response_model=ReadyResponse)
async def ready(request: Request, db: AsyncSession = Depends(get_db)):
    """Readiness check - verifies database connectivity."""
    try:
        from sqlalchemy import text
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"

    config_status = "ok" if request.app.state.settings else "error"

    status = "ok" if db_status == "ok" and config_status == "ok" else "degraded"
    return ReadyResponse(status=status, database=db_status, config=config_status)


# --- Session endpoints ---

@router.post("/api/session", response_model=SessionResponse)
async def create_session(
    body: SessionCreateRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Initialize a new profile and session."""
    check_origin(request)
    settings = request.app.state.settings

    repo = SessionRepository(db)
    level_val = body.starting_level.value if body.starting_level else "L1"
    profile, session, credential = await repo.create_profile_and_session(
        nickname=body.nickname,
        session_ttl_days=settings.session_ttl_days,
        starting_level=level_val,
    )
    await db.commit()

    set_session_cookie(response, credential, settings)

    return SessionResponse(
        nickname=profile.nickname,
        level=profile.level,
        mode=session.mode,
        recent_messages=[],
        active_activity=None,
        revision=session.revision,
    )


@router.get("/api/session", response_model=SessionResponse)
async def get_session_state(
    request: Request,
    db: AsyncSession = Depends(get_db),
    session=Depends(get_session),
):
    """Get current session state including progress and recent messages."""
    repo = SessionRepository(db)
    profile = await repo.get_profile(session.profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    messages = await repo.get_recent_messages(session, request.app.state.settings.max_history_messages)

    # Build active activity payload if present
    active_activity = None
    if session.active_activity_id:
        curriculum = request.app.state.curriculum
        activity = curriculum.get_activity(session.active_activity_id)
        if activity:
            active_activity = ActivityPayload(
                activity_id=activity.id,
                instance_id=session.active_activity_instance_id or "",
                activity_type=activity.type,
                prompt=activity.prompt,
                choices=[{"id": c.id, "text": c.text} for c in (activity.choices or [])],
                skill=activity.skill,
                level=activity.level,
            )

    # Check promotion eligibility
    qualifying = await repo.get_qualifying_attempts(profile.id, profile.level)
    from app.services.progress import check_promotion_eligibility
    eligible, _ = check_promotion_eligibility(qualifying, profile.level)

    return SessionResponse(
        nickname=profile.nickname,
        level=profile.level,
        mode=session.mode,
        recent_messages=messages,
        active_activity=active_activity,
        revision=session.revision,
        promotion_available=eligible and profile.promotion_offered,
    )


@router.post("/api/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    session=Depends(get_session),
):
    """Submit a chat turn."""
    check_origin(request)
    settings = request.app.state.settings

    # Validate message length
    if body.message and len(body.message) > settings.max_input_chars:
        raise HTTPException(
            status_code=400,
            detail=f"Message too long (max {settings.max_input_chars} characters)",
        )

    # Must have either message or action
    if not body.message and not body.action:
        raise HTTPException(status_code=400, detail="Message or action required")

    chat_service: ChatService = request.app.state.chat_service

    try:
        response = await chat_service.handle_turn(db, session, body)
        return response
    except ConflictError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        logger.error(f"chat_error type={type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred processing your message")


@router.post("/api/session/reset")
async def reset_session(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    session=Depends(get_session),
):
    """Reset learning progress. Requires explicit UI confirmation."""
    check_origin(request)

    repo = SessionRepository(db)
    await repo.reset_session(session)
    await db.commit()

    return {"status": "ok", "message": "Learning progress has been reset"}


@router.delete("/api/session")
async def delete_session(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    session=Depends(get_session),
):
    """Delete profile and session data, clear cookie."""
    check_origin(request)

    repo = SessionRepository(db)
    await repo.delete_session_and_profile(session)
    await db.commit()

    clear_session_cookie(response)

    return {"status": "ok", "message": "All data has been deleted"}
