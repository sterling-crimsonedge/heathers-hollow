"""Smoke test for persistent villager mood drift.

Run from the repo root:

    python -m server.tests.test_mood
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from server.ai.memory import MemoryStore
from server.ai.mood import (
    DEFAULT_PIN_DURATION_MINUTES,
    MOODS,
    NEGATIVE_MOOD_INTENSITY_CAPS,
    MoodTracker,
)
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


def run_mood_pin_check() -> None:
    """HH-006: a loved gift should pin `excited` for ~2 in-game hours.

    A baseline tick on a peaceful-leaning villager would normally yank the
    dominant mood back toward `peaceful`/`content` within a tick or two. The
    pin should hold `excited` until ``DEFAULT_PIN_DURATION_MINUTES`` in-game
    minutes have elapsed, then expire and let the baseline reassert.
    """
    with TemporaryDirectory() as tmp_dir:
        memory_store = MemoryStore(Path(tmp_dir) / "mood_pin.sqlite3")
        personality = PersonalityStore().load("margot")
        tracker = MoodTracker(memory_store)

        # Day 1 at 10:00 — well inside the morning baseline window.
        start_minute_of_day = 10 * 60
        start_world = {"day": 1, "minute_of_day": start_minute_of_day, "time_label": "morning"}

        # No pin yet — current_mood should fall back to score-resolved.
        assert tracker.current_mood("margot", world=start_world) in MOODS

        # Pin excited for the default window from "now".
        pinned = tracker.pin("margot", "excited", world=start_world)
        assert pinned == "excited"

        # Several baseline ticks within the pin window — all should still
        # report `excited` even though Margot's morning baseline is peaceful.
        for offset in (1, 15, 60, DEFAULT_PIN_DURATION_MINUTES - 1):
            world = {
                "day": 1,
                "minute_of_day": start_minute_of_day + offset,
                "time_label": "morning",
            }
            mood_during_pin = tracker.tick("margot", world, personality)
            assert mood_during_pin == "excited", (
                f"Pin should hold excited at offset {offset}m, got {mood_during_pin!r}."
            )
            assert tracker.current_mood("margot", world=world) == "excited"

        # current_mood without world context should still report the pinned mood
        # (the persisted `mood_state.current` carries the pin).
        assert tracker.current_mood("margot") == "excited"

        # Past the pin window — pin should expire and baseline reasserts.
        past_pin_world = {
            "day": 1,
            "minute_of_day": start_minute_of_day + DEFAULT_PIN_DURATION_MINUTES + 5,
            "time_label": "afternoon",
        }
        mood_after_pin = tracker.tick("margot", past_pin_world, personality)
        # After the pin clears, the baseline tick is back in charge. Margot's
        # afternoon baseline is `content`, with some lingering excited score
        # from the pin's reinforcement, so any of the warm/peaceful neighbors
        # is acceptable — what matters is the pin metadata is gone.
        assert mood_after_pin in MOODS

        # Pin metadata should be cleared so the next baseline isn't sticky.
        relationship = memory_store.get_relationship("margot", "self")
        mood_state = relationship["metadata"]["mood_state"]
        assert mood_state.get("pinned_mood") in {None, ""}
        assert mood_state.get("pinned_until_minute") in {None, 0} or mood_state.get(
            "pinned_until_minute"
        ) is None

        # current_mood after pin expiry should match the new dominant.
        assert tracker.current_mood("margot", world=past_pin_world) == mood_after_pin

        # Persistence sanity: a fresh tracker on the same DB sees the cleared pin.
        reloaded = MoodTracker(memory_store)
        assert reloaded.current_mood("margot", world=past_pin_world) == mood_after_pin


def main() -> None:
    run_mood_check()
    run_negative_mood_cap_check()
    run_mood_pin_check()
    print(
        "PASS: MoodTracker drifts, persists, clamps negative-mood intensity, "
        "and pins loved-gift moods until the in-game window elapses."
    )


if __name__ == "__main__":
    main()
