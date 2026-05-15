"""Smoke test for persistent villager mood drift.

Run from the repo root:

    python -m server.tests.test_mood
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from server.ai.memory import MemoryStore
from server.ai.mood import MoodTracker
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


def main() -> None:
    run_mood_check()
    print("PASS: MoodTracker drifts and persists mood state.")


if __name__ == "__main__":
    main()
