"""Smoke test for persistent villager mood drift.

Run from the repo root:

    python -m server.tests.test_mood
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from server.ai.memory import MemoryStore
from server.ai.mood import MOODS, NEGATIVE_MOOD_INTENSITY_CAPS, MoodTracker
from server.ai.personality import PersonalityStore


def run_mood_check() -> None:
    with TemporaryDirectory() as tmp_dir:
        memory_store = MemoryStore(Path(tmp_dir) / "mood.sqlite3")
        personality = PersonalityStore().load("margot")
        tracker = MoodTracker(memory_store)
        world = {"time_label": "morning"}

        for _ in range(8):
            mood = tracker.tick("margot", world, personality)

        assert mood in {"peaceful", "happy", "content"}
        assert mood != "irritated"

        tracker.nudge("margot", "excited", 0.8)
        assert tracker.current_mood("margot") in {"excited", "peaceful", "happy", "content"}

        reloaded = MoodTracker(memory_store)
        assert reloaded.current_mood("margot") == tracker.current_mood("margot")


def run_negative_mood_cap_check() -> None:
    """HH-006: villagers should never stew. Heavy nudges to irritated or anxious
    must not push the score past its cap; the excess is redirected to neighbors."""
    with TemporaryDirectory() as tmp_dir:
        memory_store = MemoryStore(Path(tmp_dir) / "mood_cap.sqlite3")
        tracker = MoodTracker(memory_store)

        # Pile heavy nudges into the worst possible mood.
        for _ in range(8):
            tracker.nudge("margot", "irritated", 4.0)

        relationship = memory_store.get_relationship("margot", "self")
        scores = relationship["metadata"]["mood_state"]["scores"]
        total = sum(float(scores.get(mood, 0.0)) for mood in MOODS)
        assert 0.999 <= total <= 1.001, scores
        assert scores["irritated"] <= NEGATIVE_MOOD_INTENSITY_CAPS["irritated"] + 1e-6, scores
        # The clamp redirects excess into adjacent moods; one of them should now
        # carry meaningful weight rather than the score sitting on irritated alone.
        adjacent_weight = float(scores.get("anxious", 0.0)) + float(scores.get("content", 0.0))
        assert adjacent_weight > 0.0, scores

        for _ in range(8):
            tracker.nudge("margot", "anxious", 4.0)
        relationship = memory_store.get_relationship("margot", "self")
        scores = relationship["metadata"]["mood_state"]["scores"]
        assert scores["anxious"] <= NEGATIVE_MOOD_INTENSITY_CAPS["anxious"] + 1e-6, scores


def main() -> None:
    run_mood_check()
    run_negative_mood_cap_check()
    print("PASS: MoodTracker drifts, persists, and clamps negative-mood intensity.")


if __name__ == "__main__":
    main()
