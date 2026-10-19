"""Unit tests for mode policy engine and emotional awareness."""

from __future__ import annotations

from app.schemas.api import Action, Mode
from app.services.mode_policy import (
    detect_distress,
    get_permitted_modes,
    resolve_mode,
)


def test_detect_distress_direct():
    """First-person emotional distress must be detected."""
    assert detect_distress("I am sad") is True
    assert detect_distress("I'm so frustrated") is True
    assert detect_distress("I feel like crying") is True
    assert detect_distress("I hate this") is True
    assert detect_distress("I'm scared") is True
    assert detect_distress("I can't do this") is True


def test_detect_distress_negation():
    """Negated distress must NOT be classified as distress."""
    assert detect_distress("I am not sad") is False
    assert detect_distress("I am not frustrated at all") is False
    assert detect_distress("I don't hate this") is False


def test_detect_distress_third_person():
    """Third-person emotional reference must NOT trigger support mode distress."""
    assert detect_distress("my dog is sad") is False
    assert detect_distress("the story's puppy was crying") is False
    assert detect_distress("the cat is scared of the vacuum") is False


def test_mode_priority_safety_first():
    """Safety concerns must take absolute highest priority and resolve to SUPPORT."""
    mode, should_stop = resolve_mode(
        action=Action.LEARN,  # Even with explicit LEARN action!
        message="Help me I am hurt",
        current_mode="learning",
        has_active_activity=True,
        consecutive_teaching_turns=0,
        is_safety_concern=True,
    )
    assert mode == Mode.SUPPORT.value
    assert should_stop is True


def test_mode_priority_distress_second():
    """Expressed distress overrides explicit actions and active activities."""
    mode, should_stop = resolve_mode(
        action=Action.PLAY,
        message="I am crying and feel bad",
        current_mode="learning",
        has_active_activity=True,
        consecutive_teaching_turns=2,
        is_safety_concern=False,
    )
    assert mode == Mode.SUPPORT.value
    assert should_stop is True


def test_mode_priority_explicit_action():
    """Explicit action buttons must be respected when no safety/distress."""
    # Learn action
    mode, _ = resolve_mode(
        action=Action.LEARN,
        message="",
        current_mode="conversation",
        has_active_activity=False,
    )
    assert mode == Mode.LEARNING.value

    # Chat action
    mode, should_stop = resolve_mode(
        action=Action.CHAT,
        message="",
        current_mode="learning",
        has_active_activity=True,
    )
    assert mode == Mode.CONVERSATION.value
    assert should_stop is True

    # Play action
    mode, _ = resolve_mode(
        action=Action.PLAY,
        message="",
        current_mode="conversation",
        has_active_activity=False,
    )
    assert mode == Mode.ENGAGEMENT.value

    # Break action
    mode, should_stop = resolve_mode(
        action=Action.BREAK,
        message="",
        current_mode="learning",
        has_active_activity=True,
    )
    assert mode == Mode.SUPPORT.value
    assert should_stop is True

    # Stop action
    mode, should_stop = resolve_mode(
        action=Action.STOP,
        message="",
        current_mode="learning",
        has_active_activity=True,
    )
    assert mode == Mode.CONVERSATION.value
    assert should_stop is True


def test_natural_language_stop_and_break():
    """Natural language requests to stop or take a break must be respected."""
    mode, should_stop = resolve_mode(
        action=None,
        message="stop please",
        current_mode="learning",
        has_active_activity=True,
    )
    assert mode == Mode.CONVERSATION.value
    assert should_stop is True

    mode, should_stop = resolve_mode(
        action=None,
        message="I want to take a break",
        current_mode="learning",
        has_active_activity=True,
    )
    assert mode == Mode.SUPPORT.value
    assert should_stop is True


def test_active_activity_answer_stays_learning():
    """Answering an active activity without explicit mode switch stays learning."""
    mode, _ = resolve_mode(
        action=None,
        message="red",
        current_mode="learning",
        has_active_activity=True,
    )
    assert mode == Mode.LEARNING.value


def test_ordinary_conversation_does_not_trigger_learning():
    """Casual sharing must stay in conversation mode and NOT quiz the child."""
    mode, _ = resolve_mode(
        action=None,
        message="I have a pet rabbit and his name is Fluffy",
        current_mode="conversation",
        has_active_activity=False,
    )
    assert mode == Mode.CONVERSATION.value


def test_support_mode_persists():
    """Support mode must not bounce immediately back to learning on next message."""
    mode, _ = resolve_mode(
        action=None,
        message="I had some water",
        current_mode="support",
        has_active_activity=False,
    )
    assert mode == Mode.SUPPORT.value


def test_permitted_modes():
    """Permitted modes must be constrained appropriately by context."""
    # When in support, permitted modes are support and conversation
    modes = get_permitted_modes(current_mode="support")
    assert "support" in modes
    assert "conversation" in modes
    assert "learning" not in modes

    # Standard conversation
    modes = get_permitted_modes(current_mode="conversation")
    assert "conversation" in modes
    assert "engagement" in modes
