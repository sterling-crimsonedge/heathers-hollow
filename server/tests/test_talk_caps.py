"""Smoke test for HH-006 talk-path daily caps.

Run from the repo root:

    python -m server.tests.test_talk_caps

These caps prevent slot-machine warmth: ten positive turns in one in-game day
should not max out Margot's affection or trust, and negative talk should never
drop a fresh player's affection below zero. Counters reset on a new in-game day.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from server.ai.conversation import (
    ConversationEngine,
    TALK_AFFECTION_DAILY_CAP,
    TALK_NEGATIVE_DAILY_CAP,
    TALK_TRUST_DAILY_CAP,
)
from server.ai.memory import MemoryStore
from server.ai.personality import PersonalityStore
from server.world.events import EventLog
from server.world.state import WorldState


POSITIVE_PERSONAL_TEXT = "I love porcelain teacups and my favorite flower is lavender."
NEGATIVE_TEXT = "You are awful and mean."


async def _drive_turns(
    engine: ConversationEngine,
    *,
    player_id: str,
    text: str,
    count: int,
    location: str = "town_square",
) -> dict[str, object]:
    response: dict[str, object] = {}
    for _ in range(count):
        response = await engine.handle_player_message(
            player_id=player_id,
            villager_id="margot",
            text=text,
            context={"location": location, "test": "talk_caps"},
        )
    return response


async def run_talk_caps_check() -> None:
    with TemporaryDirectory() as tmp_dir:
        memory_store = MemoryStore(Path(tmp_dir) / "talk_caps.sqlite3")
        event_log = EventLog()
        engine = ConversationEngine(
            memory_store=memory_store,
            personality_store=PersonalityStore(),
            world_state=WorldState.create_default(),
            event_log=event_log,
        )

        try:
            # 1) Positive cap. A fresh player_id has no seeded affection/trust with
            #    Margot, so the daily caps should be the only thing limiting growth.
            positive_player = "heather_caps_positive"
            positive = await _drive_turns(
                engine,
                player_id=positive_player,
                text=POSITIVE_PERSONAL_TEXT,
                count=10,
            )
            positive_rel = positive["relationship"]  # type: ignore[index]
            assert positive_rel["affection"] == TALK_AFFECTION_DAILY_CAP, positive_rel
            assert positive_rel["trust"] == TALK_TRUST_DAILY_CAP, positive_rel
            assert positive_rel["familiarity"] >= 10, positive_rel

            stored = memory_store.get_relationship("margot", positive_player)
            stored_meta = stored.get("metadata", {})
            assert stored_meta.get("talk_affection_today") == TALK_AFFECTION_DAILY_CAP, stored_meta
            assert stored_meta.get("talk_trust_today") == TALK_TRUST_DAILY_CAP, stored_meta
            assert stored_meta.get("talk_negative_today") == 0, stored_meta
            assert isinstance(stored_meta.get("last_talk_day"), int), stored_meta

            # 2) Negative floor. A fresh player at affection 0 should never go
            #    below 0 from talk alone, even after multiple negative turns.
            negative_player = "heather_caps_negative"
            negative = await _drive_turns(
                engine,
                player_id=negative_player,
                text=NEGATIVE_TEXT,
                count=5,
            )
            negative_rel = negative["relationship"]  # type: ignore[index]
            assert negative_rel["affection"] == 0, negative_rel
            assert negative_rel["familiarity"] >= 5, negative_rel

            negative_stored = memory_store.get_relationship("margot", negative_player)
            negative_stored_meta = negative_stored.get("metadata", {})
            # Floor short-circuits the counter: when the delta is clamped to 0
            # the negative tally does not advance, so cap stays untouched.
            assert negative_stored_meta.get("talk_negative_today") == 0, negative_stored_meta
            assert TALK_NEGATIVE_DAILY_CAP >= 1

            # 3) Seeded relationship case. Margot/heather starts at affection 8 and
            #    trust 12. One negative talk turn should subtract -1 affection (the
            #    daily cap), and the next negative turn the same day should not.
            seeded_first = await _drive_turns(
                engine,
                player_id="heather",
                text=NEGATIVE_TEXT,
                count=1,
            )
            seeded_first_rel = seeded_first["relationship"]  # type: ignore[index]
            assert seeded_first_rel["affection"] == 7, seeded_first_rel  # 8 - 1
            seeded_again = await _drive_turns(
                engine,
                player_id="heather",
                text=NEGATIVE_TEXT,
                count=1,
            )
            seeded_again_rel = seeded_again["relationship"]  # type: ignore[index]
            # Same day -> additional negatives are clamped to 0 affection delta.
            assert seeded_again_rel["affection"] == 7, seeded_again_rel
            # Familiarity still climbs by 1 each turn.
            assert seeded_again_rel["familiarity"] == seeded_first_rel["familiarity"] + 1

            # 4) Counter reset on a new in-game day. We simulate the day rollover
            #    by stamping a stale last_talk_day onto the positive player's row.
            positive_stored = memory_store.get_relationship("margot", positive_player)
            positive_stored_meta = dict(positive_stored.get("metadata", {}))
            stale_day = int(positive_stored_meta.get("last_talk_day") or 1) - 1
            positive_stored_meta["last_talk_day"] = stale_day
            memory_store.update_relationship(
                "margot",
                positive_player,
                metadata=positive_stored_meta,
            )
            rollover = await _drive_turns(
                engine,
                player_id=positive_player,
                text=POSITIVE_PERSONAL_TEXT,
                count=1,
            )
            rollover_rel = rollover["relationship"]  # type: ignore[index]
            # The new day's first positive turn should grant +1 affection and +1 trust again.
            assert rollover_rel["affection"] == TALK_AFFECTION_DAILY_CAP + 1, rollover_rel
            assert rollover_rel["trust"] == TALK_TRUST_DAILY_CAP + 1, rollover_rel
        finally:
            memory_store.close()


def main() -> None:
    asyncio.run(run_talk_caps_check())
    print("PASS: Talk-path daily caps enforce affection/trust limits and the cozy floor.")


if __name__ == "__main__":
    main()
