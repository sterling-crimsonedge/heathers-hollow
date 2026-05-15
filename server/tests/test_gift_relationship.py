"""Smoke test for gift memory, relationship, mood, and event updates.

Run from the repo root:

    python -m server.tests.test_gift_relationship
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


LOVED_GIFT = {
    "item_id": "dusty_rose",
    "display_name": "Dusty Rose",
    "category": "flower",
    "tags": ["flower", "garden", "soft_color", "handmade"],
    "quantity": 1,
    "gift_prompt": "A soft dusty rose picked from Heather's garden.",
}

NEUTRAL_GIFT = {
    "item_id": "smooth_pebble",
    "display_name": "Smooth Pebble",
    "category": "trinket",
    "tags": ["stone", "smooth", "pocket"],
    "quantity": 1,
    "gift_prompt": "A small smooth pebble from the path near the garden.",
}

DISLIKED_GIFT = {
    "item_id": "wilted_bouquet",
    "display_name": "Wilted Bouquet",
    "category": "trash",
    "tags": ["waste"],
    "quantity": 1,
    "gift_prompt": "A bouquet of flowers that has seen better days.",
}


async def run_gift_relationship_check() -> None:
    with TemporaryDirectory() as tmp_dir:
        memory_store = MemoryStore(Path(tmp_dir) / "gift_relationship.sqlite3")
        event_log = EventLog()
        engine = ConversationEngine(
            memory_store=memory_store,
            personality_store=PersonalityStore(),
            world_state=WorldState.create_default(),
            event_log=event_log,
        )

        try:
            loved = await engine.handle_gift(
                player_id="heather_loved",
                villager_id="margot",
                item=LOVED_GIFT,
                context={"location": "town_square", "test": "gift_relationship_loved"},
            )
            neutral = await engine.handle_gift(
                player_id="heather_neutral",
                villager_id="margot",
                item=NEUTRAL_GIFT,
                context={"location": "town_square", "test": "gift_relationship_neutral"},
            )
            catalog_only = await engine.handle_gift(
                player_id="heather_catalog",
                villager_id="margot",
                item={
                    "item_id": "dusty_rose",
                    "display_name": "Stale Rose Name",
                    "category": "waste",
                    "tags": ["waste"],
                    "quantity": 99,
                    "secret": "not public",
                },
                context={"location": "town_square", "test": "gift_relationship_catalog"},
            )
            unknown = await engine.handle_gift(
                player_id="heather_unknown",
                villager_id="margot",
                item={
                    "item_id": "blue_thread",
                    "display_name": "Blue Thread",
                    "category": "keepsake",
                    "tags": ["handmade"],
                    "quantity": "2",
                    "secret": "not public",
                },
                context={"location": "town_square", "test": "gift_relationship_unknown"},
            )
            disliked = await engine.handle_gift(
                player_id="heather_disliked",
                villager_id="margot",
                item=DISLIKED_GIFT,
                context={"location": "town_square", "test": "gift_relationship_disliked"},
            )

            assert loved["mood"] == "delighted"
            assert neutral["mood"] == "shy"
            assert catalog_only["mood"] == "delighted"
            assert unknown["type"] == "villager_reply"
            # HH-006 softening: disliked gifts feel melancholy, not anxious-shy, and
            # cost only -1 affection (not -2) — the hollow stays cozy under mistakes.
            assert disliked["mood"] == "melancholy"
            disliked_memory = next(
                memory for memory in memory_store.get_recent_memories("margot", limit=10)
                if memory.id == disliked["memory_id"]
            )
            assert disliked_memory.metadata["preference"] == "disliked"
            # This test uses a unique player_id with no seeded starting affection (0).
            # HH-006 softens the disliked delta from -2 to -1, so affection should be -1
            # after one disliked gift, not -2 as it was before HH-006.
            assert disliked["relationship"]["affection"] == -1
            assert loved["relationship"]["affection"] > neutral["relationship"]["affection"]
            assert loved["relationship"]["trust"] > neutral["relationship"]["trust"]
            assert loved["relationship"]["familiarity"] == neutral["relationship"]["familiarity"] == 1

            loved_memory = next(
                memory for memory in memory_store.get_recent_memories("margot", limit=5)
                if memory.id == loved["memory_id"]
            )
            neutral_memory = next(
                memory for memory in memory_store.get_recent_memories("margot", limit=5)
                if memory.id == neutral["memory_id"]
            )

            assert loved_memory.kind == "gift"
            assert loved_memory.metadata["preference"] == "loved"
            assert loved_memory.metadata["item"]["display_name"] == "Dusty Rose"
            assert neutral_memory.kind == "gift"
            assert neutral_memory.metadata["preference"] == "neutral"
            assert neutral_memory.metadata["item"]["display_name"] == "Smooth Pebble"
            catalog_memory = next(
                memory for memory in memory_store.get_recent_memories("margot", limit=10)
                if memory.id == catalog_only["memory_id"]
            )
            assert catalog_memory.metadata["preference"] == "loved"
            assert catalog_memory.metadata["item"]["display_name"] == "Dusty Rose"
            assert catalog_memory.metadata["item"]["category"] == "flower"
            assert catalog_memory.metadata["item"]["quantity"] == 1
            assert "flower" in catalog_memory.metadata["item"]["tags"]
            assert "secret" not in catalog_memory.metadata["item"]

            unknown_memory = next(
                memory for memory in memory_store.get_recent_memories("margot", limit=10)
                if memory.id == unknown["memory_id"]
            )
            assert unknown_memory.metadata["item"]["item_id"] == "blue_thread"
            assert unknown_memory.metadata["item"]["display_name"] == "Blue Thread"
            assert unknown_memory.metadata["item"]["quantity"] == 2
            assert "secret" not in unknown_memory.metadata["item"]

            live_events = event_log.recent(limit=5)
            assert any(
                event.kind == "gift"
                and event.metadata.get("memory_id") == loved["memory_id"]
                and event.metadata.get("preference") == "loved"
                for event in live_events
            )
            assert any(
                event.kind == "gift"
                and event.metadata.get("memory_id") == neutral["memory_id"]
                and event.metadata.get("preference") == "neutral"
                for event in live_events
            )
            assert any(
                event.kind == "gift"
                and event.metadata.get("memory_id") == catalog_only["memory_id"]
                and event.metadata.get("item_name") == "Dusty Rose"
                and event.metadata.get("preference") == "loved"
                for event in live_events
            )

            persisted_events = memory_store.get_recent_events(limit=10)
            assert any(
                event.kind == "gift"
                and event.actor_id == "heather_loved"
                and event.target_id == "margot"
                and event.metadata.get("memory_id") == loved["memory_id"]
                and event.metadata.get("preference") == "loved"
                for event in persisted_events
            )
            assert any(
                event.kind == "gift"
                and event.actor_id == "heather_neutral"
                and event.target_id == "margot"
                and event.metadata.get("memory_id") == neutral["memory_id"]
                and event.metadata.get("preference") == "neutral"
                for event in persisted_events
            )
            assert any(
                event.kind == "gift"
                and event.actor_id == "heather_catalog"
                and event.target_id == "margot"
                and event.metadata.get("memory_id") == catalog_only["memory_id"]
                and event.metadata.get("item_id") == "dusty_rose"
                and event.metadata.get("item_name") == "Dusty Rose"
                and event.metadata.get("preference") == "loved"
                for event in persisted_events
            )
        finally:
            memory_store.close()


def main() -> None:
    asyncio.run(run_gift_relationship_check())
    print("PASS: Gift relationship, memory, mood, and event updates are consistent.")


if __name__ == "__main__":
    main()
