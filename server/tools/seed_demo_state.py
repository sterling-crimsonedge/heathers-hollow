"""Seed a polished local demo storyline into the Heather's Hollow memory DB.

Run from the repo root:

    python -m server.tools.seed_demo_state

Use an isolated database:

    python -m server.tools.seed_demo_state --db-path /tmp/heathers-hollow-demo.sqlite3
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

from server.ai.conversation import ConversationEngine
from server.ai.memory import DEFAULT_DB_PATH, MemoryStore
from server.ai.personality import PersonalityStore
from server.mobile.notifications import compose_notifications
from server.world.away import AwayInteractionEngine
from server.world.events import EventLog
from server.world.state import WorldState


FACT_TEXT = "Margot, please remember that Heather keeps a tiny porcelain fox on the kitchen sill."
RECALL_TEXT = "Do you remember what I keep on the kitchen sill?"
DUSTY_ROSE = {
    "item_id": "dusty_rose",
    "display_name": "Dusty Rose",
    "category": "flower",
    "tags": ["flower", "garden", "soft_color", "handmade"],
    "quantity": 1,
}


async def seed_demo_state(
    *,
    db_path: str | Path | None = None,
    player_id: str = "heather",
    villager_id: str = "margot",
    away_ticks: int = 1,
    force_fallback: bool = True,
) -> dict[str, Any]:
    previous_api_key = os.environ.get("ANTHROPIC_API_KEY")
    previous_provider = os.environ.get("HOLLOW_LLM_PROVIDER")
    if force_fallback:
        os.environ.pop("ANTHROPIC_API_KEY", None)
        os.environ["HOLLOW_LLM_PROVIDER"] = "fallback"

    memory_store = MemoryStore(db_path)
    personality_store = PersonalityStore()
    event_log = EventLog()
    world_state = WorldState.create_default()
    engine = ConversationEngine(
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

    context = {"location": "town_square", "source": "seed_demo_state"}
    try:
        first = await engine.handle_player_message(
            player_id=player_id,
            villager_id=villager_id,
            text=FACT_TEXT,
            context=context,
        )
        recall = await engine.handle_player_message(
            player_id=player_id,
            villager_id=villager_id,
            text=RECALL_TEXT,
            context=context,
        )
        gift = await engine.handle_gift(
            player_id=player_id,
            villager_id=villager_id,
            item=DUSTY_ROSE,
            context=context,
        )
        away_results = [
            away_engine.run_tick(actor_id="margot", target_id="fern", location="tea_garden")
            for _ in range(max(0, int(away_ticks)))
        ]

        relationship = memory_store.peek_relationship(villager_id, player_id) or {}
        relationship_edges = memory_store.query_relationships(limit=50)
        conversation_memories = memory_store.query_memories(
            villager_id=villager_id,
            subject_id=player_id,
            kind="conversation",
            limit=10,
        )
        gift_memories = memory_store.query_memories(
            villager_id=villager_id,
            subject_id=player_id,
            kind="gift",
            limit=10,
        )
        away_memories = memory_store.query_memories(kind="villager_interaction", limit=20)
        events = memory_store.get_recent_events(limit=10)
        notifications = compose_notifications(events, personality_store)

        return {
            "db_path": str(memory_store.db_path),
            "first_reply": first["text"],
            "recall_reply": recall["text"],
            "gift_reply": gift["text"],
            "relationship": {
                "affection": int(relationship.get("affection", 0)),
                "trust": int(relationship.get("trust", 0)),
                "familiarity": int(relationship.get("familiarity", 0)),
                "tension": int(relationship.get("tension", 0)),
                "last_gift": relationship.get("metadata", {}).get("last_gift"),
                "last_gift_preference": relationship.get("metadata", {}).get("last_gift_preference"),
            },
            "conversation_memory_count": len(conversation_memories),
            "gift_memory_count": len(gift_memories),
            "away_tick_count": len(away_results),
            "away_memory_count": len(away_memories),
            "relationship_edge_count": len(relationship_edges),
            "event_count": len(events),
            "notification_count": len(notifications),
            "latest_notification": notifications[0] if notifications else None,
        }
    finally:
        memory_store.close()
        if force_fallback:
            if previous_api_key is None:
                os.environ.pop("ANTHROPIC_API_KEY", None)
            else:
                os.environ["ANTHROPIC_API_KEY"] = previous_api_key
            if previous_provider is None:
                os.environ.pop("HOLLOW_LLM_PROVIDER", None)
            else:
                os.environ["HOLLOW_LLM_PROVIDER"] = previous_provider


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed a deterministic Heather's Hollow demo storyline.")
    parser.add_argument(
        "--db-path",
        default=None,
        help=f"SQLite DB path to seed. Default: HH_MEMORY_DB or {DEFAULT_DB_PATH}",
    )
    parser.add_argument("--player-id", default="heather", help="Player/subject id to seed. Default: heather")
    parser.add_argument("--villager-id", default="margot", help="Villager id to seed. Default: margot")
    parser.add_argument(
        "--away-ticks",
        type=int,
        default=1,
        help="Number of deterministic villager-to-villager away interactions to seed. Default: 1",
    )
    parser.add_argument(
        "--live-claude",
        action="store_true",
        help="Use the configured live LLM provider instead of forcing deterministic fallback mode.",
    )
    parser.add_argument("--json", action="store_true", help="Print the seed summary as JSON.")
    return parser.parse_args()


def print_summary(summary: dict[str, Any]) -> None:
    relationship = summary["relationship"]
    print("Seeded Heather's Hollow demo state.")
    print(f"DB: {summary['db_path']}")
    print(f"Recall reply: {summary['recall_reply']}")
    print(f"Gift reply: {summary['gift_reply']}")
    print(
        "Relationship: "
        f"affection {relationship['affection']}, "
        f"trust {relationship['trust']}, "
        f"familiarity {relationship['familiarity']}, "
        f"tension {relationship['tension']}"
    )
    print(
        "Memories: "
        f"{summary['conversation_memory_count']} conversation, "
        f"{summary['gift_memory_count']} gift, "
        f"{summary['away_memory_count']} away"
    )
    print(f"Away ticks: {summary['away_tick_count']}")
    print(f"Relationship edges: {summary['relationship_edge_count']}")
    print(f"Events: {summary['event_count']}")
    print(f"Notifications: {summary['notification_count']}")
    latest = summary.get("latest_notification")
    if latest:
        print(f"Latest notification: {latest['body']}")


def main() -> None:
    args = parse_args()
    summary = asyncio.run(
        seed_demo_state(
            db_path=args.db_path,
            player_id=args.player_id,
            villager_id=args.villager_id,
            away_ticks=args.away_ticks,
            force_fallback=not args.live_claude,
        )
    )
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print_summary(summary)


if __name__ == "__main__":
    main()
