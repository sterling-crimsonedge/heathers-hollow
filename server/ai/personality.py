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
    # Optional per-villager HH-006 tuning overrides. Supported keys:
    #   - affection_per_talk_cap (int): override TALK_AFFECTION_DAILY_CAP
    #   - trust_per_talk_cap (int): override TALK_TRUST_DAILY_CAP
    #   - negative_talk_per_day_cap (int): override TALK_NEGATIVE_DAILY_CAP
    #   - loved_gift_mood_lock_hours (float): override the mood pin duration
    #       used when a loved gift fires `MoodTracker.pin` (defaults to mood.py
    #       DEFAULT_PIN_DURATION_MINUTES / 60 ≈ 2.0 hours)
    #   - first_gift_bonus_tier (int): 1 keeps the HH-006 first-of-kind bump,
    #       0 disables it for this villager (they are too gruff to be wooed by
    #       the gesture-of-bringing-anything)
    #   - trust_cap_unlocks_on_day (int > 0): days after first meeting after
    #       which the per-villager `trust_per_talk_cap` override is dropped
    #       and the global default trust cap takes over. Models the cozy
    #       "they were testing whether Heather keeps promises, and now they
    #       trust her" arc — currently used by Clover (5 days).
    #   - shared_weather_affection_bonus (int >= 0): extra affection delta
    #       added when the player's text mentions the world's current weather
    #       or time-of-day (a "rainy day greeting" or an "evening greeting").
    #       The bonus stacks on top of the normal affection delta and bypasses
    #       the daily affection cap, but only fires once per in-game day per
    #       (player, villager) pair so it cannot be spammed. Currently used
    #       by Hugo (1) — see docs/AI_ARCHITECTURE.md "Per-villager calibration".
    # Defaults match the global constants so omitting `tuning` keeps current
    # behaviour. Like `loved_tags`, `tuning` is *not* exposed in
    # `public_villager_summary` — the per-villager rubric is mechanically
    # readable but intentionally hidden from clients so the demo doesn't read
    # like a stat sheet.
    tuning: dict[str, Any] = field(default_factory=dict)

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
            tuning=cls._coerce_tuning(data.get("tuning")),
        )

    @staticmethod
    def _coerce_tuning(raw: Any) -> dict[str, Any]:
        """Normalize the optional per-villager tuning block.

        The supported keys (see the dataclass docstring above) are coerced to
        their expected types so callers don't have to defend against bad JSON
        every read. Unknown keys are dropped silently — tuning is intentionally
        narrow so we don't grow a backdoor for arbitrary client-facing data.
        """
        if not isinstance(raw, dict):
            return {}
        normalized: dict[str, Any] = {}
        for int_key in (
            "affection_per_talk_cap",
            "trust_per_talk_cap",
            "negative_talk_per_day_cap",
            "first_gift_bonus_tier",
            "trust_cap_unlocks_on_day",
            "shared_weather_affection_bonus",
        ):
            if int_key in raw and raw[int_key] is not None:
                try:
                    normalized[int_key] = int(raw[int_key])
                except (TypeError, ValueError):
                    continue
        if "loved_gift_mood_lock_hours" in raw and raw["loved_gift_mood_lock_hours"] is not None:
            try:
                normalized["loved_gift_mood_lock_hours"] = float(
                    raw["loved_gift_mood_lock_hours"]
                )
            except (TypeError, ValueError):
                pass
        return normalized

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
