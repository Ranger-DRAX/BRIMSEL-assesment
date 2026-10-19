"""Curriculum loader and activity management."""

from __future__ import annotations

import json
import random
import unicodedata
import uuid
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, field_validator


class Choice(BaseModel):
    id: str
    text: str


class Activity(BaseModel):
    id: str
    level: str
    skill: str
    type: str  # multiple_choice, short_answer
    prompt: str
    choices: Optional[list[Choice]] = None
    accepted_answers: list[str]
    hint: str
    feedback_correct: str
    feedback_incorrect: str
    placement: bool = False
    placement_order: Optional[int] = None

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        if v not in ("L1", "L2", "L3"):
            raise ValueError(f"Invalid level: {v}")
        return v


class EngagementGame(BaseModel):
    id: str
    type: str
    prompt: str
    answer: str
    hint: str


class Curriculum:
    """Manages curriculum activities, validated at startup."""

    def __init__(self):
        self.activities: dict[str, Activity] = {}
        self.by_level: dict[str, list[Activity]] = {"L1": [], "L2": [], "L3": []}
        self.placement_activities: list[Activity] = []
        self.engagement_games: list[EngagementGame] = []

    def load(self, path: Optional[Path] = None) -> None:
        """Load and validate curriculum from JSON file."""
        if path is None:
            path = Path(__file__).parent / "activities.json"

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Validate and index activities
        for item in data.get("activities", []):
            activity = Activity(**item)
            if activity.id in self.activities:
                raise ValueError(f"Duplicate activity ID: {activity.id}")
            self.activities[activity.id] = activity
            self.by_level[activity.level].append(activity)
            if activity.placement:
                self.placement_activities.append(activity)

        # Sort placement activities by order
        self.placement_activities.sort(key=lambda a: a.placement_order or 0)

        # Validate minimum requirements
        for level in ("L1", "L2", "L3"):
            non_placement = [a for a in self.by_level[level] if not a.placement]
            if len(non_placement) < 10:
                raise ValueError(
                    f"Level {level} needs at least 10 non-placement activities, "
                    f"has {len(non_placement)}"
                )
            # Check skill variety
            skills = {a.skill for a in non_placement}
            if len(skills) < 2:
                raise ValueError(
                    f"Level {level} needs at least 2 skills, has {len(skills)}: {skills}"
                )

        # Load engagement games
        for item in data.get("engagement_games", []):
            self.engagement_games.append(EngagementGame(**item))

    def get_activity(self, activity_id: str) -> Optional[Activity]:
        """Get an activity by ID."""
        return self.activities.get(activity_id)

    def pick_activity(self, level: str, exclude_ids: Optional[set[str]] = None) -> Activity:
        """Pick a random non-placement activity for a level, avoiding recently used."""
        candidates = [
            a for a in self.by_level.get(level, [])
            if not a.placement and (exclude_ids is None or a.id not in exclude_ids)
        ]
        if not candidates:
            # Fall back to all non-placement activities at this level
            candidates = [a for a in self.by_level.get(level, []) if not a.placement]
        return random.choice(candidates)

    def pick_game(self) -> EngagementGame:
        """Pick a random engagement game."""
        return random.choice(self.engagement_games)

    def get_placement_activities(self) -> list[Activity]:
        """Get placement activities in order."""
        return self.placement_activities

    def generate_instance_id(self) -> str:
        """Generate a unique instance ID for an activity presentation."""
        return str(uuid.uuid4())


def normalize_answer(text: str) -> str:
    """Normalize an answer for comparison.

    - Strip surrounding whitespace
    - Lowercase
    - Normalize Unicode
    - Strip simple trailing punctuation (.!?)
    """
    text = text.strip().lower()
    text = unicodedata.normalize("NFC", text)
    # Strip trailing punctuation
    while text and text[-1] in ".!?,;:":
        text = text[:-1]
    text = text.strip()
    return text


def check_answer(activity: Activity, answer: str) -> tuple[bool, bool]:
    """Check a user's answer against accepted answers.

    Returns: (is_correct, is_recognized)
    - For multiple_choice: answer should be a choice ID
    - For short_answer: normalized comparison against accepted list
    """
    normalized = normalize_answer(answer)

    if activity.type == "multiple_choice":
        valid_ids = [c.id.lower() for c in (activity.choices or [])]
        choice_map = {c.id.lower(): normalize_answer(c.text) for c in (activity.choices or [])}
        accepted_norms = [normalize_answer(a) for a in activity.accepted_answers]

        # Case 1: Answer is a choice ID (e.g. from tapping a button)
        if normalized in valid_ids:
            choice_text = choice_map.get(normalized, "")
            is_correct = (
                normalized in accepted_norms
                or choice_text in accepted_norms
                or any(acc in choice_text for acc in accepted_norms)
            )
            return is_correct, True

        # Case 2: Answer is text matching a choice or accepted answer (e.g. from typing)
        for cid, ctext in choice_map.items():
            if normalized == ctext:
                is_correct = (
                    cid in accepted_norms
                    or ctext in accepted_norms
                    or any(acc in ctext for acc in accepted_norms)
                )
                return is_correct, True

        # Case 3: Answer directly matches accepted answers
        if normalized in accepted_norms:
            return True, True

        # Unrecognized free-form text
        return False, False

    elif activity.type == "short_answer":
        # Check if any accepted answer is contained in the normalized text
        for accepted in activity.accepted_answers:
            accepted_norm = normalize_answer(accepted)
            if accepted_norm == normalized:
                return True, True
            # For prefix matching (e.g., "i like" matches "i like dogs")
            if accepted_norm and normalized.startswith(accepted_norm):
                return True, True

        # Check if the answer seems like an attempt (non-empty, reasonable length)
        is_recognized = len(normalized) > 0 and len(normalized) < 200
        return False, is_recognized

    return False, False


# Singleton curriculum
_curriculum: Optional[Curriculum] = None


def get_curriculum() -> Curriculum:
    """Get or initialize the curriculum singleton."""
    global _curriculum
    if _curriculum is None:
        _curriculum = Curriculum()
        _curriculum.load()
    return _curriculum
