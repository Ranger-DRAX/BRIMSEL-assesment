"""Application configuration with Pydantic settings and validation."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class AppEnv(str, Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TEST = "test"


class LLMProvider(str, Enum):
    MOCK = "mock"
    GROQ = "groq"


def _resolve_backend_root() -> Path:
    """Resolve the backend root directory consistently regardless of launch directory."""
    return Path(__file__).resolve().parent.parent


BACKEND_ROOT = _resolve_backend_root()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: AppEnv = AppEnv.DEVELOPMENT
    llm_provider: LLMProvider = LLMProvider.MOCK
    groq_api_key: Optional[str] = None
    groq_model: str = "openai/gpt-oss-20b"
    database_url: str = f"sqlite+aiosqlite:///{BACKEND_ROOT / 'data' / 'english_buddy.db'}"
    frontend_origin: str = "http://localhost:3000"
    provider_timeout_ms: int = 1600
    chat_deadline_ms: int = 2400
    max_input_chars: int = 500
    max_history_messages: int = 8
    session_ttl_days: int = 30
    enable_live_eval: bool = False

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        """Accept hosted PostgreSQL URLs with the async driver and TLS options."""
        url = make_url(value)
        if url.drivername in {"postgres", "postgresql", "postgresql+asyncpg"}:
            query = dict(url.query)
            if "sslmode" in query:
                query["ssl"] = query.pop("sslmode")
            # libpq's channel_binding option is not an asyncpg argument.
            query.pop("channel_binding", None)
            return url.set(drivername="postgresql+asyncpg", query=query).render_as_string(
                hide_password=False
            )
        return value

    @field_validator("provider_timeout_ms", "chat_deadline_ms")
    @classmethod
    def validate_timeouts(cls, v: int, info) -> int:
        if v < 100 or v > 30000:
            raise ValueError(f"{info.field_name} must be between 100 and 30000, got {v}")
        return v

    @field_validator("max_input_chars")
    @classmethod
    def validate_max_input(cls, v: int) -> int:
        if v < 1 or v > 5000:
            raise ValueError(f"max_input_chars must be between 1 and 5000, got {v}")
        return v

    @field_validator("max_history_messages")
    @classmethod
    def validate_max_history(cls, v: int) -> int:
        if v < 1 or v > 50:
            raise ValueError(f"max_history_messages must be between 1 and 50, got {v}")
        return v

    @field_validator("session_ttl_days")
    @classmethod
    def validate_session_ttl(cls, v: int) -> int:
        if v < 1 or v > 365:
            raise ValueError(f"session_ttl_days must be between 1 and 365, got {v}")
        return v

    @field_validator("groq_api_key")
    @classmethod
    def sanitize_key(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v

    @model_validator(mode="after")
    def validate_groq_key_required(self) -> "Settings":
        if self.llm_provider == LLMProvider.GROQ and not self.groq_api_key:
            raise ValueError(
                "GROQ_API_KEY is required when LLM_PROVIDER=groq. "
                "Please set a valid Groq API key in your .env file."
            )
        return self

    @property
    def frontend_origins(self) -> list[str]:
        """Explicit origins shared by CORS and mutation origin checks."""
        return [origin.strip() for origin in self.frontend_origin.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == AppEnv.PRODUCTION

    @property
    def cookie_secure(self) -> bool:
        return self.is_production

    @property
    def cookie_samesite(self) -> str:
        return "lax"

    def get_sqlite_path(self) -> Optional[Path]:
        """Extract the SQLite file path from the database URL, if applicable."""
        if "sqlite" in self.database_url:
            # Handle sqlite+aiosqlite:///./data/english_buddy.db
            path_part = self.database_url.split("///")[-1]
            if path_part.startswith("./"):
                return BACKEND_ROOT / path_part[2:]
            return Path(path_part)
        return None


def get_settings() -> Settings:
    """Create and return a validated Settings instance."""
    return Settings()
