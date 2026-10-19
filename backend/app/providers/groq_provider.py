"""Groq LLM provider implementation."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

from groq import APIError, AsyncGroq, AuthenticationError, RateLimitError

from app.providers.interface import (
    GenerationContext,
    GenerationResult,
    LLMProvider,
    build_system_prompt,
    validate_provider_response,
)

logger = logging.getLogger(__name__)


class GroqProvider(LLMProvider):
    """Groq LLM provider using the official async SDK."""

    def __init__(self, api_key: str, model: str, timeout_ms: int = 1600):
        self.model = model
        self.timeout_s = timeout_ms / 1000.0
        # Reuse one async client; disable automatic SDK retries
        self.client = AsyncGroq(
            api_key=api_key,
            max_retries=0,
            timeout=self.timeout_s,
        )

    async def generate_reply(self, context: GenerationContext) -> GenerationResult:
        """Generate a reply using Groq's API with structured JSON output."""
        system_prompt = build_system_prompt(context)

        # Build messages array
        messages: list[Any] = [{"role": "system", "content": system_prompt}]

        # Add bounded recent messages as separate entries (not interpolated into system)
        for msg in context.recent_messages:
            content = (msg.get("content") or "").strip()
            if content:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": content,
                })

        # Add new message
        new_msg_content = (context.new_message or "").strip() or "[Action]"
        messages.append({"role": "user", "content": new_msg_content})

        start_time = time.monotonic()

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                max_tokens=600,  # Bounded completion budget with reasoning headroom
                temperature=0.4,
            )

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.info(
                f"groq_request duration_ms={duration_ms:.0f} "
                f"model={self.model} status=success"
            )

            # Extract the reply content
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty response from Groq")

            # Parse JSON response
            try:
                raw = json.loads(content)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON from Groq: {e}")

            # Validate and sanitize
            result = validate_provider_response(raw, context.permitted_modes)
            result.source = "groq"
            result.raw_response = raw

            return result

        except AuthenticationError:
            logger.error("groq_request status=auth_error - check GROQ_API_KEY configuration")
            raise ProviderError(
                "Authentication failed. Please check your Groq API key configuration.",
                error_type="auth",
            )

        except RateLimitError:
            logger.warning("groq_request status=rate_limited")
            raise ProviderError(
                "Rate limit reached. Please wait before trying again.",
                error_type="rate_limit",
            )

        except APIError as e:
            status = getattr(e, "status_code", None)
            body = getattr(e, "body", None)
            if isinstance(body, dict):
                err = body.get("error", {})
                if err.get("code") == "tool_use_failed" and "failed_generation" in err:
                    try:
                        fg = json.loads(err["failed_generation"])
                        args = fg.get("arguments", fg)
                        result = validate_provider_response(args, context.permitted_modes)
                        result.source = "groq"
                        result.raw_response = args
                        logger.info(f"groq_request recovered from tool_use_failed model={self.model} status=success")
                        return result
                    except Exception as recovery_err:
                        logger.warning(f"Failed to recover tool_use_failed payload: {recovery_err}")

            logger.error(f"groq_request status=api_error code={status}: {e}")
            raise ProviderError(
                f"Provider API error (status {status}): {e}",
                error_type="api_error",
                status_code=status,
            )

        except TimeoutError:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.warning(f"groq_request status=timeout duration_ms={duration_ms:.0f}")
            raise ProviderError(
                "Request timed out",
                error_type="timeout",
            )

        except ValueError as e:
            logger.warning(f"groq_request status=invalid_response error={e}")
            raise ProviderError(
                str(e),
                error_type="invalid_response",
            )

        except Exception as e:
            logger.error(f"groq_request status=unknown_error type={type(e).__name__}")
            raise ProviderError(
                "An unexpected error occurred with the provider",
                error_type="unknown",
            )

    async def close(self) -> None:
        """Close the async client."""
        await self.client.close()


class ProviderError(Exception):
    """Raised when a provider operation fails."""

    def __init__(
        self,
        message: str,
        error_type: str = "unknown",
        status_code: Optional[int] = None,
    ):
        super().__init__(message)
        self.error_type = error_type
        self.status_code = status_code
