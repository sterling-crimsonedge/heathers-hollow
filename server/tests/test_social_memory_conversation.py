"""Smoke test for social memory use during player conversations.

Run from the repo root:

    python -m server.tests.test_social_memory_conversation
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from server.ai.conversation import ConversationEngine
from server.ai.memory import MemoryStore
from server.ai.personality import PersonalityStore
from server.world.away import AwayInteractionEngine
from server.world.events import EventLog
from server.world.state import WorldState


async def run_social_memory_conversation_check() -> None:
    with TemporaryDirectory() as tmp_dir:
        memory_store = MemoryStore(Path(tmp_dir) / "social_memory_conversation.sqlite3")
        personality_store = PersonalityStore()
        world_state = WorldState.create_default()
        event_log = EventLog()
        conversation_engine = ConversationEngine(
            memory_store=memory_store,
            personality_store=personality_store,
            world_state=world_state,
            event_log=event_log,
        )
        away_engine = AwayInteractionEngine(
            memory_store=memory_store,
            personality_store=personality_store,
            world_state=world_state,
            event_log=event_log,
        )

        try:
            away = away_engine.run_tick(actor_id="margot", target_id="fern", location="tea_garden")
            social_memory_id = int(away["event"]["metadata"]["actor_memory_id"])

            response = await conversation_engine.handle_player_message(
                player_id="heather",
                villager_id="margot",
                text="What do you think about Fern lately?",
                context={"location": "town_square", "test": "social_memory_conversation"},
            )

            reply = str(response["text"]).lower()
            assert response["type"] == "villager_reply"
            assert "fern" in reply
            assert "tea" in reply
            assert social_memory_id in response["memories_used"]

            social_relationship = memory_store.peek_relationship("margot", "fern")
            assert social_relationship is not None
            assert social_relationship["metadata"]["last_interaction_topic"] == "tea"

            conversation_memory = next(
                memory
                for memory in memory_store.get_recent_memories("margot", limit=5)
                if memory.id == response["memory_id"]
            )
            assert social_memory_id in conversation_memory.metadata["memories_used"]
            assert conversation_memory.metadata["social_memory_ids"] == [social_memory_id]

            conversation_id = conversation_memory.metadata["conversation_id"]
            turns = memory_store.get_conversation_turns(conversation_id)
            assert turns[1].speaker == "margot"
            assert social_memory_id in turns[1].metadata["memories_used"]

            persisted_event = memory_store.get_recent_events(limit=1)[0]
            assert persisted_event.kind == "conversation"
            assert persisted_event.metadata["memory_id"] == response["memory_id"]
            assert social_memory_id in persisted_event.metadata["memories_used"]
            assert persisted_event.metadata["social_memory_ids"] == [social_memory_id]
        finally:
            memory_store.close()


def main() -> None:
    asyncio.run(run_social_memory_conversation_check())
    print("PASS: Conversation replies use referenced villager social memories.")


if __name__ == "__main__":
    main()
