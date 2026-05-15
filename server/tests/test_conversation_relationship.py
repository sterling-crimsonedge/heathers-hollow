"""Smoke test for conversation memory, relationship, turns, and events.

Run from the repo root:

    python -m server.tests.test_conversation_relationship
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from server.ai.conversation import ConversationEngine
from server.ai.memory import MemoryStore
from server.ai.personality import PersonalityStore
from server.world.events import EventLog
from server.world.state import WorldState


async def run_conversation_relationship_check() -> None:
    with TemporaryDirectory() as tmp_dir:
        memory_store = MemoryStore(Path(tmp_dir) / "conversation_relationship.sqlite3")
        event_log = EventLog()
        engine = ConversationEngine(
            memory_store=memory_store,
            personality_store=PersonalityStore(),
            world_state=WorldState.create_default(),
            event_log=event_log,
        )

        try:
            response = await engine.handle_player_message(
                player_id="heather",
                villager_id="margot",
                text="I love tiny porcelain teacups, and my favorite flower is lavender.",
                context={"location": "town_square", "test": "conversation_relationship"},
            )

            assert response["type"] == "villager_reply"
            assert response["mood"] == "warm"
            # Margot's HH-006 `tuning` block sets `affection_per_talk_cap: 1`
            # and `trust_per_talk_cap: 0` (see server/data/personalities/margot.json
            # and docs/AI_ARCHITECTURE.md). Her seeded heather row starts at
            # affection 8 / trust 12 / familiarity 2; one personal-disclosure
            # turn earns +1 affection (capped at 1), +0 trust (capped at 0),
            # and +1 familiarity. Trust intentionally stays at 12 — Margot's
            # slow-trust register is what makes loved gifts (a separate path
            # with its own delta) feel like a real event.
            assert response["relationship"] == {
                "affection": 9,
                "trust": 12,
                "familiarity": 3,
                "tension": 0,
            }

            memory = next(
                item for item in memory_store.get_recent_memories("margot", limit=5)
                if item.id == response["memory_id"]
            )
            assert memory.kind == "conversation"
            assert memory.subject_id == "heather"
            assert memory.emotion == "warm"
            assert memory.metadata["player_text"] == "I love tiny porcelain teacups, and my favorite flower is lavender."
            assert memory.metadata["villager_reply"] == response["text"]
            assert memory.metadata["context"]["location"] == "town_square"
            assert "world" in memory.metadata

            conversation_id = memory.metadata["conversation_id"]
            turns = memory_store.get_conversation_turns(conversation_id)
            assert len(turns) == 2
            assert turns[0].speaker == "heather"
            assert turns[0].text == "I love tiny porcelain teacups, and my favorite flower is lavender."
            assert turns[0].metadata["context"]["test"] == "conversation_relationship"
            assert turns[1].speaker == "margot"
            assert turns[1].text == response["text"]
            assert turns[1].metadata["mood"] == "warm"
            assert turns[1].metadata["memories_used"] == []

            live_event = event_log.recent(limit=1)[0]
            assert live_event.kind == "conversation"
            assert live_event.actor_id == "heather"
            assert live_event.target_id == "margot"
            assert live_event.location == "town_square"
            assert live_event.metadata["memory_id"] == response["memory_id"]
            assert live_event.metadata["mood"] == "warm"

            persisted_event = memory_store.get_recent_events(limit=1)[0]
            assert persisted_event.kind == "conversation"
            assert persisted_event.actor_id == "heather"
            assert persisted_event.target_id == "margot"
            assert persisted_event.location == "town_square"
            assert persisted_event.metadata["memory_id"] == response["memory_id"]
            assert persisted_event.metadata["mood"] == "warm"
        finally:
            memory_store.close()


def main() -> None:
    asyncio.run(run_conversation_relationship_check())
    print("PASS: Conversation relationship, turns, memory, and events are consistent.")


if __name__ == "__main__":
    main()
