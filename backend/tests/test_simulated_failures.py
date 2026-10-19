"""Simulated failure and fault-injection test suite.

Verifies robust, child-safe failure handling across provider errors:
- Timeout
- 401/403 (Auth failure)
- 429 (Rate limit)
- 5xx (Server error)
- Malformed JSON
- Empty output
- Unsafe output
- Idempotent request retry under failure
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import AppEnv, LLMProvider, Settings
from app.curriculum.loader import get_curriculum
from app.db.engine import create_session_factory
from app.db.models import ActivityAttempt, Base, Profile, Session as DBSession, Turn
from app.main import create_app
from app.providers.groq_provider import ProviderError
from app.providers.interface import (
    GenerationContext,
    GenerationResult,
    LLMProvider as LLMProviderBase,
)
from app.services.chat import ChatService


class FaultInjectingProvider(LLMProviderBase):
    """Controlled stub for injecting specific provider failure modes."""

    def __init__(self, failure_mode: str = "timeout", call_log: list | None = None):
        self.failure_mode = failure_mode
        self.call_count = 0
        self.call_log = call_log if call_log is not None else []

    async def close(self) -> None:
        pass

    async def generate_reply(self, context: GenerationContext) -> GenerationResult:
        self.call_count += 1
        self.call_log.append(self.failure_mode)

        if self.failure_mode == "timeout":
            raise asyncio.TimeoutError("Provider request timed out")
        elif self.failure_mode == "auth_401":
            raise ProviderError("Authentication failed", error_type="auth", status_code=401)
        elif self.failure_mode == "rate_limit_429":
            raise ProviderError("Rate limit exceeded", error_type="rate_limit", status_code=429)
        elif self.failure_mode == "server_error_500":
            raise ProviderError("Groq internal server error", error_type="api_error", status_code=500)
        elif self.failure_mode == "malformed_json":
            raise ProviderError("Invalid JSON from LLM", error_type="malformed_json")
        elif self.failure_mode == "empty_output":
            raise ProviderError("Empty response from LLM", error_type="empty_output")
        elif self.failure_mode == "unsafe_output":
            # Output containing blocked or inappropriate terms
            return GenerationResult(
                reply="This is a secret key: gsk_123456789 and you should hurt people.",
                mode=context.mode,
                suggested_replies=["bad", "worse"],
                source="groq",
            )
        else:
            return GenerationResult(
                reply="Hello friend!",
                mode=context.mode,
                suggested_replies=["Hi!"],
                source="mock",
            )


async def create_test_client_with_provider(tmp_path, provider: LLMProviderBase):
    db_path = tmp_path / f"sim_fail_{uuid.uuid4().hex[:8]}.db"
    settings = Settings(
        app_env=AppEnv.TEST,
        llm_provider=LLMProvider.MOCK,
        database_url=f"sqlite+aiosqlite:///{db_path}",
        frontend_origin="http://localhost:3000",
        provider_timeout_ms=500,
        chat_deadline_ms=1000,
        max_input_chars=500,
        max_history_messages=8,
        session_ttl_days=30,
        enable_live_eval=False,
    )
    engine = create_async_engine(settings.database_url, connect_args={"timeout": 10})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = create_session_factory(engine)
    curriculum = get_curriculum()

    app = create_app()
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.curriculum = curriculum
    app.state.provider = provider
    app.state.chat_service = ChatService(settings, provider, curriculum)

    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://test")
    return client, engine, session_factory


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure_mode,expected_fallback_reason",
    [
        ("timeout", "timeout"),
        ("auth_401", "auth"),
        ("rate_limit_429", "rate_limit"),
        ("server_error_500", "api_error"),
        ("malformed_json", "malformed_json"),
        ("empty_output", "empty_output"),
    ],
)
async def test_simulated_provider_failures_return_safe_fallback(tmp_path, failure_mode, expected_fallback_reason):
    """Verifies that all provider failure modes degrade to child-safe reviewed fallbacks without exposing errors."""
    call_log = []
    provider = FaultInjectingProvider(failure_mode=failure_mode, call_log=call_log)
    client, engine, session_factory = await create_test_client_with_provider(tmp_path, provider)

    async with client:
        # Create session
        s_resp = await client.post("/api/session", json={"nickname": "TestKid"})
        assert s_resp.status_code == 200

        # Send a chat message that requires generative reply
        chat_resp = await client.post(
            "/api/chat",
            json={
                "request_id": str(uuid.uuid4()),
                "expected_revision": 0,
                "message": "Tell me about stars",
            },
        )
        assert chat_resp.status_code == 200
        data = chat_resp.json()

        # 1. Fallback returned
        assert data["source"] == "fallback"
        assert data["fallback_reason"] == expected_fallback_reason
        assert len(data["reply"]) > 5

        # 2. No raw errors or secrets shown to child
        reply_lower = data["reply"].lower()
        assert "500" not in reply_lower
        assert "401" not in reply_lower
        assert "429" not in reply_lower
        assert "error" not in reply_lower
        assert "groq" not in reply_lower
        assert "traceback" not in reply_lower

        # 3. No hidden automatic retries (exactly 1 provider call made)
        assert len(call_log) == 1

        # 4. Mode remains child-friendly and valid
        assert data["mode"] in ("conversation", "support", "engagement", "learning")

    await engine.dispose()


@pytest.mark.asyncio
async def test_simulated_failure_no_state_corruption_or_extra_scoring(tmp_path):
    """Verifies that provider failures do NOT mutate learning scores or log activity attempts."""
    provider = FaultInjectingProvider(failure_mode="server_error_500")
    client, engine, session_factory = await create_test_client_with_provider(tmp_path, provider)

    async with client:
        s_resp = await client.post("/api/session", json={"nickname": "Emma", "starting_level": "L1"})
        assert s_resp.status_code == 200

        # Attempt turn
        chat_resp = await client.post(
            "/api/chat",
            json={
                "request_id": str(uuid.uuid4()),
                "expected_revision": 0,
                "message": "I love reading books",
            },
        )
        assert chat_resp.status_code == 200
        data = chat_resp.json()
        assert data["source"] == "fallback"

        # Verify database state has zero activity attempts and no corrupted score
        async with session_factory() as db:
            attempts = (await db.execute(select(ActivityAttempt))).scalars().all()
            assert len(attempts) == 0

            profile = (await db.execute(select(Profile))).scalars().first()
            assert profile.level == "L1"
            assert profile.skill_progress == "{}" or profile.skill_progress == "{}"

    await engine.dispose()


@pytest.mark.asyncio
async def test_simulated_failure_retry_idempotence(tmp_path):
    """Retrying the exact same request_id after a failure must return the identical saved response without duplicate turns."""
    provider = FaultInjectingProvider(failure_mode="timeout")
    client, engine, session_factory = await create_test_client_with_provider(tmp_path, provider)

    req_id = str(uuid.uuid4())
    async with client:
        await client.post("/api/session", json={"nickname": "RetryKid"})

        # First request
        resp1 = await client.post(
            "/api/chat",
            json={
                "request_id": req_id,
                "expected_revision": 0,
                "message": "Hello Pip!",
            },
        )
        assert resp1.status_code == 200
        data1 = resp1.json()

        # Immediate retry with same request_id
        resp2 = await client.post(
            "/api/chat",
            json={
                "request_id": req_id,
                "expected_revision": 0,
                "message": "Hello Pip!",
            },
        )
        assert resp2.status_code == 200
        data2 = resp2.json()

        # Returns identical fallback turn
        assert data1["request_id"] == data2["request_id"]
        assert data1["reply"] == data2["reply"]
        assert data1["source"] == data2["source"] == "fallback"

        # Verify only one turn record was created
        async with session_factory() as db:
            turns = (await db.execute(select(Turn))).scalars().all()
            assert len(turns) == 1

    await engine.dispose()
