"""North-star demo smoke test for the Heather's Hollow memory loop.

Run from the repo root with server dependencies installed:

    python -m server.tests.test_demo_storyline

Or without a persistent virtualenv:

    uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_demo_storyline

This uses a temporary SQLite database and fallback mode, then verifies the
same state surfaces that Godot, debug tools, and the future mobile companion
need for a morning demo.
"""

from __future__ import annotations

import asyncio
import importlib
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import ModuleType
from typing import Any


def import_server_with_temp_db(tmp_dir: str) -> ModuleType:
    os.environ["HH_MEMORY_DB"] = str(Path(tmp_dir) / "demo_storyline.sqlite3")
    os.environ.pop("ANTHROPIC_API_KEY", None)
    os.environ["HOLLOW_LLM_PROVIDER"] = "fallback"
    sys.modules.pop("server.api.server", None)
    return importlib.import_module("server.api.server")


async def run_demo_storyline(server_module: ModuleType) -> dict[str, Any]:
    fact_text = "Margot, please remember that Heather's lucky teacup is painted with bluebells."
    recall_text = "Do you remember what is painted on my lucky teacup?"

    first_reply = await send_player_message(server_module, fact_text)
    recall_reply = await send_player_message(server_module, recall_text)
    gift_reply = await send_gift(server_module)

    relationship = await server_module.relationship_detail("margot", "heather")
    conversation_memories = await server_module.recent_memories(
        villager_id="margot",
        subject_id="heather",
        kind="conversation",
        limit=10,
    )
    gift_memories = await server_module.recent_memories(
        villager_id="margot",
        subject_id="heather",
        kind="gift",
        limit=10,
    )
    events = await server_module.recent_events(limit=10)
    notifications = await server_module.recent_notifications(limit=10)

    return {
        "first_reply": first_reply,
        "recall_reply": recall_reply,
        "gift_reply": gift_reply,
        "relationship": relationship,
        "conversation_memories": conversation_memories["memories"],
        "gift_memories": gift_memories["memories"],
        "events": events["events"],
        "notifications": notifications["notifications"],
    }


async def send_player_message(server_module: ModuleType, text: str) -> str:
    response = await server_module.handle_ws_payload(
        {
            "type": "player_message",
            "player_id": "heather",
            "villager_id": "margot",
            "text": text,
            "context": {"location": "town_square", "test": "demo_storyline"},
        }
    )
    assert response["type"] == "villager_reply"
    return str(response["text"])


async def send_gift(server_module: ModuleType) -> str:
    response = await server_module.handle_ws_payload(
        {
            "type": "gift_item",
            "player_id": "heather",
            "villager_id": "margot",
            "item": {
                "item_id": "dusty_rose",
                "display_name": "Dusty Rose",
                "category": "flower",
                "tags": ["flower", "garden", "soft_color", "handmade"],
                "quantity": 1,
            },
            "context": {"location": "town_square", "test": "demo_storyline"},
        }
    )
    assert response["type"] == "villager_reply"
    return str(response["text"])


def assert_demo_storyline(result: dict[str, Any]) -> None:
    recall_reply = result["recall_reply"].lower()
    assert "bluebell" in recall_reply or "teacup" in recall_reply, result["recall_reply"]

    relationship = result["relationship"]
    assert relationship["persisted"] is True
    assert relationship["affection"] > 8
    assert relationship["trust"] > 12
    assert relationship["familiarity"] > 2
    assert relationship["metadata"]["last_gift"] == "Dusty Rose"
    assert relationship["metadata"]["last_gift_preference"] == "loved"

    conversation_memories = result["conversation_memories"]
    assert len(conversation_memories) >= 2
    assert any("bluebell" in memory["text"].lower() for memory in conversation_memories)
    assert all("player_text" not in memory["metadata"] for memory in conversation_memories)

    gift_memories = result["gift_memories"]
    assert len(gift_memories) == 1
    gift_memory = gift_memories[0]
    assert gift_memory["metadata"]["item_id"] == "dusty_rose"
    assert gift_memory["metadata"]["item_name"] == "Dusty Rose"
    assert gift_memory["metadata"]["preference"] == "loved"
    assert gift_memory["metadata"]["location"] == "town_square"

    events = result["events"]
    assert any(event["kind"] == "conversation" for event in events)
    assert any(event["kind"] == "gift" for event in events)

    notifications = result["notifications"]
    gift_notification = next(item for item in notifications if item["event_kind"] == "gift")
    assert gift_notification["villager_id"] == "margot"
    assert "Dusty Rose" in gift_notification["body"]
    assert gift_notification["metadata"]["preference"] == "loved"
    assert any(item["event_kind"] == "conversation" for item in notifications)


def main() -> None:
    previous_db = os.environ.get("HH_MEMORY_DB")
    previous_api_key = os.environ.get("ANTHROPIC_API_KEY")
    previous_provider = os.environ.get("HOLLOW_LLM_PROVIDER")

    with TemporaryDirectory() as tmp_dir:
        server_module = import_server_with_temp_db(tmp_dir)
        try:
            result = asyncio.run(run_demo_storyline(server_module))
            assert_demo_storyline(result)
        finally:
            server_module.memory_store.close()
            if previous_db is None:
                os.environ.pop("HH_MEMORY_DB", None)
            else:
                os.environ["HH_MEMORY_DB"] = previous_db
            if previous_api_key is None:
                os.environ.pop("ANTHROPIC_API_KEY", None)
            else:
                os.environ["ANTHROPIC_API_KEY"] = previous_api_key
            if previous_provider is None:
                os.environ.pop("HOLLOW_LLM_PROVIDER", None)
            else:
                os.environ["HOLLOW_LLM_PROVIDER"] = previous_provider

    print("First reply:", result["first_reply"])
    print("Recall reply:", result["recall_reply"])
    print("Gift reply:", result["gift_reply"])
    print("PASS: North-star demo storyline persisted memory, relationship, events, and notifications.")


if __name__ == "__main__":
    main()
