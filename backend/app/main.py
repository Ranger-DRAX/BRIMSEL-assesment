"""FastAPI application factory and lifespan management."""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.config import LLMProvider as LLMProviderConfig
from app.config import get_settings
from app.curriculum.loader import get_curriculum
from app.db.engine import create_engine, create_session_factory
from app.db.models import Base
from app.providers.groq_provider import GroqProvider
from app.providers.interface import LLMProvider
from app.providers.mock import MockProvider
from app.services.chat import ChatService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# Filter out sensitive data from logs
class SensitiveFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = str(record.msg)
        # Block any log that contains API keys or cookie values
        sensitive_patterns = ["gsk_", "GROQ_API_KEY=", "eb_session="]
        for pattern in sensitive_patterns:
            if pattern in msg:
                record.msg = "[REDACTED - sensitive data filtered]"
                break
        return True


for handler in logging.root.handlers:
    handler.addFilter(SensitiveFilter())


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    settings = get_settings()
    app.state.settings = settings

    logger.info(f"Starting English Buddy (env={settings.app_env.value}, provider={settings.llm_provider.value})")

    # Ensure data directory exists for SQLite
    sqlite_path = settings.get_sqlite_path()
    if sqlite_path:
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    # Create database engine and tables
    engine = create_engine(settings)
    app.state.engine = engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app.state.session_factory = create_session_factory(engine)

    # Load and validate curriculum
    curriculum = get_curriculum()
    app.state.curriculum = curriculum
    logger.info(
        f"Curriculum loaded: {sum(len(v) for v in curriculum.by_level.values())} activities, "
        f"{len(curriculum.engagement_games)} games"
    )

    # Initialize LLM provider
    provider: LLMProvider
    if settings.llm_provider == LLMProviderConfig.GROQ:
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is required when LLM_PROVIDER=groq")
        provider = GroqProvider(
            api_key=settings.groq_api_key,
            model=settings.groq_model,
            timeout_ms=settings.provider_timeout_ms,
        )
        logger.info(f"Groq provider initialized (model={settings.groq_model})")
    else:
        provider = MockProvider()
        logger.info("Mock provider initialized")

    app.state.provider = provider

    # Create chat service
    app.state.chat_service = ChatService(settings, provider, curriculum)

    yield

    # Shutdown
    await provider.close()
    await engine.dispose()
    logger.info("English Buddy shut down cleanly")


def create_app() -> FastAPI:
    """Create the FastAPI application."""
    app = FastAPI(
        title="Little English Buddy API",
        description="A child-friendly English learning chatbot API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Get settings for CORS (need to handle this before lifespan)
    try:
        settings = get_settings()
        origins = settings.frontend_origins
    except Exception:
        origins = ["http://localhost:3000"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
        expose_headers=[],
    )

    # Global exception handler - never expose stack traces
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"unhandled_error type={type(exc).__name__}")
        return JSONResponse(
            status_code=500,
            content={"detail": "An internal error occurred"},
        )

    # Request size limiting middleware
    @app.middleware("http")
    async def limit_request_size(request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > 10_000:  # 10KB max
            return JSONResponse(
                status_code=413,
                content={"detail": "Request body too large"},
            )
        return await call_next(request)

    app.include_router(router)

    return app


app = create_app()
