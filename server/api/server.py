"""FastAPI server for Godot and future companion clients."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from server.ai.conversation import ConversationEngine
from server.ai.memory import (
    ConversationTurnRecord,
    EventRecord,
    MemoryRecord,
    MemoryStore,
    NotificationCursorRecord,
)
from server.ai.personality import Personality, PersonalityStore
from server.mobile.notifications import compose_notifications
from server.world.away import AwayInteractionEngine
from server.world.events import EventLog
from server.world.inventory import starter_inventory_payload
from server.world.state import WorldState


memory_store = MemoryStore()
personality_store = PersonalityStore()
world_state = WorldState.create_default()
event_log = EventLog()
conversation_engine = ConversationEngine(
    memory_store=memory_store,
    personality_store=personality_store,
    world_state=world_state,
    event_log=event_log,
)
away_interaction_engine = AwayInteractionEngine(
    memory_store=memory_store,
    personality_store=personality_store,
    world_state=world_state,
    event_log=event_log,
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Heather's Hollow AI Server", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PUBLIC_HOME_LOCATIONS_BY_VILLAGER = {
    "margot": "town_square",
    "fern": "garden",
    "hugo": "shop",
}

PUBLIC_RELATIONSHIP_METADATA_KEYS = {
    "last_gift",
    "last_gift_preference",
    "last_interaction_memory_id",
    "last_interaction_topic",
    "last_memory_id",
    "last_mood",
}

PUBLIC_MEMORY_METADATA_KEYS = {
    "conversation_id",
    "location",
    "other_villager_id",
    "other_villager_name",
    "preference",
    "topic",
}

PUBLIC_EVENT_METADATA_KEYS = {
    "actor_memory_id",
    "item_id",
    "item_name",
    "memory_id",
    "mood",
    "preference",
    "relationship_delta",
    "target_memory_id",
    "topic",
}

PUBLIC_ID_LIST_METADATA_KEYS = {"memories_used", "social_memory_ids"}


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "ok": True,
        "world": world_state.snapshot(),
        "villagers": personality_store.list_ids(),
        "llm": conversation_engine.llm_provider_status(),
    }


@app.get("/world")
async def world() -> dict[str, Any]:
    return world_state.snapshot()


@app.get("/client/bootstrap")
async def client_bootstrap(
    client_id: str = "heather_mobile",
    notification_limit: int = 5,
    player_id: str = "heather",
) -> dict[str, Any]:
    clean_player_id = normalize_player_id(player_id)
    return {
        "world": world_state.snapshot(),
        "villagers": public_villagers_payload()["villagers"],
        "inventory": public_inventory_payload(clean_player_id),
        "notifications": await notification_inbox(client_id=client_id, limit=notification_limit),
    }


@app.get("/client/inventory")
async def client_inventory(player_id: str = "heather") -> dict[str, Any]:
    clean_player_id = normalize_player_id(player_id)
    return public_inventory_payload(clean_player_id)


def public_inventory_payload(player_id: str) -> dict[str, Any]:
    return {
        "player_id": player_id,
        "items": starter_inventory_payload(),
    }


@app.get("/client/villagers/{villager_id}/context")
async def client_villager_context(
    villager_id: str,
    subject_id: str = "heather",
    memory_limit: int = 5,
    event_limit: int = 5,
) -> dict[str, Any]:
    try:
        personality = personality_store.load(villager_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown villager: {villager_id}") from exc

    clamped_memory_limit = max(1, min(int(memory_limit), 20))
    clamped_event_limit = max(1, min(int(event_limit), 20))
    memories = memory_store.query_memories(
        villager_id=villager_id,
        subject_id=subject_id,
        limit=clamped_memory_limit,
    )
    events = memory_store.query_events(
        target_id=villager_id,
        limit=clamped_event_limit,
    )

    return {
        "world": world_state.snapshot(),
        "villager": public_villager_detail_payload(personality),
        "relationship": await relationship_detail(villager_id, subject_id),
        "memories": [public_memory_payload(memory) for memory in memories],
        "events": [public_event_payload(event) for event in events],
    }


@app.get("/client/villagers/{villager_id}/social-context")
async def client_villager_social_context(villager_id: str, limit: int = 10) -> dict[str, Any]:
    try:
        personality = personality_store.load(villager_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown villager: {villager_id}") from exc

    clamped_limit = max(1, min(int(limit), 50))
    relationships_payload = [
        public_relationship_snapshot(relationship, persisted=True)
        for relationship in social_relationships_for_villager(villager_id, clamped_limit)
    ]
    memories = memory_store.query_memories(
        villager_id=villager_id,
        kind="villager_interaction",
        limit=clamped_limit,
    )
    events = social_events_for_villager(villager_id, clamped_limit)

    return {
        "villager": public_villager_summary(personality),
        "relationships": relationships_payload,
        "memories": [public_memory_payload(memory) for memory in memories],
        "events": [public_event_payload(event) for event in events],
    }


@app.get("/villagers")
async def villagers() -> dict[str, Any]:
    return public_villagers_payload()


@app.get("/villagers/{villager_id}")
async def villager_detail(villager_id: str) -> dict[str, Any]:
    try:
        personality = personality_store.load(villager_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown villager: {villager_id}") from exc

    return public_villager_detail_payload(personality)


def public_villager_detail_payload(personality: Personality) -> dict[str, Any]:
    return public_villager_summary(personality) | {
        "relationships": {
            subject_id: {
                key: value
                for key, value in relationship.items()
                if key.startswith("starting_")
            }
            for subject_id, relationship in personality.relationships.items()
            if isinstance(relationship, dict)
        },
        "mood_baseline_by_time": personality.mood_baseline_by_time,
    }


@app.get("/events/recent")
async def recent_events(
    kind: str | None = None,
    actor_id: str | None = None,
    target_id: str | None = None,
    after_id: int | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    clamped_limit = max(1, min(int(limit), 50))
    return {
        "events": [
            public_event_payload(event)
            for event in memory_store.query_events(
                kind=kind,
                actor_id=actor_id,
                target_id=target_id,
                after_id=after_id,
                limit=clamped_limit,
            )
        ]
    }


@app.get("/events/{event_id}")
async def event_detail(event_id: int) -> dict[str, Any]:
    event = memory_store.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"Unknown event: {event_id}")
    return public_event_payload(event)


@app.get("/notifications/summary")
async def notification_summary(
    kind: str | None = None,
    actor_id: str | None = None,
    target_id: str | None = None,
    after_id: int | None = None,
) -> dict[str, Any]:
    return notification_summary_payload(
        kind=kind,
        actor_id=actor_id,
        target_id=target_id,
        after_id=after_id,
    )


@app.get("/notifications/recent")
async def recent_notifications(
    kind: str | None = None,
    actor_id: str | None = None,
    target_id: str | None = None,
    after_id: int | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    clamped_limit = max(1, min(int(limit), 50))
    events = memory_store.query_events(
        kind=kind,
        actor_id=actor_id,
        target_id=target_id,
        after_id=after_id,
        limit=clamped_limit,
    )
    return {"notifications": compose_notifications(events, personality_store)}


@app.get("/notifications/inbox")
async def notification_inbox(client_id: str = "heather_mobile", limit: int = 10) -> dict[str, Any]:
    clean_client_id = normalize_client_id(client_id)
    cursor = memory_store.get_notification_cursor(clean_client_id)
    cursor_payload = public_notification_cursor_payload(clean_client_id, cursor)
    last_event_id = int(cursor_payload["last_event_id"])
    clamped_limit = max(1, min(int(limit), 50))
    events = memory_store.query_events(
        after_id=last_event_id,
        limit=clamped_limit,
        ascending=True,
    )
    notifications = compose_notifications(events, personality_store)
    next_cursor_event_id = max([last_event_id, *[event.id for event in events]])
    unseen_count = int(cursor_payload["summary"]["unseen_count"])

    return {
        "client_id": clean_client_id,
        "cursor": cursor_payload,
        "notifications": notifications,
        "count": len(notifications),
        "next_cursor_event_id": next_cursor_event_id,
        "has_more": unseen_count > len(notifications),
    }


@app.get("/notifications/cursor")
async def notification_cursor(client_id: str = "heather_mobile") -> dict[str, Any]:
    clean_client_id = normalize_client_id(client_id)
    cursor = memory_store.get_notification_cursor(clean_client_id)
    return public_notification_cursor_payload(clean_client_id, cursor)


@app.post("/notifications/cursor")
async def update_notification_cursor(
    client_id: str = "heather_mobile",
    last_event_id: int = 0,
) -> dict[str, Any]:
    clean_client_id = normalize_client_id(client_id)
    cursor = memory_store.set_notification_cursor(clean_client_id, last_event_id)
    return public_notification_cursor_payload(clean_client_id, cursor)


@app.get("/notifications/{event_id}")
async def notification_detail(event_id: int) -> dict[str, Any]:
    event = memory_store.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"Unknown notification event: {event_id}")

    return compose_notifications([event], personality_store)[0]


@app.get("/memories/recent")
async def recent_memories(
    villager_id: str | None = None,
    subject_id: str | None = None,
    kind: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    if villager_id:
        try:
            personality_store.load(villager_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"Unknown villager: {villager_id}") from exc

    clamped_limit = max(1, min(int(limit), 50))
    memories = memory_store.query_memories(
        villager_id=villager_id,
        subject_id=subject_id,
        kind=kind,
        limit=clamped_limit,
    )
    return {"memories": [public_memory_payload(memory) for memory in memories]}


@app.get("/memories/{memory_id}")
async def memory_detail(memory_id: int) -> dict[str, Any]:
    memory = memory_store.get_memory(memory_id)
    if memory is None:
        raise HTTPException(status_code=404, detail=f"Unknown memory: {memory_id}")
    return public_memory_payload(memory)


@app.get("/relationships")
async def relationships(
    villager_id: str | None = None,
    subject_id: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    clamped_limit = max(1, min(int(limit), 100))
    relationship_rows = memory_store.query_relationships(
        villager_id=villager_id,
        subject_id=subject_id,
        limit=clamped_limit,
    )
    return {
        "relationships": [
            public_relationship_snapshot(relationship, persisted=True)
            for relationship in relationship_rows
        ]
    }


@app.get("/relationships/{villager_id}/{subject_id}")
async def relationship_detail(villager_id: str, subject_id: str) -> dict[str, Any]:
    try:
        personality = personality_store.load(villager_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown villager: {villager_id}") from exc

    relationship = memory_store.peek_relationship(villager_id, subject_id)
    if relationship is None:
        starting_values = personality.starting_relationship(subject_id)
        relationship = {
            "villager_id": villager_id,
            "subject_id": subject_id,
            "affection": starting_values["affection"],
            "trust": starting_values["trust"],
            "familiarity": starting_values["familiarity"],
            "tension": starting_values["tension"],
            "updated_at": None,
            "metadata": {},
        }
        return public_relationship_snapshot(relationship, persisted=False)

    return public_relationship_snapshot(relationship, persisted=True)


@app.get("/conversations/{conversation_id}/turns")
async def conversation_turns(conversation_id: str) -> dict[str, Any]:
    turns = memory_store.get_conversation_turns(conversation_id)
    if not turns:
        raise HTTPException(status_code=404, detail=f"Unknown conversation: {conversation_id}")

    return {
        "conversation_id": conversation_id,
        "turns": [public_conversation_turn_payload(turn) for turn in turns],
    }


@app.post("/world/away-tick")
async def away_tick(
    actor_id: str | None = None,
    target_id: str | None = None,
    location: str | None = None,
) -> dict[str, Any]:
    try:
        return away_interaction_engine.run_tick(actor_id=actor_id, target_id=target_id, location=location)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/world/away-ticks")
async def away_ticks(
    count: int = 1,
    actor_id: str | None = None,
    target_id: str | None = None,
    location: str | None = None,
) -> dict[str, Any]:
    try:
        return away_interaction_engine.run_ticks(
            count=count,
            actor_id=actor_id,
            target_id=target_id,
            location=location,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.websocket("/ws")
@app.websocket("/ws/conversation")
async def conversation_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_json(
        {
            "type": "server_status",
            "message": "Heather's Hollow AI server connected.",
            "world": world_state.snapshot(),
        }
    )

    try:
        while True:
            try:
                payload = await websocket.receive_json()
                response = await handle_ws_payload(payload)
            except Exception:
                logger.exception("Failed to handle websocket payload")
                response = {
                    "type": "error",
                    "message": "The AI server had trouble answering that.",
                }
            await websocket.send_json(response)
    except WebSocketDisconnect:
        return


async def handle_ws_payload(payload: dict[str, Any]) -> dict[str, Any]:
    message_type = payload.get("type")

    if message_type == "player_message":
        return await conversation_engine.handle_player_message(
            player_id=str(payload.get("player_id") or "heather"),
            villager_id=str(payload.get("villager_id") or "margot"),
            text=str(payload.get("text") or ""),
            context=dict(payload.get("context") or {}),
        )

    if message_type == "gift_item":
        return await conversation_engine.handle_gift(
            player_id=str(payload.get("player_id") or "heather"),
            villager_id=str(payload.get("villager_id") or "margot"),
            item=dict(payload.get("item") or {}),
            context=dict(payload.get("context") or {}),
        )

    return {
        "type": "error",
        "message": f"Unknown message type: {message_type}",
    }


def public_villager_summary(personality: Personality) -> dict[str, Any]:
    return {
        "id": personality.id,
        "display_name": personality.display_name,
        "home_location": PUBLIC_HOME_LOCATIONS_BY_VILLAGER.get(personality.id, "town_square"),
        "species": personality.species,
        "archetype": personality.archetype,
        "core_traits": personality.core_traits,
        "values": personality.values,
        "speaking_style": {
            "sentence_length": personality.speaking_style.sentence_length,
            "tone": personality.speaking_style.tone,
            "quirks": personality.speaking_style.quirks,
        },
        "likes": personality.likes,
        "dislikes": personality.dislikes,
    }


def public_villagers_payload() -> dict[str, Any]:
    return {
        "villagers": [
            public_villager_summary(personality_store.load(villager_id))
            for villager_id in personality_store.list_ids()
        ]
    }


def social_relationships_for_villager(villager_id: str, limit: int) -> list[dict[str, Any]]:
    relationships_by_pair: dict[tuple[str, str], dict[str, Any]] = {}
    for relationship in [
        *memory_store.query_relationships(villager_id=villager_id, limit=limit),
        *memory_store.query_relationships(subject_id=villager_id, limit=limit),
    ]:
        relationships_by_pair[(relationship["villager_id"], relationship["subject_id"])] = relationship

    return sorted(
        relationships_by_pair.values(),
        key=lambda relationship: (
            str(relationship.get("updated_at") or ""),
            str(relationship.get("villager_id") or ""),
            str(relationship.get("subject_id") or ""),
        ),
        reverse=True,
    )[:limit]


def social_events_for_villager(villager_id: str, limit: int) -> list[EventRecord]:
    events_by_id: dict[int, EventRecord] = {}
    for event in [
        *memory_store.query_events(kind="villager_interaction", actor_id=villager_id, limit=limit),
        *memory_store.query_events(kind="villager_interaction", target_id=villager_id, limit=limit),
    ]:
        events_by_id[event.id] = event

    return sorted(events_by_id.values(), key=lambda event: event.id, reverse=True)[:limit]


def public_relationship_snapshot(relationship: dict[str, Any], *, persisted: bool) -> dict[str, Any]:
    return {
        "villager_id": relationship["villager_id"],
        "subject_id": relationship["subject_id"],
        "persisted": persisted,
        "affection": int(relationship.get("affection", 0)),
        "trust": int(relationship.get("trust", 0)),
        "familiarity": int(relationship.get("familiarity", 0)),
        "tension": int(relationship.get("tension", 0)),
        "updated_at": relationship.get("updated_at"),
        "metadata": public_relationship_metadata(dict(relationship.get("metadata") or {})),
    }


def public_relationship_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    public_metadata = {
        key: metadata[key]
        for key in PUBLIC_RELATIONSHIP_METADATA_KEYS
        if key in metadata
    }

    mood_state = metadata.get("mood_state")
    if isinstance(mood_state, dict) and mood_state.get("current"):
        public_metadata["current_mood"] = str(mood_state["current"])

    return public_metadata


def public_memory_payload(memory: MemoryRecord) -> dict[str, Any]:
    return {
        "id": memory.id,
        "villager_id": memory.villager_id,
        "kind": memory.kind,
        "subject_id": memory.subject_id,
        "text": memory.text,
        "salience": memory.salience,
        "emotion": memory.emotion,
        "created_at": memory.created_at,
        "metadata": public_memory_metadata(memory.metadata),
    }


def public_event_payload(event: EventRecord) -> dict[str, Any]:
    return {
        "id": event.id,
        "kind": event.kind,
        "actor_id": event.actor_id,
        "target_id": event.target_id,
        "location": event.location,
        "summary": event.summary,
        "created_at": event.created_at,
        "metadata": public_event_metadata(event.metadata),
    }


def public_event_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    public_metadata = {
        key: metadata[key]
        for key in PUBLIC_EVENT_METADATA_KEYS
        if key in metadata
    }
    public_metadata.update(public_id_list_metadata(metadata))
    return public_metadata


def notification_summary_payload(
    *,
    kind: str | None = None,
    actor_id: str | None = None,
    target_id: str | None = None,
    after_id: int | None = None,
) -> dict[str, Any]:
    unseen_count = memory_store.count_events(
        kind=kind,
        actor_id=actor_id,
        target_id=target_id,
        after_id=after_id,
    )
    latest_events = memory_store.query_events(
        kind=kind,
        actor_id=actor_id,
        target_id=target_id,
        limit=1,
    )
    return {
        "latest_event_id": latest_events[0].id if latest_events else None,
        "after_id": after_id,
        "unseen_count": unseen_count,
        "has_unseen": unseen_count > 0,
        "filters": {
            "kind": kind,
            "actor_id": actor_id,
            "target_id": target_id,
        },
    }


def public_notification_cursor_payload(
    client_id: str,
    cursor: NotificationCursorRecord | None,
) -> dict[str, Any]:
    last_event_id = cursor.last_event_id if cursor else 0
    return {
        "client_id": client_id,
        "last_event_id": last_event_id,
        "updated_at": cursor.updated_at if cursor else None,
        "summary": notification_summary_payload(after_id=last_event_id),
    }


def normalize_client_id(client_id: str) -> str:
    clean_client_id = str(client_id or "").strip()
    if not clean_client_id:
        raise HTTPException(status_code=400, detail="client_id is required")
    return clean_client_id


def normalize_player_id(player_id: str) -> str:
    clean_player_id = str(player_id or "").strip()
    if not clean_player_id:
        raise HTTPException(status_code=400, detail="player_id is required")
    return clean_player_id


def public_memory_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    public_metadata = {
        key: metadata[key]
        for key in PUBLIC_MEMORY_METADATA_KEYS
        if key in metadata
    }
    public_metadata.update(public_id_list_metadata(metadata))

    item = metadata.get("item")
    if isinstance(item, dict):
        if item.get("item_id"):
            public_metadata["item_id"] = str(item["item_id"])
        if item.get("display_name"):
            public_metadata["item_name"] = str(item["display_name"])
        elif item.get("item_id"):
            public_metadata["item_name"] = str(item["item_id"])

    context = metadata.get("context")
    if isinstance(context, dict) and context.get("location"):
        public_metadata["location"] = str(context["location"])

    world = metadata.get("world")
    if isinstance(world, dict):
        for key in ("time_label", "season", "weather"):
            if world.get(key):
                public_metadata[f"world_{key}"] = str(world[key])

    return public_metadata


def public_id_list_metadata(metadata: dict[str, Any]) -> dict[str, list[int]]:
    public_metadata: dict[str, list[int]] = {}
    for key in PUBLIC_ID_LIST_METADATA_KEYS:
        values = metadata.get(key)
        if not isinstance(values, list):
            continue
        public_metadata[key] = [
            int(value)
            for value in values
            if isinstance(value, int) or str(value).isdigit()
        ]
    return public_metadata


def public_conversation_turn_payload(turn: ConversationTurnRecord) -> dict[str, Any]:
    return {
        "id": turn.id,
        "conversation_id": turn.conversation_id,
        "villager_id": turn.villager_id,
        "player_id": turn.player_id,
        "speaker": turn.speaker,
        "text": turn.text,
        "created_at": turn.created_at,
        "metadata": public_conversation_turn_metadata(turn.metadata),
    }


def public_conversation_turn_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    public_metadata: dict[str, Any] = {}

    context = metadata.get("context")
    if isinstance(context, dict) and context.get("location"):
        public_metadata["location"] = str(context["location"])

    if metadata.get("mood"):
        public_metadata["mood"] = str(metadata["mood"])

    memories_used = metadata.get("memories_used")
    if isinstance(memories_used, list):
        public_metadata["memories_used"] = [
            int(memory_id)
            for memory_id in memories_used
            if isinstance(memory_id, int) or str(memory_id).isdigit()
        ]

    return public_metadata


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server.api.server:app", host="127.0.0.1", port=8765, reload=True)
