"""Smoke test for the local demo state seed utility.

Run from the repo root:

    python -m server.tests.test_demo_seed
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from server.ai.memory import MemoryStore
from server.tools.seed_demo_state import seed_demo_state


async def run_demo_seed_check() -> None:
    with TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "seeded_demo.sqlite3"
        summary = await seed_demo_state(db_path=db_path)

        assert summary["db_path"] == str(db_path)
        assert "porcelain" in summary["recall_reply"].lower() or "fox" in summary["recall_reply"].lower()
        assert "Dusty Rose" in summary["gift_reply"]
        assert summary["relationship"]["affection"] > 8
        assert summary["relationship"]["trust"] > 12
        assert summary["relationship"]["last_gift"] == "Dusty Rose"
        assert summary["relationship"]["last_gift_preference"] == "loved"
        assert summary["conversation_memory_count"] >= 2
        assert summary["gift_memory_count"] == 1
        assert summary["away_tick_count"] == 1
        assert summary["away_memory_count"] == 2
        assert summary["relationship_edge_count"] >= 3
        assert summary["event_count"] >= 3
        assert summary["notification_count"] >= 3
        assert summary["latest_notification"]
        assert summary["latest_notification"]["event_kind"] == "villager_interaction"

        memory_store = MemoryStore(db_path)
        try:
            relationship = memory_store.peek_relationship("margot", "heather")
            assert relationship is not None
            assert relationship["metadata"]["last_gift"] == "Dusty Rose"
            margot_fern = memory_store.peek_relationship("margot", "fern")
            assert margot_fern is not None
            assert margot_fern["metadata"]["last_interaction_topic"] == "tea"

            conversation_memories = memory_store.query_memories(
                villager_id="margot",
                subject_id="heather",
                kind="conversation",
                limit=10,
            )
            gift_memories = memory_store.query_memories(
                villager_id="margot",
                subject_id="heather",
                kind="gift",
                limit=10,
            )
            away_memories = memory_store.query_memories(
                villager_id="margot",
                subject_id="fern",
                kind="villager_interaction",
                limit=10,
            )
            relationship_edges = memory_store.query_relationships(villager_id="margot", limit=10)
            events = memory_store.get_recent_events(limit=10)
        finally:
            memory_store.close()

        assert any("porcelain fox" in memory.text.lower() for memory in conversation_memories)
        assert len(gift_memories) == 1
        assert gift_memories[0].metadata["preference"] == "loved"
        assert len(away_memories) == 1
        assert away_memories[0].metadata["topic"] == "tea"
        assert any(edge["subject_id"] == "fern" for edge in relationship_edges)
        assert any(event.kind == "conversation" for event in events)
        assert any(event.kind == "gift" for event in events)
        assert any(event.kind == "villager_interaction" for event in events)


def main() -> None:
    asyncio.run(run_demo_seed_check())
    print("PASS: Demo seed utility writes player and away-activity storylines.")


if __name__ == "__main__":
    main()
