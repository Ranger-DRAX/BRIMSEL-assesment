"""Progress tracking and level promotion logic (pure functions)."""

from __future__ import annotations

from app.db.models import ActivityAttempt


def check_promotion_eligibility(
    attempts: list[ActivityAttempt],
    current_level: str,
) -> tuple[bool, str]:
    """Check if a profile is eligible for level promotion.

    Rules:
    - Need exactly 10 qualifying attempts (scored, unassisted)
    - At least 8 of the latest 10 must be correct
    - Must cover at least 2 different skills
    - L3 is the ceiling

    Returns: (eligible, reason)
    """
    if current_level == "L3":
        return False, "Already at maximum level L3"

    # Filter qualifying attempts: unassisted, scored at current level
    qualifying = [
        a for a in attempts
        if a.level == current_level and not a.assisted and a.result in ("correct", "incorrect")
    ]

    if len(qualifying) < 10:
        return False, f"Need at least 10 qualifying attempts, have {len(qualifying)}"

    # Take the latest 10
    latest_10 = qualifying[:10]

    # Count correct
    correct_count = sum(1 for a in latest_10 if a.result == "correct")
    if correct_count < 8:
        return False, f"Need at least 8/10 correct, have {correct_count}/10"

    # Check skill variety
    skills = {a.skill for a in latest_10 if a.result == "correct"}
    if len(skills) < 2:
        return False, f"Need correct answers in at least 2 different skills, have {len(skills)}: {skills}"

    return True, "Eligible for promotion"


def get_next_level(current_level: str) -> str | None:
    """Get the next level, or None if at maximum."""
    levels = {"L1": "L2", "L2": "L3"}
    return levels.get(current_level)


def should_offer_hint(
    recent_attempts: list[ActivityAttempt],
    consecutive_wrong: int = 2,
) -> bool:
    """Determine if we should offer a hint after repeated mistakes."""
    if len(recent_attempts) < consecutive_wrong:
        return False

    latest = recent_attempts[:consecutive_wrong]
    return all(a.result == "incorrect" for a in latest)


def calculate_skill_summary(attempts: list[ActivityAttempt]) -> dict[str, dict]:
    """Calculate a compact skill summary from attempts.

    Returns: {skill_name: {"correct": N, "total": N}}
    """
    summary: dict[str, dict] = {}
    for attempt in attempts:
        if attempt.skill not in summary:
            summary[attempt.skill] = {"correct": 0, "total": 0}
        summary[attempt.skill]["total"] += 1
        if attempt.result == "correct":
            summary[attempt.skill]["correct"] += 1
    return summary
