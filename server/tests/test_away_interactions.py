"""Smoke test for villager-to-villager away interactions.

Run from the repo root:

    python -m server.tests.test_away_interactions
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from server.ai.memory import MemoryStore
from server.ai.personality import PersonalityStore
from server.mobile.notifications import compose_notifications
from server.world.away import AwayInteractionEngine
from server.world.events import EventLog
from server.world.state import WorldState


def run_away_interaction_check() -> None:
    with TemporaryDirectory() as tmp_dir:
        memory_store = MemoryStore(Path(tmp_dir) / "away_interactions.sqlite3")
        personality_store = PersonalityStore()
        event_log = EventLog()
        engine = AwayInteractionEngine(
            memory_store=memory_store,
            personality_store=personality_store,
            world_state=WorldState.create_default(),
            event_log=event_log,
        )

        try:
            result = engine.run_tick(actor_id="margot", target_id="fern", location="tea_garden")

            assert result["type"] == "away_interaction"
            assert result["actor"]["id"] == "margot"
            assert result["target"]["id"] == "fern"
            assert result["topic"] == "tea"
            assert result["event"]["kind"] == "villager_interaction"
            assert result["event"]["location"] == "tea_garden"

            margot_relationship = memory_store.peek_relationship("margot", "fern")
            fern_relationship = memory_store.peek_relationship("fern", "margot")
            assert margot_relationship is not None
            assert fern_relationship is not None
            assert margot_relationship["affection"] == 1
            assert margot_relationship["trust"] == 1
            assert margot_relationship["familiarity"] == 1
            assert fern_relationship["affection"] == 1
            assert fern_relationship["metadata"]["last_interaction_topic"] == "tea"

            margot_memories = memory_store.query_memories(
                villager_id="margot",
                subject_id="fern",
                kind="villager_interaction",
                limit=5,
            )
            fern_memories = memory_store.query_memories(
                villager_id="fern",
                subject_id="margot",
                kind="villager_interaction",
                limit=5,
            )
            assert len(margot_memories) == 1
            assert len(fern_memories) == 1
            assert "Fern" in margot_memories[0].text
            assert "Margot" in fern_memories[0].text
            assert margot_memories[0].metadata["topic"] == "tea"
            assert margot_memories[0].metadata["location"] == "tea_garden"
            assert margot_memories[0].metadata["other_villager_id"] == "fern"

            events = memory_store.get_recent_events(limit=5)
            assert len(events) == 1
            event = events[0]
            assert event.kind == "villager_interaction"
            assert event.actor_id == "margot"
            assert event.target_id == "fern"
            assert event.metadata["actor_memory_id"] == margot_memories[0].id
            assert event.metadata["target_memory_id"] == fern_memories[0].id
            assert event.metadata["topic"] == "tea"

            notifications = compose_notifications(events, personality_store)
            assert len(notifications) == 1
            notification = notifications[0]
            assert notification["event_kind"] == "villager_interaction"
            assert notification["villager_id"] == "fern"
            assert "Margot and Fern" in notification["body"]
            assert notification["metadata"]["topic"] == "tea"
            assert notification["metadata"]["actor_memory_id"] == margot_memories[0].id

            batch = engine.run_ticks(count=2, actor_id="margot", target_id="fern", location="tea_garden")
            assert batch["type"] == "away_interaction_batch"
            assert batch["requested_count"] == 2
            assert batch["count"] == 2
            assert len(batch["ticks"]) == 2
            assert all(tick["event"]["kind"] == "villager_interaction" for tick in batch["ticks"])

            updated_relationship = memory_store.peek_relationship("margot", "fern")
            assert updated_relationship is not None
            assert updated_relationship["affection"] == 3
            assert updated_relationship["trust"] == 3
            assert updated_relationship["familiarity"] == 3

            batch_events = memory_store.query_events(
                kind="villager_interaction",
                actor_id="margot",
                target_id="fern",
                limit=5,
            )
            assert len(batch_events) == 3
            batch_notifications = compose_notifications(batch_events, personality_store)
            assert len(batch_notifications) == 3
            assert all(item["event_kind"] == "villager_interaction" for item in batch_notifications)
        finally:
            memory_store.close()


def main() -> None:
    run_away_interaction_check()
    print("PASS: Away interaction tick creates reciprocal memories, relationships, events, and notifications.")


if __name__ == "__main__":
    main()
