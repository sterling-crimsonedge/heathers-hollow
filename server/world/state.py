"""Authoritative world state for Heather's Hollow."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime


DEFAULT_DAY_LENGTH_SECONDS = 3600
SECONDS_PER_GAME_DAY = 24 * 60


def day_length_seconds_from_env() -> int:
    raw_value = os.getenv("HOLLOW_DAY_LENGTH_SECONDS")
    if raw_value is None:
        return DEFAULT_DAY_LENGTH_SECONDS

    try:
        value = int(raw_value)
    except ValueError:
        return DEFAULT_DAY_LENGTH_SECONDS

    return value if value > 0 else DEFAULT_DAY_LENGTH_SECONDS


@dataclass
class WorldState:
    """Compressed in-game clock and simple ambient state."""

    start_time: datetime
    start_minute_of_day: int = 8 * 60
    day_length_seconds: int = DEFAULT_DAY_LENGTH_SECONDS
    season: str = "spring"
    weather: str = "clear"

    @classmethod
    def create_default(cls) -> "WorldState":
        return cls(start_time=datetime.now(UTC), day_length_seconds=day_length_seconds_from_env())

    def snapshot(self) -> dict[str, object]:
        now = datetime.now(UTC)
        elapsed_seconds = max(0.0, (now - self.start_time).total_seconds())
        game_minutes_per_second = SECONDS_PER_GAME_DAY / self.day_length_seconds
        total_game_minutes = self.start_minute_of_day + int(elapsed_seconds * game_minutes_per_second)
        day = 1 + total_game_minutes // 1440
        minute_of_day = total_game_minutes % 1440
        hour = minute_of_day // 60
        minute = minute_of_day % 60

        return {
            "day": day,
            "minute_of_day": minute_of_day,
            "clock": f"{hour:02d}:{minute:02d}",
            "time_label": self.time_label(minute_of_day),
            "season": self.season,
            "weather": self.weather,
            "day_length_seconds": self.day_length_seconds,
        }

    @staticmethod
    def time_label(minute_of_day: int) -> str:
        if 5 * 60 <= minute_of_day < 11 * 60:
            return "morning"
        if 11 * 60 <= minute_of_day < 17 * 60:
            return "afternoon"
        if 17 * 60 <= minute_of_day < 21 * 60:
            return "evening"
        return "night"
