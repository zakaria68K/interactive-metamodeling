from dataclasses import dataclass
from typing import Dict, List


@dataclass
class UserTurnPolicy:
    familiar: bool
    background: str
    agree: bool
    feedback: str = ""


class ScriptedUserProtocol:
    """Deterministic user policy for fair, reproducible evaluations."""

    def __init__(self, scripted: Dict[str, UserTurnPolicy]):
        self.scripted = scripted

    def get(self, prompt_id: str) -> UserTurnPolicy:
        return self.scripted.get(
            prompt_id,
            UserTurnPolicy(
                familiar=False,
                background="I know only high-level behavior.",
                agree=True,
                feedback="",
            ),
        )


class NoviceUserProtocol:
    """Non-expert protocol that gives generic clarifications only."""

    GENERIC_BACKGROUNDS: List[str] = [
        "I only know the basic idea and expected behavior.",
        "I am not familiar with formal modeling terms.",
        "I understand examples, not technical notation.",
    ]

    GENERIC_FEEDBACK: List[str] = [
        "Please use simpler wording and fewer technical terms.",
        "Focus on the main building blocks and their behavior.",
        "Make concepts clearer for a beginner.",
    ]

    def __init__(self):
        self._idx = 0

    def next(self) -> UserTurnPolicy:
        bg = self.GENERIC_BACKGROUNDS[self._idx % len(self.GENERIC_BACKGROUNDS)]
        fb = self.GENERIC_FEEDBACK[self._idx % len(self.GENERIC_FEEDBACK)]
        self._idx += 1
        return UserTurnPolicy(
            familiar=False,
            background=bg,
            agree=False,
            feedback=fb,
        )
