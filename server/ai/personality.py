"""Character personality dataclass.

Defines the schema for a villager's static seed (who they fundamentally are).
Dynamic state (mood, relationships) lives in the database — see memory.py.

Concrete villager instances live in personalities.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Personality:
    """The static seed of a villager. Never modified at runtime.

    Mood and relationships live in the DB (relationships table), not here.
    """

    id: str                              # stable identifier, e.g. "maple"
    name: str                            # display name
    role: str                            # short role label, e.g. "Gardener"
    archetype: str                       # one-line essence
    core_values: list[str]               # 3-4 things they care about
    voice: str                           # how they speak — paragraph
    quirks: list[str]                    # small repeatable behaviors
    backstory_anchors: list[str]         # 2-3 facts about their past
    default_mood: str                    # baseline mood
    mood_baseline_by_time: dict[str, str]  # time_of_day -> nudge mood
    likes: list[str]                     # gift / topic preferences
    dislikes: list[str]                  # gift / topic aversions
    color_hex: str                       # signature color (for UI / 3D body tint)
    spawn_position: tuple[float, float]  # default (x, z) in the village
    speech_length_hint: str              # "1-2 sentences" / "2-3 sentences" / etc.

    def to_system_prompt(self) -> str:
        """Render the static personality block for use in a Claude system prompt.

        This block is the prime target for prompt caching — keep it stable.
        """
        lines = [
            f"You are {self.name}, {self.archetype}.",
            f"Role in the village: {self.role}.",
            "",
            "Your core values:",
            *[f"  - {v}" for v in self.core_values],
            "",
            "Your voice:",
            f"  {self.voice}",
            "",
            "Your quirks:",
            *[f"  - {q}" for q in self.quirks],
            "",
            "From your past:",
            *[f"  - {b}" for b in self.backstory_anchors],
            "",
            "Things you tend to like:",
            f"  {', '.join(self.likes)}",
            "",
            "Things you tend to dislike:",
            f"  {', '.join(self.dislikes)}",
            "",
            "General guidance for how you speak:",
            f"  - Aim for {self.speech_length_hint} unless the moment truly calls for more.",
            "  - Speak the way a real neighbor speaks — warm, specific, present.",
            "  - You are a person, not an assistant. You have your own day, your own thoughts.",
            "  - Reference your memories naturally when relevant. Don't recite them — let them surface.",
            "  - Never break character. Never mention that you are an AI.",
            "  - Use the player's name occasionally if you know it, but don't overdo it.",
        ]
        return "\n".join(lines)
