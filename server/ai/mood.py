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

# HH-006 cozy guardrail: villagers can have a bad morning, but they should never
# live in foul-mood territory. After normalization any mood listed below is
# clamped to its cap and the excess is redirected to that mood's neighbors.
NEGATIVE_MOOD_INTENSITY_CAPS = {
    "irritated": 0.7,
    "anxious": 0.7,
}

# HH-006 mood pin: a loved gift should "land" — `delighted`/`excited` shouldn't
# be erased by the next baseline tick a few real seconds later. The pin holds
# the dominant mood for a configurable window of in-game minutes regardless of
# how many ticks fire in between. ~120 in-game minutes (~2 in-game hours)
# matches the cozy "linger over a thoughtful gift for a couple of hours" feel
# described in `docs/AI_ARCHITECTURE.md` HH-006.
DEFAULT_PIN_DURATION_MINUTES = 120
# Reinforcement weight applied to the pinned mood on every tick while the pin
# is active. Small enough that it doesn't overwhelm the baseline drift on the
# adjacent moods, large enough that when the pin eventually expires the
# score-resolved mood still reflects the lingering warmth of the loved gift.
PINNED_MOOD_TICK_REINFORCEMENT = 0.45
MINUTES_PER_GAME_DAY = 1440


class MoodTracker:
    """Stores slow-moving mood in the villager's self relationship metadata."""

    def __init__(self, memory_store: MemoryStore) -> None:
        self.memory_store = memory_store

    def current_mood(self, villager_id: str, *, world: Any = None) -> str:
        state = self._load_state(villager_id)
        pinned = self._active_pin(state, world)
        if pinned is not None:
            return pinned
        return str(state.get("current") or self._dominant_mood(state.get("scores", {})))

    def nudge(self, villager_id: str, mood: str, weight: float) -> str:
        if mood not in MOODS:
            mood = "content"

        state = self._load_state(villager_id)
        scores = self._scores(state)
        scores[mood] += max(0.0, float(weight))
        scores = self._normalize(scores)
        scores = self._clamp_negative_moods(scores)
        current = self._dominant_mood(scores)
        # An active mood pin overrides the score-resolved dominant when the pin
        # window has not yet elapsed. We deliberately don't have `world` here, so
        # we trust the persisted pin metadata until `tick()` (which does have
        # world) clears it.
        pinned_mood = state.get("pinned_mood")
        if isinstance(pinned_mood, str) and pinned_mood in MOODS and state.get("pinned_until_minute") is not None:
            current = pinned_mood
        self._save_state(
            villager_id,
            scores,
            current,
            pinned_mood=state.get("pinned_mood"),
            pinned_until_minute=state.get("pinned_until_minute"),
        )
        return current

    def tick(self, villager_id: str, world_state: Any, personality: Personality) -> str:
        time_label = self._time_label(world_state)
        baseline = self._baseline_for_time(personality, time_label)

        state = self._load_state(villager_id)
        scores = self._scores(state)
        scores[baseline] += 0.36

        for adjacent in self._stable_adjacent_moods(villager_id, baseline, time_label):
            scores[adjacent] += 0.04

        # HH-006 mood pin: if a pin is active (e.g. delighted from a loved gift)
        # add a small reinforcement weight to the pinned mood every tick so the
        # score-resolved mood doesn't fight the pin. When the pin window has
        # elapsed, clear the pin metadata and let the baseline tick reassert.
        pinned_mood = state.get("pinned_mood") if isinstance(state.get("pinned_mood"), str) else None
        pinned_until_minute = state.get("pinned_until_minute")
        current_total_minutes = self._total_game_minutes(world_state)
        pin_active = (
            pinned_mood in MOODS
            and isinstance(pinned_until_minute, int)
            and current_total_minutes is not None
            and current_total_minutes < pinned_until_minute
        )
        if pin_active:
            scores[pinned_mood] += PINNED_MOOD_TICK_REINFORCEMENT
            next_pinned_mood: str | None = pinned_mood
            next_pinned_until: int | None = int(pinned_until_minute)
        else:
            # Expired or no pin: drop the metadata so subsequent ticks behave
            # like the pre-HH-006 baseline. If pinned_until_minute was set but
            # we couldn't compute current minute (world without day/minute),
            # err on the side of preserving the pin so demo determinism holds.
            if (
                pinned_mood in MOODS
                and isinstance(pinned_until_minute, int)
                and current_total_minutes is None
            ):
                next_pinned_mood = pinned_mood
                next_pinned_until = int(pinned_until_minute)
                scores[pinned_mood] += PINNED_MOOD_TICK_REINFORCEMENT
                pin_active = True
            else:
                next_pinned_mood = None
                next_pinned_until = None

        scores = self._normalize(scores)
        scores = self._clamp_negative_moods(scores)
        current = pinned_mood if pin_active else self._dominant_mood(scores)
        self._save_state(
            villager_id,
            scores,
            current,
            pinned_mood=next_pinned_mood,
            pinned_until_minute=next_pinned_until,
        )
        return current

    def pin(
        self,
        villager_id: str,
        mood: str,
        *,
        world: Any,
        duration_minutes: int = DEFAULT_PIN_DURATION_MINUTES,
    ) -> str:
        """Pin a villager's reported mood for ``duration_minutes`` in-game minutes.

        While the pin is active, ``current_mood`` and ``tick`` return ``mood``
        regardless of the score distribution, so a "loved gift" reading of
        ``excited`` is not erased by the next baseline tick a couple of real
        seconds later. Scores still drift in the background, so when the pin
        eventually expires the dominant mood reflects the lingering warmth
        rather than snapping back to a stale baseline.

        Returns the pinned mood (or, if ``mood`` is not in ``MOODS`` and falls
        back to ``content``, that fallback) for caller convenience.
        """
        if mood not in MOODS:
            mood = "content"
        duration = max(1, int(duration_minutes))
        current_total_minutes = self._total_game_minutes(world)
        if current_total_minutes is None:
            # No usable game clock — fall back to "now" being minute 0 so the
            # pin still expires after `duration` ticks of equivalent time.
            current_total_minutes = 0
        pin_deadline = int(current_total_minutes) + duration

        state = self._load_state(villager_id)
        scores = self._scores(state)
        # Give the pinned mood a meaningful initial weight so when the pin
        # eventually expires, the dominant mood doesn't snap back to whatever
        # the prior baseline was. This mirrors how `nudge` accumulates weight.
        scores[mood] += 1.0
        scores = self._normalize(scores)
        scores = self._clamp_negative_moods(scores)
        self._save_state(
            villager_id,
            scores,
            mood,
            pinned_mood=mood,
            pinned_until_minute=pin_deadline,
        )
        return mood

    def _active_pin(self, state: dict[str, Any], world: Any) -> str | None:
        pinned_mood = state.get("pinned_mood")
        pinned_until_minute = state.get("pinned_until_minute")
        if not isinstance(pinned_mood, str) or pinned_mood not in MOODS:
            return None
        if not isinstance(pinned_until_minute, int):
            return None
        if world is None:
            # No world context — trust the pin until tick() with world clears it.
            return pinned_mood
        current_total_minutes = self._total_game_minutes(world)
        if current_total_minutes is None:
            return pinned_mood
        if current_total_minutes >= pinned_until_minute:
            return None
        return pinned_mood

    def _total_game_minutes(self, world: Any) -> int | None:
        """Return monotonic in-game minute count from a world snapshot or state.

        Accepts a snapshot dict (``{"day": ..., "minute_of_day": ...}``), a
        ``WorldState`` object (or any object with a ``snapshot()`` method),
        or ``None``. Returns ``None`` if the snapshot doesn't expose both
        ``day`` and ``minute_of_day`` — in that case callers should preserve
        the existing pin metadata rather than clear it.
        """
        snapshot: dict[str, Any] | None = None
        if isinstance(world, dict):
            snapshot = world
        elif world is not None and hasattr(world, "snapshot"):
            try:
                snapshot = world.snapshot()
            except Exception:
                snapshot = None
        if not isinstance(snapshot, dict):
            return None
        day = snapshot.get("day")
        minute_of_day = snapshot.get("minute_of_day")
        if not isinstance(day, int) or not isinstance(minute_of_day, int):
            return None
        return max(0, (day - 1) * MINUTES_PER_GAME_DAY + int(minute_of_day))

    def _load_state(self, villager_id: str) -> dict[str, Any]:
        relationship = self.memory_store.get_relationship(villager_id, "self")
        metadata = relationship.get("metadata", {})
        mood_state = metadata.get("mood_state", {})
        return mood_state if isinstance(mood_state, dict) else {}

    def _save_state(
        self,
        villager_id: str,
        scores: dict[str, float],
        current: str,
        *,
        pinned_mood: str | None = None,
        pinned_until_minute: int | None = None,
    ) -> None:
        mood_state: dict[str, Any] = {
            "current": current,
            "scores": {mood: round(score, 4) for mood, score in scores.items()},
        }
        if pinned_mood and pinned_until_minute is not None:
            mood_state["pinned_mood"] = pinned_mood
            mood_state["pinned_until_minute"] = int(pinned_until_minute)
        else:
            # Explicit None clears any stale pin metadata.
            mood_state["pinned_mood"] = None
            mood_state["pinned_until_minute"] = None
        self.memory_store.update_relationship(
            villager_id,
            "self",
            metadata={"mood_state": mood_state},
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

    def _clamp_negative_moods(self, scores: dict[str, float]) -> dict[str, float]:
        """Cap intensity of bad-mood scores so cozy villagers never stew.

        For each mood listed in NEGATIVE_MOOD_INTENSITY_CAPS, if its normalized
        score exceeds the cap we clamp it to the cap and redirect the excess to
        its adjacent moods (or to `content` if it has none). This keeps the
        distribution summing to 1.0 while preventing one harsh turn from leaving
        a villager prickly all afternoon.
        """
        clamped = dict(scores)
        for mood, cap in NEGATIVE_MOOD_INTENSITY_CAPS.items():
            current = float(clamped.get(mood, 0.0))
            if current <= cap:
                continue
            excess = current - cap
            clamped[mood] = cap
            neighbors = [
                neighbor for neighbor in ADJACENT_MOODS.get(mood, []) if neighbor in clamped
            ]
            if not neighbors:
                clamped["content"] = clamped.get("content", 0.0) + excess
                continue
            share = excess / len(neighbors)
            for neighbor in neighbors:
                clamped[neighbor] = float(clamped.get(neighbor, 0.0)) + share
        return clamped

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
