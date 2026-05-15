"""Smoke test for configurable world-clock speed.

Run from the repo root:

    python -m server.tests.test_world_state
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

from server.world.state import DEFAULT_DAY_LENGTH_SECONDS, WorldState


def run_world_state_check() -> None:
    original_value = os.environ.get("HOLLOW_DAY_LENGTH_SECONDS")
    try:
        os.environ["HOLLOW_DAY_LENGTH_SECONDS"] = "300"
        world = WorldState.create_default()
        assert world.day_length_seconds == 300

        world.start_time = datetime.now(UTC) - timedelta(seconds=60)
        snapshot = world.snapshot()
        assert snapshot["day_length_seconds"] == 300
        assert snapshot["minute_of_day"] == (8 * 60 + 288) % 1440

        os.environ.pop("HOLLOW_DAY_LENGTH_SECONDS", None)
        default_world = WorldState.create_default()
        assert default_world.day_length_seconds == DEFAULT_DAY_LENGTH_SECONDS
    finally:
        if original_value is None:
            os.environ.pop("HOLLOW_DAY_LENGTH_SECONDS", None)
        else:
            os.environ["HOLLOW_DAY_LENGTH_SECONDS"] = original_value


def main() -> None:
    run_world_state_check()
    print("PASS: WorldState honors HOLLOW_DAY_LENGTH_SECONDS.")


if __name__ == "__main__":
    main()
