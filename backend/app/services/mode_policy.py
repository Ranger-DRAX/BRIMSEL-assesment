"""Mode policy engine - determines conversation mode transitions."""

from __future__ import annotations

import re
from typing import Optional

from app.schemas.api import Action, Mode

# Distress/frustration indicators (direct first-person statements)
DISTRESS_PHRASES = [
    "i am sad", "i'm sad", "i feel sad", "feeling sad", "feel like crying",
    "i am scared", "i'm scared", "i feel scared",
    "i can't do this", "i cant do this", "i can't do it",
    "this is too hard", "too hard",
    "i'm frustrated", "i am frustrated", "so frustrated",
    "i want to cry", "i'm crying", "i am crying",
    "i'm upset", "i am upset", "i feel bad",
    "i don't like this", "i dont like this",
    "i'm angry", "i am angry",
    "i hate this",
    "nobody likes me", "no one likes me",
]

# Negation patterns that should NOT trigger support mode
NEGATION_PATTERNS = [
    r"\bnot sad\b", r"\bnot scared\b", r"\bnot angry\b", r"\bnot upset\b", r"\bnot frustrated\b",
    r"\bi'm not\b", r"\bi am not\b", r"\bdon't feel sad\b", r"\bdon't feel scared\b",
]

# Third-person/quoted patterns that should NOT trigger support mode
THIRD_PERSON_PATTERNS = [
    r"\bthe story\b", r"\bthe book\b", r"\bthe dog\b", r"\bthe cat\b", r"\bthe puppy\b",
    r"\bthe boy\b", r"\bthe girl\b", r"\bmy dog\b", r"\bmy cat\b", r"\bmy puppy\b",
    r"\bmy sister\b", r"\bmy brother\b", r"\bhe is\b", r"\bshe is\b", r"\bit is\b",
    r"\bthey are\b", r"\bhe was\b", r"\bshe was\b", r"\bhis\b", r"\bher\b",
    r"\btheir\b", r"\bthe character\b",
]


def detect_distress(text: str) -> bool:
    """Detect first-person distress. Handles negation and third-person context.

    Returns True only for direct first-person expressions of distress.
    """
    lower = text.lower().strip()

    # Check negation first
    for neg in NEGATION_PATTERNS:
        if re.search(neg, lower):
            return False

    # Check third-person context
    for tp in THIRD_PERSON_PATTERNS:
        if re.search(tp, lower):
            return False

    # Check for distress phrases
    for phrase in DISTRESS_PHRASES:
        if phrase in lower:
            return True

    return False


def resolve_mode(
    action: Optional[Action],
    message: Optional[str],
    current_mode: str,
    has_active_activity: bool,
    consecutive_teaching_turns: int = 0,
    is_safety_concern: bool = False,
) -> tuple[str, bool]:
    """Resolve the target mode for this turn.

    Priority (from spec section 7):
    1. Safety concern -> support
    2. Expressed distress -> support
    3. Explicit action/request -> respect it
    4. Clear answer to active activity -> learning
    5. Ambiguous -> context-dependent, default conversation

    Returns: (mode, should_stop_activity)
    """
    text = message or ""
    lower_text = text.lower().strip()

    # Priority 1: Immediate safety concern
    if is_safety_concern:
        return Mode.SUPPORT.value, True

    # Priority 2: Expressed distress
    if detect_distress(text):
        return Mode.SUPPORT.value, True

    # Priority 3: Explicit actions
    if action:
        if action == Action.LEARN:
            return Mode.LEARNING.value, False
        elif action == Action.CHAT:
            return Mode.CONVERSATION.value, True
        elif action == Action.PLAY:
            return Mode.ENGAGEMENT.value, True
        elif action == Action.BREAK:
            return Mode.SUPPORT.value, True
        elif action == Action.STOP:
            return Mode.CONVERSATION.value, True
        elif action == Action.HINT:
            return Mode.LEARNING.value, False
        elif action == Action.SKIP:
            return Mode.LEARNING.value, True
        elif action == Action.CONTINUE:
            return Mode.LEARNING.value, False
        elif action in (Action.ACCEPT_PROMOTION, Action.DECLINE_PROMOTION):
            return Mode.LEARNING.value, False
        elif action == Action.PLACEMENT:
            return Mode.LEARNING.value, False

    # Natural language action detection
    if any(phrase in lower_text for phrase in ["take a break", "want a break", "need a break", "can we take a break", "can we have a break"]):
        return Mode.SUPPORT.value, True
    if any(phrase in lower_text for phrase in ["stop please", "please stop"]) or lower_text in ("stop", "pause"):
        return Mode.CONVERSATION.value, True
    if any(phrase in lower_text for phrase in ["teach me", "let's learn", "learn about",
                                                 "i want to learn", "learn again", "let's learn again"]):
        return Mode.LEARNING.value, False

    if any(phrase in lower_text for phrase in ["let's play", "play a game", "game"]):
        return Mode.ENGAGEMENT.value, True

    if any(phrase in lower_text for phrase in ["stop", "no more", "i don't want to study",
                                                 "don't want to learn"]):
        return Mode.CONVERSATION.value, True

    if any(phrase in lower_text for phrase in ["rest", "need rest"]):
        return Mode.CONVERSATION.value, True

    # Priority 4: Answer to active activity
    if has_active_activity and current_mode == Mode.LEARNING.value:
        return Mode.LEARNING.value, False

    # Priority 5: Default - stay in current mode or conversation
    if current_mode == Mode.SUPPORT.value:
        # Support persists until explicit mode change or emotional recovery
        if any(phrase in lower_text for phrase in [
            "i'm okay", "i am okay", "i'm fine", "i feel better", "feeling better",
            "feeling a little better", "better now", "let's learn", "let's play",
            "i'm ready", "thank you", "thanks", "i am not sad", "not sad"
        ]):
            return Mode.CONVERSATION.value, False
        return Mode.SUPPORT.value, False

    # Engagement mode: subsequent conversational messages default to conversation
    if current_mode == Mode.ENGAGEMENT.value:
        return Mode.CONVERSATION.value, False

    return current_mode if current_mode else Mode.CONVERSATION.value, False


def get_permitted_modes(current_mode: str) -> list[str]:
    """Get the list of modes the LLM is allowed to output."""
    if current_mode == Mode.SUPPORT.value:
        return [Mode.SUPPORT.value, Mode.CONVERSATION.value]
    return [m.value for m in Mode]
