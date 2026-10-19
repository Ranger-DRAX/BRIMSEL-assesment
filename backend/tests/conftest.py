"""Pytest fixtures for backend tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import AppEnv, LLMProvider, Settings
from app.curriculum.loader import get_curriculum
from app.db.engine import create_session_factory
from app.db.models import Base
from app.main import create_app
from app.providers.mock import MockProvider
from app.services.chat import ChatService


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    """Create test settings with a temporary SQLite database."""
    db_path = tmp_path / "test.db"
    return Settings(
        app_env=AppEnv.TEST,
        llm_provider=LLMProvider.MOCK,
        database_url=f"sqlite+aiosqlite:///{db_path}",
        frontend_origin="http://localhost:3000",
        provider_timeout_ms=1000,
        chat_deadline_ms=2000,
        max_input_chars=500,
        max_history_messages=8,
        session_ttl_days=30,
        enable_live_eval=False,
    )


@pytest_asyncio.fixture
async def test_engine(test_settings: Settings):
    """Create test database engine and tables."""
    engine = create_async_engine(
        test_settings.database_url,
        connect_args={"timeout": 10},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session_factory(test_engine):
    """Create test session factory."""
    return create_session_factory(test_engine)


@pytest_asyncio.fixture
async def test_db(test_session_factory) -> AsyncGenerator[AsyncSession, None]:
    """Provide a test database session."""
    async with test_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def app_client(test_settings: Settings, test_engine, test_session_factory):
    """Create an AsyncClient wired to the test FastAPI app."""
    app = create_app()
    app.state.settings = test_settings
    app.state.engine = test_engine
    app.state.session_factory = test_session_factory
    curriculum = get_curriculum()
    app.state.curriculum = curriculum
    provider = MockProvider()
    app.state.provider = provider
    app.state.chat_service = ChatService(test_settings, provider, curriculum)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
