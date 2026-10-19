"""Fallback responses for various failure modes."""

from __future__ import annotations

import random

CONVERSATION_FALLBACKS = [
    "That's nice! What else would you like to talk about? 😊",
    "Interesting! Would you like to chat more or try something new? 🌟",
    "I'd love to hear more! What shall we do next? ✨",
]

LEARNING_FALLBACKS = [
    "Let's try this activity again! You can do it! 💪",
    "Ready to give it another try? I believe in you! 🌟",
    "Let's keep going with our lesson! You're doing great! ⭐",
]

ENGAGEMENT_FALLBACKS = [
    "Let's play a fun word game! Think of an animal that starts with 'B'! 🎮",
    "Here's a riddle: What has hands but can't clap? A clock! 🕐",
    "Let's count together! Can you count to five? 🔢",
]

SUPPORT_FALLBACKS = [
    "I'm here for you! It's okay to feel that way. Would you like to take a break, or talk to a grown-up you trust? 💙",
    "Everyone has tough moments. You're being very brave! Want to rest or try something different? 🌈",
]

GENERIC_FALLBACK = "I'm having a little trouble right now. Want to try again or do something else? 😊"


def get_fallback_response(mode: str) -> tuple[str, list[str]]:
    """Get a mode-appropriate fallback response.

    Returns: (reply, suggested_replies)
    """
    if mode == "conversation":
        reply = random.choice(CONVERSATION_FALLBACKS)
        suggestions = ["Tell me about your day", "Let's learn!", "Play a game"]
    elif mode == "learning":
        reply = random.choice(LEARNING_FALLBACKS)
        suggestions = ["Try again", "Give me a hint", "Let's do something else"]
    elif mode == "engagement":
        reply = random.choice(ENGAGEMENT_FALLBACKS)
        suggestions = ["That's fun!", "Another game!", "Let's learn instead"]
    elif mode == "support":
        reply = random.choice(SUPPORT_FALLBACKS)
        suggestions = ["Take a break", "I'm okay now", "Talk to grown-up"]
    else:
        reply = GENERIC_FALLBACK
        suggestions = ["Try again", "Let's chat", "Take a break"]

    return reply, suggestions
