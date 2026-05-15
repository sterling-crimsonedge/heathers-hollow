"""Deterministic mobile companion notification composition."""

from __future__ import annotations

from typing import Any

from server.ai.memory import EventRecord
from server.ai.personality import PersonalityStore


def compose_notifications(
    events: list[EventRecord],
    personality_store: PersonalityStore,
) -> list[dict[str, Any]]:
    return [_compose_notification(event, personality_store) for event in events]


def _compose_notification(event: EventRecord, personality_store: PersonalityStore) -> dict[str, Any]:
    villager_name = _villager_name(event.target_id, personality_store)
    body = _body_for_event(event, villager_name, personality_store)

    return {
        "id": f"event-{event.id}",
        "villager_id": event.target_id,
        "villager_name": villager_name,
        "title": villager_name,
        "body": body,
        "event_kind": event.kind,
        "created_at": event.created_at,
        "metadata": {
            key: value
            for key, value in event.metadata.items()
            if key
            in {
                "memory_id",
                "actor_memory_id",
                "target_memory_id",
                "mood",
                "preference",
                "item_id",
                "item_name",
                "topic",
            }
        },
    }


def _villager_name(villager_id: str | None, personality_store: PersonalityStore) -> str:
    if not villager_id:
        return "Heather's Hollow"
    try:
        return personality_store.load(villager_id).display_name
    except FileNotFoundError:
        return villager_id.replace("_", " ").title()


def _body_for_event(event: EventRecord, villager_name: str, personality_store: PersonalityStore) -> str:
    if event.kind == "gift":
        item_name = str(event.metadata.get("item_name") or "your gift")
        preference = str(event.metadata.get("preference") or "remembered")
        if preference == "loved":
            return f"I found the perfect little place for {item_name}. Thank you again."
        if preference == "liked":
            return f"{item_name} made the hollow feel softer today."
        if preference == "disliked":
            return f"I'm still thinking about {item_name}. It was kind of you to bring it."
        return f"I tucked away the memory of {item_name}."

    if event.kind == "conversation":
        mood = str(event.metadata.get("mood") or "content")
        if mood in {"warm", "delighted", "happy"}:
            return "I was just thinking about what you said. It stayed with me."
        if mood in {"worried", "anxious"}:
            return "I hope you're doing all right. I kept our talk close."
        return "Our little conversation is still on my mind."

    if event.kind == "villager_interaction":
        topic = str(event.metadata.get("topic") or "something small")
        actor_name = _villager_name(event.actor_id, personality_store)
        return f"{actor_name} and {villager_name} spent a quiet moment talking about {topic}."

    if event.summary:
        return event.summary
    return f"{villager_name} has a small update from the hollow."
