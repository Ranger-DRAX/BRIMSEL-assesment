"""Deterministic mock provider for development and testing."""

from __future__ import annotations

import random

from app.providers.interface import GenerationContext, GenerationResult, LLMProvider

# Deterministic response templates by mode
MOCK_RESPONSES = {
    "conversation": [
        {
            "reply": "That's so interesting! Tell me more about that! 😊",
            "suggested_replies": ["I like it a lot", "Let me think", "Something else"],
        },
        {
            "reply": "Wow, how cool! What else do you enjoy? 🌟",
            "suggested_replies": ["Playing", "Drawing", "Reading"],
        },
        {
            "reply": "That sounds fun! Do you do that often? 😄",
            "suggested_replies": ["Yes!", "Sometimes", "Not really"],
        },
    ],
    "learning": [
        {
            "reply": "Great job! You're learning so well! Ready for the next one? 🎯",
            "suggested_replies": ["Yes please!", "I need a hint", "Let's take a break"],
        },
        {
            "reply": "You're doing amazing! Keep going, you can do it! ⭐",
            "suggested_replies": ["Next question", "Can I get a hint?", "Let's chat instead"],
        },
    ],
    "engagement": [
        {
            "reply": "Let's play a fun game! I'm thinking of something... 🎮",
            "suggested_replies": ["Sounds fun!", "Give me a clue", "Something else"],
        },
    ],
    "support": [
        {
            "reply": "I hear you, and that's okay! Everyone feels that way sometimes. Would you like to take a break or try something different? 💙",
            "suggested_replies": ["Take a break", "Try something easier", "Let's just chat"],
        },
        {
            "reply": "You're doing great just by trying! It's okay to find things tricky. Want to do something fun instead? 🌈",
            "suggested_replies": ["Yes, let's play!", "I want to keep trying", "Let's talk"],
        },
    ],
}

# Responses for specific situations
CORRECT_ANSWER_RESPONSES = [
    "Wonderful! That's exactly right! You're so smart! 🎉",
    "Yes! You got it! Great job! 🌟",
    "Perfect answer! You're doing amazingly! ⭐",
]

INCORRECT_ANSWER_RESPONSES = [
    "Good try! That's not quite it, but you're learning! Want to try again? 💪",
    "Almost! Don't worry, mistakes help us learn! Would you like a hint? 🤔",
    "Not quite, but that's okay! Learning takes practice! Try once more? 😊",
]

HINT_RESPONSES = [
    "Here's a hint to help you out! 💡",
]

BREAK_RESPONSES = [
    "Great idea to take a break! Come back when you're ready! We'll be here! 🌈",
    "Taking a break is smart! Rest up and we'll play again soon! 😊",
]

STOP_RESPONSES = [
    "Okay! We'll stop right here. Come back whenever you want! 👋",
]


class MockProvider(LLMProvider):
    """Deterministic mock provider for development and testing.

    All responses are clearly mock responses - never represented as live Groq output.
    """

    async def generate_reply(self, context: GenerationContext) -> GenerationResult:
        """Generate a deterministic mock reply based on context."""
        mode = context.mode

        # Check for specific actions/situations
        lower_msg = context.new_message.lower() if context.new_message else ""

        # Safety concern
        if any(kw in lower_msg for kw in ["sad", "scared", "can't do", "don't want to",
                                           "hate", "angry", "upset"]):
            if not any(neg in lower_msg for neg in ["not sad", "not scared", "not angry",
                                                     "the story", "the dog", "he is", "she is"]):
                mode = "support"

        # Break/stop
        if any(phrase in lower_msg for phrase in ["take a break", "break", "rest"]):
            resp = random.choice(BREAK_RESPONSES)
            return GenerationResult(
                reply=resp,
                mode="conversation",
                suggested_replies=["I'm back!", "Let's learn!", "Let's play!"],
                source="mock",
            )

        if lower_msg in ["stop", "stop it", "no more"]:
            resp = random.choice(STOP_RESPONSES)
            return GenerationResult(
                reply=resp,
                mode="conversation",
                suggested_replies=["Start again", "Let's chat"],
                source="mock",
            )

        # Mode-specific responses
        templates = MOCK_RESPONSES.get(mode, MOCK_RESPONSES["conversation"])
        template = random.choice(templates)

        # If we have consecutive teaching turns, offer choice
        if context.consecutive_teaching_turns >= 2 and mode == "learning":
            return GenerationResult(
                reply="You've been working hard! Would you like to keep learning, chat, or play a game? 🌟",
                mode="learning",
                suggested_replies=["Continue learning", "Let's chat!", "Play a game!"],
                source="mock",
            )

        return GenerationResult(
            reply=str(template["reply"]),
            mode=mode,
            suggested_replies=list(template.get("suggested_replies", [])),
            source="mock",
        )

    async def close(self) -> None:
        """No resources to clean up for mock provider."""
        pass
