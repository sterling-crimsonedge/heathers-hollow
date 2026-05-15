"""World state — authoritative time, weather, and ambient context.

Lives on the server so the future mobile companion app can read the same
state the game client sees. Villagers consult this when deciding what to
talk about.

Time progresses on a real-time-accelerated clock. Default: 1 in-game day
per real hour, configurable.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field


# Real seconds per in-game day. 3600 = 1 real hour per in-game day.
DEFAULT_DAY_LENGTH_SECONDS = 3600


# Time-of-day boundaries in fractional in-game hours [0..24)
# (start_hour_inclusive, end_hour_exclusive, label)
_TIME_BANDS = [
    (5.0,  7.0,  "dawn"),
    (7.0,  11.0, "morning"),
    (11.0, 14.0, "midday"),
    (14.0, 17.0, "afternoon"),
    (17.0, 20.0, "evening"),
    (20.0, 24.0, "night"),
    (0.0,  5.0,  "night"),
]


@dataclass
class WorldState:
    """In-memory authoritative world state. Cheap to read, occasionally persisted."""

    started_at_real_ts: float = field(default_factory=time.time)
    day_length_seconds: float = DEFAULT_DAY_LENGTH_SECONDS
    weather: str = "clear"
    season: str = "spring"
    villager_positions: dict[str, tuple[float, float]] = field(default_factory=dict)
    villager_activities: dict[str, str] = field(default_factory=dict)

    def in_game_hours(self) -> float:
        """Returns the current in-game time as a float in [0, 24)."""
        real_elapsed = time.time() - self.started_at_real_ts
        in_game_seconds = real_elapsed * (24 * 3600 / self.day_length_seconds)
        # start the world at 8am so first launch isn't dark
        return (8.0 + in_game_seconds / 3600.0) % 24.0

    def day_count(self) -> int:
        real_elapsed = time.time() - self.started_at_real_ts
        return int(real_elapsed / self.day_length_seconds)

    def time_of_day(self) -> str:
        h = self.in_game_hours()
        for start, end, label in _TIME_BANDS:
            if start <= h < end:
                return label
        return "night"

    def clock_string(self) -> str:
        h = self.in_game_hours()
        hour = int(h)
        minute = int((h - hour) * 60)
        return f"{hour:02d}:{minute:02d}"

    def light_intensity(self) -> float:
        """0.1 (deepest night) to 1.0 (brightest midday). Smooth, no banding."""
        h = self.in_game_hours()
        # cosine curve: 1.0 at 13:00, dips lowest around 01:00
        normalized = math.cos((h - 13.0) / 12.0 * math.pi)
        return max(0.1, 0.55 + 0.45 * normalized)

    def sky_color_hex(self) -> str:
        """Suggested sky color for the current time. Driven by time_of_day."""
        return _SKY_COLORS.get(self.time_of_day(), "#B6D0E2")

    def to_dict(self) -> dict:
        return {
            "in_game_time": self.clock_string(),
            "in_game_hours": round(self.in_game_hours(), 2),
            "time_of_day": self.time_of_day(),
            "day_count": self.day_count(),
            "weather": self.weather,
            "season": self.season,
            "light_intensity": round(self.light_intensity(), 3),
            "sky_color": self.sky_color_hex(),
            "villager_positions": self.villager_positions,
            "villager_activities": self.villager_activities,
        }

    def context_for_prompt(self) -> str:
        """A small, human-readable snippet of world state for Claude prompts."""
        tod = self.time_of_day()
        clock = self.clock_string()
        return (
            f"The current time in the village is {clock} ({tod}). "
            f"The season is {self.season}. The weather is {self.weather}."
        )


_SKY_COLORS = {
    "dawn": "#F2C57C",       # marigold dawn
    "morning": "#B6D0E2",    # soft blue
    "midday": "#A8C8E0",     # bright blue
    "afternoon": "#C9E0E2",  # pale blue
    "evening": "#E8B4B8",    # dusty rose sunset
    "night": "#3D3A55",      # wisteria-charcoal night
}
