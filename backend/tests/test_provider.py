"""Unit tests for mock provider, fallbacks, and prompt construction."""

from __future__ import annotations

import pytest

from app.providers.interface import (
    GenerationContext,
    build_system_prompt,
)
from app.providers.mock import MockProvider
from app.services.fallbacks import (
    get_fallback_response,
)


@pytest.mark.asyncio
async def test_mock_provider_conversation():
    """Mock provider returns child-friendly conversation replies."""
    provider = MockProvider()
    ctx = GenerationContext(
        level="L1",
        mode="conversation",
        recent_messages=[],
        new_message="Hello buddy!",
        skill_progress={},
    )
    result = await provider.generate_reply(ctx)
    assert result.source == "mock"
    assert len(result.reply) > 0
    assert len(result.suggested_replies) <= 3
    assert result.mode == "conversation"


@pytest.mark.asyncio
async def test_mock_provider_distress_emotional_awareness():
    """Mock provider detects distress in new message and responds with support."""
    provider = MockProvider()
    ctx = GenerationContext(
        level="L1",
        mode="support",
        recent_messages=[],
        new_message="I'm sad today",
        skill_progress={},
    )
    result = await provider.generate_reply(ctx)
    assert result.mode == "support"
    assert len(result.reply) > 0
    assert "break" in result.reply.lower() or "grown-up" in result.reply.lower() or "okay" in result.reply.lower()


@pytest.mark.asyncio
async def test_mock_provider_consecutive_teaching_turn_break_offer():
    """After 2 consecutive teaching turns, mock provider offers Continue/Chat/Play choices."""
    provider = MockProvider()
    ctx = GenerationContext(
        level="L1",
        mode="learning",
        recent_messages=[],
        new_message="cat",
        skill_progress={},
        consecutive_teaching_turns=2,
    )
    result = await provider.generate_reply(ctx)
    assert "working hard" in result.reply or "chat" in result.reply.lower()
    assert any("chat" in r.lower() or "play" in r.lower() for r in result.suggested_replies)


def test_fallbacks_per_mode():
    """Every mode has distinct reviewed fallbacks."""
    for mode in ["conversation", "learning", "engagement", "support"]:
        reply, suggestions = get_fallback_response(mode)
        assert len(reply) > 0
        assert len(suggestions) <= 3

    # Support fallback must not quiz or demand learning
    reply, suggestions = get_fallback_response("support")
    assert not any("quiz" in s.lower() for s in suggestions)


def test_build_system_prompt_includes_critical_rules():
    """System prompt must contain explicit guardrails against secrets, harmful content, etc."""
    ctx = GenerationContext(
        level="L1",
        mode="conversation",
        recent_messages=[{"role": "user", "content": "I like cats"}],
        new_message="Do you like cats?",
        skill_progress={"colors": 2},
    )
    prompt = build_system_prompt(ctx)
    assert "L1" in prompt
    assert "CRITICAL RULES" in prompt
    assert "personal information" in prompt.lower()
    assert "shame" in prompt.lower()
    assert "claim to be human" in prompt.lower()
