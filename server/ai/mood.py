"""Persistent villager mood state."""

from __future__ import annotations

import hashlib
from typing import Any

from server.ai.memory import MemoryStore
from server.ai.personality import Personality


MOODS = ["content", "happy", "excited", "melancholy", "anxious", "irritated", "peaceful", "lonely"]

DEFAULT_BASELINE_BY_TIME = {
    "morning": "peaceful",
    "afternoon": "content",
    "evening": "peaceful",
    "night": "lonely",
}

ADJACENT_MOODS = {
    "content": ["peaceful", "happy"],
    "happy": ["content", "excited", "peaceful"],
    "excited": ["happy", "content"],
    "melancholy": ["lonely", "peaceful"],
    "anxious": ["irritated", "content"],
    "irritated": ["anxious", "content"],
    "peaceful": ["content", "happy", "melancholy"],
    "lonely": ["melancholy", "peaceful"],
}


class MoodTracker:
    """Stores slow-moving mood in the villager's self relationship metadata."""

    def __init__(self, memory_store: MemoryStore) -> None:
        self.memory_store = memory_store

    def current_mood(self, villager_id: str) -> str:
        state = self._load_state(villager_id)
        return str(state.get("current") or self._dominant_mood(state.get("scores", {})))

    def nudge(self, villager_id: str, mood: str, weight: float) -> str:
        if mood not in MOODS:
            mood = "content"

        state = self._load_state(villager_id)
        scores = self._scores(state)
        scores[mood] += max(0.0, float(weight))
        scores = self._normalize(scores)
        current = self._dominant_mood(scores)
        self._save_state(villager_id, scores, current)
        return current

    def tick(self, villager_id: str, world_state: Any, personality: Personality) -> str:
        time_label = self._time_label(world_state)
        baseline = self._baseline_for_time(personality, time_label)

        state = self._load_state(villager_id)
        scores = self._scores(state)
        scores[baseline] += 0.36

        for adjacent in self._stable_adjacent_moods(villager_id, baseline, time_label):
            scores[adjacent] += 0.04

        scores = self._normalize(scores)
        current = self._dominant_mood(scores)
        self._save_state(villager_id, scores, current)
        return current

    def _load_state(self, villager_id: str) -> dict[str, Any]:
        relationship = self.memory_store.get_relationship(villager_id, "self")
        metadata = relationship.get("metadata", {})
        mood_state = metadata.get("mood_state", {})
        return mood_state if isinstance(mood_state, dict) else {}

    def _save_state(self, villager_id: str, scores: dict[str, float], current: str) -> None:
        self.memory_store.update_relationship(
            villager_id,
            "self",
            metadata={
                "mood_state": {
                    "current": current,
                    "scores": {mood: round(score, 4) for mood, score in scores.items()},
                }
            },
        )

    def _scores(self, state: dict[str, Any]) -> dict[str, float]:
        raw_scores = state.get("scores", {})
        scores = {mood: 0.0 for mood in MOODS}
        if isinstance(raw_scores, dict):
            for mood, score in raw_scores.items():
                if mood in scores:
                    scores[mood] = max(0.0, float(score))
        if sum(scores.values()) <= 0:
            scores["content"] = 1.0
        return scores

    def _normalize(self, scores: dict[str, float]) -> dict[str, float]:
        total = sum(scores.values())
        if total <= 0:
            return {"content": 1.0, **{mood: 0.0 for mood in MOODS if mood != "content"}}
        return {mood: scores.get(mood, 0.0) / total for mood in MOODS}

    def _dominant_mood(self, scores: dict[str, float]) -> str:
        if not scores:
            return "content"
        return max(MOODS, key=lambda mood: scores.get(mood, 0.0))

    def _time_label(self, world_state: Any) -> str:
        if isinstance(world_state, dict):
            return str(world_state.get("time_label", "afternoon"))
        snapshot = world_state.snapshot()
        return str(snapshot.get("time_label", "afternoon"))

    def _baseline_for_time(self, personality: Personality, time_label: str) -> str:
        baseline = personality.mood_baseline_by_time.get(time_label) or DEFAULT_BASELINE_BY_TIME.get(time_label)
        if baseline in MOODS:
            return baseline

        traits = {trait.lower() for trait in personality.core_traits}
        if {"gentle", "observant", "romantic"} & traits:
            return "peaceful"
        if {"shy", "worried", "anxious"} & traits:
            return "anxious"
        return "content"

    def _stable_adjacent_moods(self, villager_id: str, baseline: str, time_label: str) -> list[str]:
        adjacent = ADJACENT_MOODS.get(baseline, ["content"])
        digest = hashlib.sha1(f"{villager_id}:{baseline}:{time_label}".encode("utf-8")).digest()
        count = 1 + digest[0] % min(2, len(adjacent))
        start = digest[1] % len(adjacent)
        ordered = adjacent[start:] + adjacent[:start]
        return ordered[:count]
