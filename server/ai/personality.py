"""Character personality definitions loaded from JSON configs."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_PERSONALITY_DIR = Path(__file__).resolve().parents[1] / "data" / "personalities"


@dataclass(frozen=True)
class SpeakingStyle:
    sentence_length: str = "short"
    tone: str = "warm"
    quirks: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "SpeakingStyle":
        data = data or {}
        return cls(
            sentence_length=str(data.get("sentence_length", "short")),
            tone=str(data.get("tone", "warm")),
            quirks=[str(item) for item in data.get("quirks", [])],
        )


@dataclass(frozen=True)
class Personality:
    id: str
    display_name: str
    species: str
    archetype: str
    core_traits: list[str]
    values: list[str]
    speaking_style: SpeakingStyle
    likes: list[str]
    dislikes: list[str]
    relationships: dict[str, Any]
    private_goals: list[str]
    mood_baseline_by_time: dict[str, str]
    system_prompt: str
    config_path: Path
    # Optional enrichment fields (HH-060). Empty defaults keep older configs valid.
    quirks: list[str] = field(default_factory=list)
    backstory_anchors: list[str] = field(default_factory=list)
    default_mood: str = ""
    # Optional spatial placement hint for clients. Empty falls back to the
    # server-side default ("town_square") so older configs stay valid.
    home_location: str = ""
    # Optional per-villager "loved" gift rubric (HH-062). When supplied, gifts
    # whose tag set or category intersects with this list are scored as "loved"
    # by the gift engine. When empty, conversation.py falls back to a legacy
    # global loved set (flower/porcelain/tea/handmade/garden vegetables) so
    # older configs keep their pre-HH-062 behaviour. This list is server-side
    # only — it is *not* exposed in `public_villager_summary` so clients can't
    # mine the precise gift rubric from the bootstrap payload.
    loved_tags: list[str] = field(default_factory=list)

    @classmethod
    def from_json_file(cls, path: Path) -> "Personality":
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)

        return cls(
            id=str(data["id"]),
            display_name=str(data["display_name"]),
            species=str(data.get("species", "villager")),
            archetype=str(data.get("archetype", "neighbor")),
            core_traits=[str(item) for item in data.get("core_traits", [])],
            values=[str(item) for item in data.get("values", [])],
            speaking_style=SpeakingStyle.from_dict(data.get("speaking_style")),
            likes=[str(item) for item in data.get("likes", [])],
            dislikes=[str(item) for item in data.get("dislikes", [])],
            relationships=dict(data.get("relationships", {})),
            private_goals=[str(item) for item in data.get("private_goals", [])],
            mood_baseline_by_time={
                str(key): str(value) for key, value in data.get("mood_baseline_by_time", {}).items()
            },
            system_prompt=str(data.get("system_prompt", "")),
            config_path=path,
            quirks=[str(item) for item in data.get("quirks", [])],
            backstory_anchors=[str(item) for item in data.get("backstory_anchors", [])],
            default_mood=str(data.get("default_mood", "")),
            home_location=str(data.get("home_location", "")),
            loved_tags=[
                str(tag).strip().lower()
                for tag in data.get("loved_tags", [])
                if str(tag).strip()
            ],
        )

    def starting_relationship(self, subject_id: str) -> dict[str, int]:
        relationship = self.relationships.get(subject_id, {})
        return {
            "affection": int(relationship.get("starting_affection", 0)),
            "trust": int(relationship.get("starting_trust", 0)),
            "familiarity": int(relationship.get("starting_familiarity", 0)),
            "tension": int(relationship.get("starting_tension", 0)),
        }

    def prompt_block(self) -> str:
        lines = [
            f"Name: {self.display_name}",
            f"Species: {self.species}",
            f"Archetype: {self.archetype}",
            f"Core traits: {', '.join(self.core_traits) or 'none supplied'}",
            f"Values: {', '.join(self.values) or 'none supplied'}",
            f"Likes: {', '.join(self.likes) or 'none supplied'}",
            f"Dislikes: {', '.join(self.dislikes) or 'none supplied'}",
            f"Speaking tone: {self.speaking_style.tone}",
            f"Speaking quirks: {', '.join(self.speaking_style.quirks) or 'none supplied'}",
            f"Private goals: {', '.join(self.private_goals) or 'none supplied'}",
        ]
        # Optional enrichment lines: only emit them when the config supplied content,
        # so existing prompts and snapshot tests stay byte-for-byte stable.
        if self.quirks:
            lines.append(f"Character quirks: {', '.join(self.quirks)}")
        if self.backstory_anchors:
            lines.append(f"Backstory anchors: {', '.join(self.backstory_anchors)}")
        if self.default_mood:
            lines.append(f"Default mood: {self.default_mood}")
        return "\n".join(lines)


class PersonalityStore:
    """Loads and caches villager personality configs."""

    def __init__(self, personality_dir: Path | None = None) -> None:
        self.personality_dir = personality_dir or DEFAULT_PERSONALITY_DIR
        self._cache: dict[str, Personality] = {}

    def load(self, villager_id: str) -> Personality:
        if villager_id in self._cache:
            return self._cache[villager_id]

        path = self.personality_dir / f"{villager_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"No personality config found for villager '{villager_id}' at {path}")

        personality = Personality.from_json_file(path)
        self._cache[villager_id] = personality
        return personality

    def list_ids(self) -> list[str]:
        if not self.personality_dir.exists():
            return []
        return sorted(path.stem for path in self.personality_dir.glob("*.json"))
