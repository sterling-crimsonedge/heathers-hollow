"""Smoke test for mobile companion notification composition.

Run from the repo root:

    python -m server.tests.test_mobile_notifications
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from server.ai.memory import MemoryStore
from server.ai.personality import PersonalityStore
from server.mobile.notifications import compose_notifications


def run_mobile_notification_check() -> None:
    with TemporaryDirectory() as tmp_dir:
        memory_store = MemoryStore(Path(tmp_dir) / "mobile_notifications.sqlite3")
        try:
            conversation_id = memory_store.add_event(
                kind="conversation",
                actor_id="heather",
                target_id="margot",
                location="town_square",
                summary="heather talked with Margot.",
                metadata={"memory_id": 101, "mood": "warm", "internal_note": "do not expose"},
            )
            gift_id = memory_store.add_event(
                kind="gift",
                actor_id="heather",
                target_id="margot",
                location="town_square",
                summary="heather gave Margot a Dusty Rose.",
                metadata={
                    "memory_id": 102,
                    "mood": "delighted",
                    "preference": "loved",
                    "item_id": "dusty_rose",
                    "item_name": "Dusty Rose",
                },
            )

            notifications = compose_notifications(
                memory_store.get_recent_events(limit=5),
                PersonalityStore(),
            )

            assert len(notifications) == 2
            gift = next(item for item in notifications if item["id"] == f"event-{gift_id}")
            conversation = next(item for item in notifications if item["id"] == f"event-{conversation_id}")

            assert gift["villager_id"] == "margot"
            assert gift["villager_name"] == "Margot"
            assert gift["title"] == "Margot"
            assert "Dusty Rose" in gift["body"]
            assert gift["event_kind"] == "gift"
            assert gift["metadata"]["preference"] == "loved"
            assert gift["metadata"]["item_id"] == "dusty_rose"

            assert conversation["villager_name"] == "Margot"
            assert conversation["event_kind"] == "conversation"
            assert "stayed with me" in conversation["body"]
            assert conversation["metadata"]["memory_id"] == 101
            assert "internal_note" not in conversation["metadata"]
        finally:
            memory_store.close()


def main() -> None:
    run_mobile_notification_check()
    print("PASS: Mobile notification payloads compose from persisted events.")


if __name__ == "__main__":
    main()
