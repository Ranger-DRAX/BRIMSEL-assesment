"""Unit tests for progress tracking, level promotion, and answer normalization."""

from __future__ import annotations

from datetime import datetime, timezone

from app.curriculum.loader import Activity, check_answer, normalize_answer
from app.db.models import ActivityAttempt
from app.services.progress import (
    check_promotion_eligibility,
    get_next_level,
    should_offer_hint,
)


def make_attempt(
    result: str = "correct",
    assisted: bool = False,
    skill: str = "vocabulary",
    level: str = "L1",
) -> ActivityAttempt:
    """Helper to create dummy ActivityAttempt instances."""
    return ActivityAttempt(
        profile_id="test-profile",
        activity_id="act-1",
        instance_id="inst-1",
        result=result,
        assisted=assisted,
        skill=skill,
        level=level,
        created_at=datetime.now(timezone.utc),
    )


def test_promotion_eligible_8_of_10():
    """8 correct out of 10 qualifying attempts across 2 skills qualifies for promotion."""
    attempts = [
        make_attempt(result="correct", skill="vocabulary"),
        make_attempt(result="correct", skill="vocabulary"),
        make_attempt(result="correct", skill="vocabulary"),
        make_attempt(result="correct", skill="vocabulary"),
        make_attempt(result="correct", skill="grammar"),
        make_attempt(result="correct", skill="grammar"),
        make_attempt(result="correct", skill="grammar"),
        make_attempt(result="correct", skill="grammar"),
        make_attempt(result="incorrect", skill="vocabulary"),
        make_attempt(result="incorrect", skill="grammar"),
    ]
    eligible, reason = check_promotion_eligibility(attempts, "L1")
    assert eligible is True


def test_promotion_not_eligible_7_of_10():
    """7 correct out of 10 does not qualify."""
    attempts = [
        make_attempt(result="correct", skill="vocabulary"),
        make_attempt(result="correct", skill="vocabulary"),
        make_attempt(result="correct", skill="grammar"),
        make_attempt(result="correct", skill="grammar"),
        make_attempt(result="correct", skill="vocabulary"),
        make_attempt(result="correct", skill="vocabulary"),
        make_attempt(result="correct", skill="grammar"),
        make_attempt(result="incorrect", skill="grammar"),
        make_attempt(result="incorrect", skill="vocabulary"),
        make_attempt(result="incorrect", skill="grammar"),
    ]
    eligible, reason = check_promotion_eligibility(attempts, "L1")
    assert eligible is False
    assert "7/10" in reason or "Need at least 8" in reason


def test_promotion_requires_10_attempts():
    """9 perfect attempts do not qualify — strictly requires 10 attempts."""
    attempts = [
        make_attempt(result="correct", skill="vocabulary")
        for _ in range(5)
    ] + [
        make_attempt(result="correct", skill="grammar")
        for _ in range(4)
    ]
    assert len(attempts) == 9
    eligible, reason = check_promotion_eligibility(attempts, "L1")
    assert eligible is False
    assert "Need at least 10" in reason


def test_promotion_requires_two_skills():
    """10 correct attempts in only 1 skill do not qualify (variety requirement)."""
    attempts = [
        make_attempt(result="correct", skill="vocabulary")
        for _ in range(10)
    ]
    eligible, reason = check_promotion_eligibility(attempts, "L1")
    assert eligible is False
    assert "at least 2 different skills" in reason


def test_assisted_attempts_excluded():
    """Assisted (hinted) attempts do not count toward qualifying window."""
    attempts = [
        make_attempt(result="correct", assisted=True, skill="vocabulary")
        for _ in range(5)
    ] + [
        make_attempt(result="correct", assisted=False, skill="grammar")
        for _ in range(6)
    ]
    eligible, reason = check_promotion_eligibility(attempts, "L1")
    assert eligible is False
    assert "Need at least 10" in reason


def test_promotion_l3_ceiling():
    """L3 is the maximum level and cannot be promoted further."""
    attempts = [
        make_attempt(result="correct", skill="vocabulary", level="L3")
        for _ in range(5)
    ] + [
        make_attempt(result="correct", skill="grammar", level="L3")
        for _ in range(5)
    ]
    eligible, reason = check_promotion_eligibility(attempts, "L3")
    assert eligible is False
    assert "maximum level" in reason
    assert get_next_level("L3") is None


def test_get_next_level():
    assert get_next_level("L1") == "L2"
    assert get_next_level("L2") == "L3"
    assert get_next_level("L3") is None


def test_should_offer_hint():
    """Hint offered after 2 consecutive mistakes on same activity."""
    attempts = [
        make_attempt(result="incorrect"),
        make_attempt(result="incorrect"),
    ]
    assert should_offer_hint(attempts, consecutive_wrong=2) is True

    # Only 1 mistake
    attempts_one = [make_attempt(result="incorrect")]
    assert should_offer_hint(attempts_one, consecutive_wrong=2) is False


# --- Deterministic answer normalization tests ---


def test_normalize_answer():
    assert normalize_answer("  Hello!  ") == "hello"
    assert normalize_answer("CAT.") == "cat"
    assert normalize_answer("Red,") == "red"
    assert normalize_answer("  BLUE ? ") == "blue"


def test_check_answer_multiple_choice():
    activity = Activity(
        id="act-mc",
        level="L1",
        skill="vocabulary",
        type="multiple_choice",
        prompt="What color is an apple?",
        accepted_answers=["red", "red apple"],
        choices=[
            {"id": "c1", "text": "Red"},
            {"id": "c2", "text": "Blue"},
        ],
        hint="Apples are usually red or green.",
        feedback_correct="Super! Apples are red! 🍎",
        feedback_incorrect="Apples are red! Let's try again! 🍎",
    )
    # By choice ID
    correct, recognized = check_answer(activity, "c1")
    assert correct is True
    assert recognized is True

    correct, recognized = check_answer(activity, "c2")
    assert correct is False
    assert recognized is True

    # By text match
    correct, recognized = check_answer(activity, "RED")
    assert correct is True
    assert recognized is True

    correct, recognized = check_answer(activity, "blue")
    assert correct is False
    assert recognized is True

    # Unrecognized free-form text
    correct, recognized = check_answer(activity, "I love ice cream")
    assert correct is False
    assert recognized is False
