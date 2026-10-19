"""Tests for configuration and environment validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import AppEnv, LLMProvider, Settings


def test_mock_mode_without_key():
    """Mock mode must succeed without any API key."""
    settings = Settings(
        llm_provider=LLMProvider.MOCK,
        groq_api_key=None,
    )
    assert settings.llm_provider == LLMProvider.MOCK
    assert settings.groq_api_key is None


def test_live_groq_mode_without_key_fails():
    """Live Groq mode without key must fail with a clear configuration error."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            llm_provider=LLMProvider.GROQ,
            groq_api_key=None,
        )
    assert "GROQ_API_KEY is required" in str(exc_info.value)


def test_live_groq_mode_with_empty_key_fails():
    """Live Groq mode with empty/whitespace key must fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            llm_provider=LLMProvider.GROQ,
            groq_api_key="   ",
        )
    assert "GROQ_API_KEY is required" in str(exc_info.value)


def test_invalid_provider_timeout():
    """Timeout below minimum or above maximum must fail validation."""
    with pytest.raises(ValidationError):
        Settings(provider_timeout_ms=50)

    with pytest.raises(ValidationError):
        Settings(provider_timeout_ms=50000)


def test_invalid_chat_deadline():
    """Chat deadline below minimum or above maximum must fail validation."""
    with pytest.raises(ValidationError):
        Settings(chat_deadline_ms=50)

    with pytest.raises(ValidationError):
        Settings(chat_deadline_ms=50000)


def test_invalid_max_input_chars():
    """Input length limits must be validated."""
    with pytest.raises(ValidationError):
        Settings(max_input_chars=0)

    with pytest.raises(ValidationError):
        Settings(max_input_chars=10000)


def test_invalid_max_history_messages():
    """History message limit must be bounded."""
    with pytest.raises(ValidationError):
        Settings(max_history_messages=0)

    with pytest.raises(ValidationError):
        Settings(max_history_messages=100)


def test_cookie_attributes_dev_vs_prod():
    """Cookie Secure flag must be False in development and True in production."""
    dev_settings = Settings(app_env=AppEnv.DEVELOPMENT)
    assert dev_settings.cookie_secure is False
    assert dev_settings.cookie_samesite == "lax"

    prod_settings = Settings(
        app_env=AppEnv.PRODUCTION,
        llm_provider=LLMProvider.MOCK,
    )
    assert prod_settings.cookie_secure is True


def test_sqlite_path_resolution():
    """SQLite path resolution must handle relative paths."""
    settings = Settings(database_url="sqlite+aiosqlite:///./data/test.db")
    path = settings.get_sqlite_path()
    assert path is not None
    assert str(path).endswith("test.db")


@pytest.mark.parametrize("scheme", ["postgres", "postgresql", "postgresql+asyncpg"])
def test_hosted_postgres_url(scheme):
    settings = Settings(
        database_url=f"{scheme}://user:p%40ss@db.example/app?sslmode=require&channel_binding=require"
    )
    assert settings.database_url == "postgresql+asyncpg://user:p%40ss@db.example/app?ssl=require"
    assert settings.get_sqlite_path() is None
