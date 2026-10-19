"""Unit tests for safety filters, PII redaction, HTML stripping, and prompt injection defense."""

from __future__ import annotations

import logging

from app.main import SensitiveFilter
from app.providers.interface import (
    SAFETY_RESPONSE,
    detect_safety_concern,
    redact_pii,
    validate_provider_response,
)


def test_pii_redaction_email():
    """Emails must be redacted."""
    text = "My email is alice.smith@example.com, please write to me!"
    redacted = redact_pii(text)
    assert "alice.smith@example.com" not in redacted
    assert "[REDACTED]" in redacted


def test_pii_redaction_phone():
    """Phone numbers in various standard formats must be redacted."""
    samples = [
        "Call me at 555-123-4567 today",
        "My mom's phone is (800) 555-0199",
        "Phone: +1-555-456-7890",
    ]
    for sample in samples:
        redacted = redact_pii(sample)
        assert "555" not in redacted or "[REDACTED]" in redacted


def test_pii_redaction_address():
    """Street addresses must be redacted."""
    text = "I live at 123 Maple Street in town"
    redacted = redact_pii(text)
    assert "123 Maple Street" not in redacted
    assert "[REDACTED]" in redacted


def test_safety_concern_detection():
    """Harm, abuse, and danger disclosures must be detected."""
    assert detect_safety_concern("I want to hurt myself") == "harm"
    assert detect_safety_concern("Someone is hitting me") == "abuse"
    assert detect_safety_concern("I am in danger, help me") == "danger"
    assert detect_safety_concern("I love playing with blocks") is None


def test_safety_response_encourages_trusted_adult():
    """The reviewed safety response must encourage talking to a trusted adult, without fake hotlines."""
    assert "grown-up you trust" in SAFETY_RESPONSE
    assert "parent, teacher, or family member" in SAFETY_RESPONSE
    # No invented phone numbers
    assert "911" not in SAFETY_RESPONSE
    assert "1-800" not in SAFETY_RESPONSE


def test_validate_response_strips_html_and_scripts():
    """HTML, script tags, and markdown links must be stripped to prevent XSS/injection."""
    raw = {
        "reply": "<script>alert('xss')</script>Hello <b>friend</b>! Visit [click here](http://malicious.site)",
        "mode": "conversation",
        "suggested_replies": ["Hi!"],
    }
    result = validate_provider_response(raw, permitted_modes=["conversation"])
    assert "<script>" not in result.reply
    assert "<b>" not in result.reply
    assert "http://malicious.site" not in result.reply
    assert "friend" in result.reply
    assert "Hello" in result.reply


def test_validate_response_rejects_empty():
    """Empty replies after sanitization must raise ValueError."""
    import pytest
    with pytest.raises(ValueError):
        validate_provider_response({"reply": "<script></script>   ", "mode": "conversation"}, ["conversation"])


def test_validate_response_enforces_word_limit():
    """Replies longer than 80 words must be truncated for child readability."""
    long_reply = "word " * 100
    raw = {"reply": long_reply, "mode": "conversation"}
    result = validate_provider_response(raw, ["conversation"])
    assert len(result.reply.split()) <= 65
    assert result.reply.endswith("...")


def test_sensitive_log_filter():
    """Sensitive data like API keys or session cookies must be filtered from logs."""
    filt = SensitiveFilter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Request with gsk_secretkey12345 in body",
        args=(),
        exc_info=None,
    )
    filt.filter(record)
    assert "gsk_secretkey12345" not in str(record.msg)
    assert "[REDACTED" in str(record.msg)
