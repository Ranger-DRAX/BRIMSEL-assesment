"""Pydantic schemas for API requests and responses."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class Level(str, Enum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"


class Mode(str, Enum):
    LEARNING = "learning"
    CONVERSATION = "conversation"
    ENGAGEMENT = "engagement"
    SUPPORT = "support"


class Action(str, Enum):
    LEARN = "learn"
    CHAT = "chat"
    PLAY = "play"
    BREAK = "break"
    STOP = "stop"
    HINT = "hint"
    SKIP = "skip"
    CONTINUE = "continue"
    ACCEPT_PROMOTION = "accept_promotion"
    DECLINE_PROMOTION = "decline_promotion"
    PLACEMENT = "placement"


class Source(str, Enum):
    GROQ = "groq"
    MOCK = "mock"
    CURRICULUM = "curriculum"
    FALLBACK = "fallback"


# --- Request schemas ---


class SessionCreateRequest(BaseModel):
    nickname: Optional[str] = Field(None, max_length=50)
    starting_level: Optional[Level] = Field(default=Level.L1)

    @field_validator("nickname")
    @classmethod
    def sanitize_nickname(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                return None
            # Don't allow anything that looks like personal info
            if len(v) > 50:
                v = v[:50]
        return v


class ChatRequest(BaseModel):
    request_id: str = Field(..., min_length=1, max_length=36)
    expected_revision: int = Field(..., ge=0)
    message: Optional[str] = Field(None, max_length=500)
    action: Optional[Action] = None
    activity_instance_id: Optional[str] = Field(None, max_length=36)
    answer_option_id: Optional[str] = Field(None, max_length=36)

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v


# --- Response schemas ---


class ActivityPayload(BaseModel):
    """Activity data exposed to the client (no answer key)."""
    activity_id: str
    instance_id: str
    activity_type: str
    prompt: str
    choices: Optional[list[dict]] = None
    skill: str
    level: str


class ChatResponse(BaseModel):
    request_id: str
    revision: int
    reply: str
    mode: str
    level: str
    suggested_replies: list[str] = Field(default_factory=list)
    activity: Optional[ActivityPayload] = None
    source: str
    fallback_reason: Optional[str] = None


class SessionResponse(BaseModel):
    nickname: Optional[str]
    level: str
    mode: str
    recent_messages: list[dict]
    active_activity: Optional[ActivityPayload] = None
    revision: int
    promotion_available: bool = False


class HealthResponse(BaseModel):
    status: str = "ok"
    timestamp: str


class ReadyResponse(BaseModel):
    status: str
    database: str
    config: str
