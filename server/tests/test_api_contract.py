"""FastAPI contract smoke test for Heather's Hollow clients.

Run from the repo root with server dependencies installed:

    python -m server.tests.test_api_contract

Or without a persistent virtualenv:

    uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract
"""

from __future__ import annotations

import asyncio
import importlib
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import ModuleType

from fastapi import HTTPException


def import_server_with_temp_db(tmp_dir: str) -> ModuleType:
    os.environ["HH_MEMORY_DB"] = str(Path(tmp_dir) / "api_contract.sqlite3")
    os.environ["HOLLOW_LLM_PROVIDER"] = "fallback"
    sys.modules.pop("server.api.server", None)
    return importlib.import_module("server.api.server")


def test_route_contract(server_module: ModuleType) -> None:
    http_paths: set[str] = set()
    websocket_paths: set[str] = set()

    for route in server_module.app.routes:
        route_path = getattr(route, "path", "")
        route_type = route.__class__.__name__.lower()
        if "websocket" in route_type:
            websocket_paths.add(route_path)
        else:
            http_paths.add(route_path)

    assert "/health" in http_paths, "Expected /health HTTP route to be registered."
    assert "/world" in http_paths, "Expected /world HTTP route to be registered."
    assert "/client/bootstrap" in http_paths, "Expected client bootstrap route."
    assert "/client/inventory" in http_paths, "Expected client inventory route."
    assert "/client/villagers/{villager_id}/context" in http_paths, "Expected villager context route."
    assert "/client/villagers/{villager_id}/social-context" in http_paths, "Expected villager social context route."
    assert "/world/away-tick" in http_paths, "Expected /world/away-tick HTTP route."
    assert "/world/away-ticks" in http_paths, "Expected /world/away-ticks HTTP route."
    assert "/villagers" in http_paths, "Expected /villagers HTTP route to be registered."
    assert "/villagers/{villager_id}" in http_paths, "Expected /villagers/{villager_id} HTTP route."
    assert "/events/recent" in http_paths, "Expected /events/recent HTTP route to be registered."
    assert "/events/{event_id}" in http_paths, "Expected event detail route."
    assert "/notifications/summary" in http_paths, "Expected notification summary route."
    assert "/notifications/recent" in http_paths, "Expected /notifications/recent HTTP route."
    assert "/notifications/inbox" in http_paths, "Expected notification inbox route."
    assert "/notifications/cursor" in http_paths, "Expected notification cursor route."
    assert "/notifications/{event_id}" in http_paths, "Expected notification detail route."
    assert "/memories/recent" in http_paths, "Expected /memories/recent HTTP route."
    assert "/memories/{memory_id}" in http_paths, "Expected memory detail route."
    assert "/relationships" in http_paths, "Expected relationship graph route."
    assert "/relationships/{villager_id}/{subject_id}" in http_paths, "Expected relationship detail route."
    assert "/conversations/{conversation_id}/turns" in http_paths, "Expected conversation turns route."
    assert "/ws" in websocket_paths, "Expected /ws WebSocket alias to be registered."
    assert "/ws/conversation" in websocket_paths, "Expected /ws/conversation WebSocket route."


async def test_health_payload(server_module: ModuleType) -> None:
    payload = await server_module.health()

    assert payload["ok"] is True
    assert "world" in payload and isinstance(payload["world"], dict)
    assert "villagers" in payload and isinstance(payload["villagers"], list)
    assert "llm" in payload and isinstance(payload["llm"], dict)
    assert "margot" in payload["villagers"]
    assert "time_label" in payload["world"]
    assert "day_length_seconds" in payload["world"]
    assert payload["llm"]["configured"] in {"auto", "fallback", "ollama", "anthropic"}
    assert "active_order" in payload["llm"]


async def test_read_only_payloads(server_module: ModuleType) -> None:
    world = await server_module.world()
    assert "clock" in world
    assert "time_label" in world
    assert "season" in world

    villagers = await server_module.villagers()
    summaries = villagers["villagers"]
    assert isinstance(summaries, list)
    margot_summary = next(summary for summary in summaries if summary["id"] == "margot")
    assert margot_summary["display_name"] == "Margot"
    assert "system_prompt" not in margot_summary
    assert "private_goals" not in margot_summary
    assert "likes" in margot_summary

    margot_detail = await server_module.villager_detail("margot")
    assert margot_detail["display_name"] == "Margot"
    assert "relationships" in margot_detail
    assert "mood_baseline_by_time" in margot_detail
    assert "system_prompt" not in margot_detail
    assert "private_goals" not in margot_detail

    try:
        await server_module.villager_detail("missing_villager")
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Unknown villager detail request should raise HTTP 404.")


async def test_client_bootstrap_payload(server_module: ModuleType) -> None:
    baseline_events = server_module.memory_store.query_events(limit=1)
    baseline_event_id = baseline_events[0].id if baseline_events else 0
    client_id = "bootstrap_contract_mobile"
    await server_module.update_notification_cursor(client_id, baseline_event_id)

    event_id = server_module.memory_store.add_event(
        kind="gift",
        actor_id="bootstrap_test",
        target_id="margot",
        location="town_square",
        summary="bootstrap_test gave Margot a startup ribbon.",
        metadata={
            "memory_id": 111,
            "preference": "liked",
            "item_name": "Startup Ribbon",
        },
    )

    payload = await server_module.client_bootstrap(
        client_id=client_id,
        notification_limit=3,
        player_id="bootstrap_player",
    )
    assert payload["world"]["time_label"]
    assert "day_length_seconds" in payload["world"]
    assert any(villager["id"] == "margot" for villager in payload["villagers"])
    margot = next(villager for villager in payload["villagers"] if villager["id"] == "margot")
    assert margot["display_name"] == "Margot"
    assert margot["home_location"] == "town_square"
    assert "system_prompt" not in margot
    assert "private_goals" not in margot
    # HH-006/HH-062: the per-villager loved-gift rubric and the per-villager
    # tuning knobs are server-side only. Clients reading `/client/bootstrap`
    # or `/villagers/{id}` must not be able to mine them.
    for villager in payload["villagers"]:
        assert "loved_tags" not in villager, (
            f"villager {villager.get('id')} bootstrap payload must not "
            f"expose loved_tags."
        )
        assert "tuning" not in villager, (
            f"villager {villager.get('id')} bootstrap payload must not "
            f"expose tuning."
        )

    # The canonical MVP cast must each carry a non-empty, JSON-driven
    # home_location so clients can place all four villagers spatially. Clover
    # specifically lives at "brook"; the other three keep their legacy spots.
    villagers_by_id = {villager["id"]: villager for villager in payload["villagers"]}
    expected_home_locations = {
        "margot": "town_square",
        "fern": "garden",
        "hugo": "shop",
        "clover": "brook",
    }
    for villager_id, expected in expected_home_locations.items():
        if villager_id not in villagers_by_id:
            continue
        assert villagers_by_id[villager_id]["home_location"] == expected, (
            f"{villager_id} bootstrap home_location should be {expected!r}; "
            f"got {villagers_by_id[villager_id]['home_location']!r}."
        )

    inventory = payload["inventory"]
    assert inventory["player_id"] == "bootstrap_player"
    assert inventory == await server_module.client_inventory(player_id="bootstrap_player")
    assert inventory["items"][0]["item_id"] == "dusty_rose"
    assert inventory["items"][0]["display_name"] == "Dusty Rose"
    assert "sort_order" not in inventory["items"][0]
    assert "preference" not in inventory["items"][0]

    notifications = payload["notifications"]
    assert notifications["client_id"] == client_id
    assert notifications["cursor"]["last_event_id"] == baseline_event_id
    assert notifications["count"] == 1
    assert notifications["notifications"][0]["id"] == f"event-{event_id}"
    assert notifications["notifications"][0]["villager_name"] == "Margot"
    assert "Startup Ribbon" in notifications["notifications"][0]["body"]
    assert notifications["next_cursor_event_id"] == event_id
    assert notifications["has_more"] is False

    await server_module.update_notification_cursor(client_id, event_id)
    empty_payload = await server_module.client_bootstrap(client_id=client_id, notification_limit=3)
    assert empty_payload["notifications"]["cursor"]["last_event_id"] == event_id
    assert empty_payload["notifications"]["notifications"] == []
    assert empty_payload["notifications"]["count"] == 0

    try:
        await server_module.client_bootstrap(client_id="   ")
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("Blank bootstrap client id should raise HTTP 400.")

    try:
        await server_module.client_bootstrap(client_id="bootstrap_contract_mobile", player_id="   ")
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("Blank bootstrap player id should raise HTTP 400.")


async def test_client_inventory_payload(server_module: ModuleType) -> None:
    payload = await server_module.client_inventory(player_id="heather")

    assert payload["player_id"] == "heather"
    items = payload["items"]
    assert len(items) >= 4
    assert [item["item_id"] for item in items[:4]] == [
        "dusty_rose",
        "chamomile_bundle",
        "porcelain_button",
        "smooth_pebble",
    ]

    dusty_rose = items[0]
    assert set(dusty_rose) == {
        "item_id",
        "display_name",
        "category",
        "tags",
        "quantity",
        "gift_prompt",
    }
    assert dusty_rose["display_name"] == "Dusty Rose"
    assert dusty_rose["category"] == "flower"
    assert dusty_rose["quantity"] == 1
    assert "flower" in dusty_rose["tags"]
    assert "garden" in dusty_rose["tags"]
    assert dusty_rose["gift_prompt"].startswith("A soft dusty rose")

    for item in items:
        assert item["item_id"]
        assert item["display_name"]
        assert item["category"]
        assert isinstance(item["tags"], list)
        assert all(isinstance(tag, str) and tag for tag in item["tags"])
        assert isinstance(item["quantity"], int)
        assert item["quantity"] > 0
        assert item["gift_prompt"]
        assert "secret" not in item
        assert "preference" not in item
        assert "sort_order" not in item

    try:
        await server_module.client_inventory(player_id="   ")
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("Blank inventory player id should raise HTTP 400.")


async def test_catalog_gift_payload(server_module: ModuleType) -> None:
    catalog_response = await server_module.handle_ws_payload(
        {
            "type": "gift_item",
            "player_id": "catalog_gift_contract",
            "villager_id": "margot",
            "item": {
                "item_id": "dusty_rose",
                "display_name": "Wrong Rose Name",
                "category": "waste",
                "tags": ["waste"],
                "quantity": 42,
                "secret": "not public",
            },
            "context": {
                "location": "town_square",
                "secret": "not public",
            },
        }
    )
    assert catalog_response["type"] == "villager_reply"
    assert catalog_response["mood"] == "delighted"
    assert "Dusty Rose" in catalog_response["text"]

    raw_memory = server_module.memory_store.get_memory(catalog_response["memory_id"])
    assert raw_memory is not None
    raw_item = raw_memory.metadata["item"]
    assert raw_item == {
        "item_id": "dusty_rose",
        "display_name": "Dusty Rose",
        "category": "flower",
        "tags": ["flower", "garden", "soft_color", "handmade"],
        "quantity": 1,
        "gift_prompt": "A soft dusty rose picked from Heather's garden.",
    }
    assert "secret" not in raw_item

    public_memory = await server_module.memory_detail(catalog_response["memory_id"])
    assert public_memory["metadata"]["item_id"] == "dusty_rose"
    assert public_memory["metadata"]["item_name"] == "Dusty Rose"
    assert public_memory["metadata"]["preference"] == "loved"
    assert public_memory["metadata"]["location"] == "town_square"
    assert "secret" not in public_memory["metadata"]

    events = await server_module.recent_events(
        kind="gift",
        actor_id="catalog_gift_contract",
        target_id="margot",
        limit=5,
    )
    matching_event = next(
        event for event in events["events"]
        if event["metadata"]["memory_id"] == catalog_response["memory_id"]
    )
    assert matching_event["metadata"]["item_id"] == "dusty_rose"
    assert matching_event["metadata"]["item_name"] == "Dusty Rose"
    assert matching_event["metadata"]["preference"] == "loved"
    assert "secret" not in matching_event["metadata"]

    unknown_response = await server_module.handle_ws_payload(
        {
            "type": "gift_item",
            "player_id": "unknown_gift_contract",
            "villager_id": "margot",
            "item": {
                "item_id": "blue_thread",
                "display_name": "Blue Thread",
                "category": "keepsake",
                "tags": "handmade",
                "quantity": "2",
                "secret": "not public",
            },
            "context": {"location": "town_square"},
        }
    )
    unknown_memory = server_module.memory_store.get_memory(unknown_response["memory_id"])
    assert unknown_memory is not None
    unknown_item = unknown_memory.metadata["item"]
    assert unknown_item["item_id"] == "blue_thread"
    assert unknown_item["display_name"] == "Blue Thread"
    assert unknown_item["category"] == "keepsake"
    assert unknown_item["tags"] == ["handmade"]
    assert unknown_item["quantity"] == 2
    assert "secret" not in unknown_item


async def test_client_villager_context_payload(server_module: ModuleType) -> None:
    subject_id = "context_player"
    server_module.memory_store.get_relationship(
        "margot",
        subject_id,
        {"affection": 8, "trust": 12, "familiarity": 2, "tension": 0},
    )
    server_module.memory_store.update_relationship(
        "margot",
        subject_id,
        affection_delta=3,
        trust_delta=2,
        familiarity_delta=1,
        metadata={
            "last_mood": "warm",
            "last_memory_id": 120,
            "secret": "not public",
        },
    )
    memory_id = server_module.memory_store.add_memory(
        "margot",
        kind="conversation",
        subject_id=subject_id,
        text="context_player told Margot about a pocket-sized tea journal.",
        salience=72,
        emotion="warm",
        metadata={
            "conversation_id": "context-conversation",
            "world": {"time_label": "morning", "season": "spring", "weather": "clear"},
            "secret": "not public",
        },
    )
    event_id = server_module.memory_store.add_event(
        kind="conversation",
        actor_id=subject_id,
        target_id="margot",
        location="tea_garden",
        summary="context_player told Margot about a pocket-sized tea journal.",
        metadata={
            "memory_id": memory_id,
            "mood": "warm",
            "secret": "not public",
        },
    )

    payload = await server_module.client_villager_context(
        "margot",
        subject_id=subject_id,
        memory_limit=3,
        event_limit=3,
    )
    assert payload["world"]["time_label"]
    assert payload["villager"]["id"] == "margot"
    assert payload["villager"]["display_name"] == "Margot"
    assert "system_prompt" not in payload["villager"]
    assert "private_goals" not in payload["villager"]

    relationship = payload["relationship"]
    assert relationship["villager_id"] == "margot"
    assert relationship["subject_id"] == subject_id
    assert relationship["persisted"] is True
    assert relationship["affection"] == 11
    assert relationship["trust"] == 14
    assert relationship["metadata"]["last_mood"] == "warm"
    assert relationship["metadata"]["last_memory_id"] == 120
    assert "secret" not in relationship["metadata"]

    matching_memory = next(memory for memory in payload["memories"] if memory["id"] == memory_id)
    assert matching_memory["villager_id"] == "margot"
    assert matching_memory["subject_id"] == subject_id
    assert matching_memory["metadata"]["conversation_id"] == "context-conversation"
    assert matching_memory["metadata"]["world_time_label"] == "morning"
    assert "secret" not in matching_memory["metadata"]

    matching_event = next(event for event in payload["events"] if event["id"] == event_id)
    assert matching_event["kind"] == "conversation"
    assert matching_event["target_id"] == "margot"
    assert matching_event["metadata"]["memory_id"] == memory_id
    assert matching_event["metadata"]["mood"] == "warm"
    assert "secret" not in matching_event["metadata"]

    try:
        await server_module.client_villager_context("missing_villager")
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Unknown villager context request should raise HTTP 404.")


async def test_client_villager_social_context_payload(server_module: ModuleType) -> None:
    memory_id = server_module.memory_store.add_memory(
        "hugo",
        kind="villager_interaction",
        subject_id="fern",
        text="Hugo traded carving notes with Fern beside the workshop.",
        salience=58,
        emotion="content",
        metadata={
            "other_villager_id": "fern",
            "other_villager_name": "Fern",
            "topic": "woodcarving",
            "location": "workshop",
            "secret": "not public",
        },
    )
    server_module.memory_store.update_relationship(
        "hugo",
        "fern",
        affection_delta=2,
        trust_delta=1,
        familiarity_delta=1,
        metadata={
            "last_interaction_topic": "woodcarving",
            "last_interaction_memory_id": memory_id,
            "secret": "not public",
        },
    )
    event_id = server_module.memory_store.add_event(
        kind="villager_interaction",
        actor_id="hugo",
        target_id="fern",
        location="workshop",
        summary="Hugo and Fern traded careful notes about woodcarving.",
        metadata={
            "actor_memory_id": memory_id,
            "target_memory_id": memory_id + 1,
            "topic": "woodcarving",
            "mood": "content",
            "relationship_delta": {"affection": 2, "trust": 1, "familiarity": 1},
            "secret": "not public",
        },
    )

    payload = await server_module.client_villager_social_context("hugo", limit=10)
    assert payload["villager"]["id"] == "hugo"
    assert payload["villager"]["display_name"] == "Hugo"
    assert "system_prompt" not in payload["villager"]
    assert "private_goals" not in payload["villager"]

    relationship = next(edge for edge in payload["relationships"] if edge["subject_id"] == "fern")
    assert relationship["villager_id"] == "hugo"
    assert relationship["persisted"] is True
    assert relationship["metadata"]["last_interaction_topic"] == "woodcarving"
    assert relationship["metadata"]["last_interaction_memory_id"] == memory_id
    assert "secret" not in relationship["metadata"]

    matching_memory = next(memory for memory in payload["memories"] if memory["id"] == memory_id)
    assert matching_memory["villager_id"] == "hugo"
    assert matching_memory["subject_id"] == "fern"
    assert matching_memory["kind"] == "villager_interaction"
    assert matching_memory["metadata"]["other_villager_id"] == "fern"
    assert matching_memory["metadata"]["topic"] == "woodcarving"
    assert matching_memory["metadata"]["location"] == "workshop"
    assert "secret" not in matching_memory["metadata"]

    matching_event = next(event for event in payload["events"] if event["id"] == event_id)
    assert matching_event["kind"] == "villager_interaction"
    assert matching_event["actor_id"] == "hugo"
    assert matching_event["target_id"] == "fern"
    assert matching_event["metadata"]["topic"] == "woodcarving"
    assert matching_event["metadata"]["actor_memory_id"] == memory_id
    assert matching_event["metadata"]["target_memory_id"] == memory_id + 1
    assert matching_event["metadata"]["relationship_delta"]["trust"] == 1
    assert "secret" not in matching_event["metadata"]

    target_side = await server_module.client_villager_social_context("fern", limit=10)
    assert any(event["id"] == event_id for event in target_side["events"])
    assert any(edge["villager_id"] == "hugo" and edge["subject_id"] == "fern" for edge in target_side["relationships"])

    try:
        await server_module.client_villager_social_context("missing_villager")
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Unknown villager social context request should raise HTTP 404.")


async def test_conversation_memory_influence_public_payload(server_module: ModuleType) -> None:
    away_payload = await server_module.away_tick(actor_id="hugo", target_id="fern", location="workshop")
    social_memory_id = int(away_payload["event"]["metadata"]["actor_memory_id"])

    response = await server_module.handle_ws_payload(
        {
            "type": "player_message",
            "player_id": "influence_test",
            "villager_id": "hugo",
            "text": "What do you think about Fern lately?",
            "context": {
                "location": "workshop",
                "secret": "not public",
            },
        }
    )
    assert response["type"] == "villager_reply"
    assert social_memory_id in response["memories_used"]

    memory_payload = await server_module.recent_memories(
        villager_id="hugo",
        subject_id="influence_test",
        kind="conversation",
        limit=5,
    )
    conversation_memory = next(
        memory for memory in memory_payload["memories"]
        if memory["id"] == response["memory_id"]
    )
    assert social_memory_id in conversation_memory["metadata"]["memories_used"]
    assert social_memory_id in conversation_memory["metadata"]["social_memory_ids"]
    assert all(isinstance(memory_id, int) for memory_id in conversation_memory["metadata"]["social_memory_ids"])
    assert "player_text" not in conversation_memory["metadata"]
    assert "villager_reply" not in conversation_memory["metadata"]
    assert "secret" not in conversation_memory["metadata"]

    event_payload = await server_module.recent_events(
        kind="conversation",
        actor_id="influence_test",
        target_id="hugo",
        limit=5,
    )
    conversation_event = next(
        event for event in event_payload["events"]
        if event["metadata"]["memory_id"] == response["memory_id"]
    )
    assert social_memory_id in conversation_event["metadata"]["memories_used"]
    assert social_memory_id in conversation_event["metadata"]["social_memory_ids"]
    assert all(isinstance(memory_id, int) for memory_id in conversation_event["metadata"]["social_memory_ids"])
    assert "secret" not in conversation_event["metadata"]


async def test_recent_events_payload(server_module: ModuleType) -> None:
    conversation_event_id = server_module.memory_store.add_event(
        kind="conversation",
        actor_id="heather",
        target_id="margot",
        location="garden",
        summary="heather told Margot about a hidden tea shelf.",
        metadata={"memory_id": 40, "mood": "warm", "test": "api_contract"},
    )
    fern_event_id = server_module.memory_store.add_event(
        kind="gift",
        actor_id="heather",
        target_id="fern",
        location="garden",
        summary="heather gave Fern a test fern cutting.",
        metadata={"preference": "liked", "test": "api_contract"},
    )
    event_id = server_module.memory_store.add_event(
        kind="gift",
        actor_id="heather",
        target_id="margot",
        location="town_square",
        summary="heather gave Margot a test rose.",
        metadata={"preference": "loved", "test": "api_contract"},
    )

    payload = await server_module.recent_events(limit=3)
    events = payload["events"]
    assert events
    matching = next(event for event in events if event["id"] == event_id)
    assert matching["kind"] == "gift"
    assert matching["actor_id"] == "heather"
    assert matching["target_id"] == "margot"
    assert matching["metadata"]["preference"] == "loved"
    assert "test" not in matching["metadata"]

    conversation_payload = await server_module.recent_events(kind="conversation", target_id="margot", limit=5)
    conversation_event = next(event for event in conversation_payload["events"] if event["id"] == conversation_event_id)
    assert conversation_event["metadata"]["memory_id"] == 40
    assert conversation_event["metadata"]["mood"] == "warm"
    assert "test" not in conversation_event["metadata"]

    filtered = await server_module.recent_events(
        kind="gift",
        actor_id="heather",
        target_id="margot",
        limit=5,
    )
    filtered_events = filtered["events"]
    assert len(filtered_events) == 1
    assert filtered_events[0]["id"] == event_id
    assert filtered_events[0]["kind"] == "gift"
    assert filtered_events[0]["target_id"] == "margot"

    fern_gifts = await server_module.recent_events(kind="gift", target_id="fern", limit=5)
    assert len(fern_gifts["events"]) == 1
    assert fern_gifts["events"][0]["target_id"] == "fern"

    incremental = await server_module.recent_events(after_id=fern_event_id, limit=5)
    incremental_ids = {event["id"] for event in incremental["events"]}
    assert event_id in incremental_ids
    assert fern_event_id not in incremental_ids
    assert conversation_event_id not in incremental_ids

    no_new_events = await server_module.recent_events(after_id=event_id, limit=5)
    assert no_new_events["events"] == []


async def test_event_detail_payload(server_module: ModuleType) -> None:
    event_id = server_module.memory_store.add_event(
        kind="gift",
        actor_id="heather",
        target_id="margot",
        location="town_square",
        summary="heather gave Margot a tiny porcelain bell.",
        metadata={
            "preference": "loved",
            "item_name": "Tiny Porcelain Bell",
            "secret": "not public",
        },
    )

    payload = await server_module.event_detail(event_id)
    assert payload["id"] == event_id
    assert payload["kind"] == "gift"
    assert payload["actor_id"] == "heather"
    assert payload["target_id"] == "margot"
    assert payload["location"] == "town_square"
    assert payload["summary"].endswith("porcelain bell.")
    assert payload["metadata"]["preference"] == "loved"
    assert payload["metadata"]["item_name"] == "Tiny Porcelain Bell"
    assert "secret" not in payload["metadata"]

    try:
        await server_module.event_detail(event_id + 999)
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Unknown event detail request should raise HTTP 404.")


async def test_recent_notifications_payload(server_module: ModuleType) -> None:
    conversation_event_id = server_module.memory_store.add_event(
        kind="conversation",
        actor_id="notification_test",
        target_id="margot",
        location="garden",
        summary="notification_test told Margot about a moon jar.",
        metadata={"mood": "warm", "secret": "not public"},
    )
    fern_event_id = server_module.memory_store.add_event(
        kind="gift",
        actor_id="notification_test",
        target_id="fern",
        location="garden",
        summary="notification_test gave Fern a pressed leaf.",
        metadata={
            "memory_id": 56,
            "preference": "liked",
            "item_id": "pressed_leaf",
            "item_name": "Pressed Leaf",
            "secret": "not public",
        },
    )
    event_id = server_module.memory_store.add_event(
        kind="gift",
        actor_id="notification_test",
        target_id="margot",
        location="town_square",
        summary="heather gave Margot a test rose.",
        metadata={
            "memory_id": 55,
            "mood": "delighted",
            "preference": "loved",
            "item_id": "test_rose",
            "item_name": "Test Rose",
            "secret": "not public",
        },
    )

    payload = await server_module.recent_notifications(limit=3)
    notifications = payload["notifications"]
    assert notifications
    matching = next(item for item in notifications if item["id"] == f"event-{event_id}")
    assert matching["villager_id"] == "margot"
    assert matching["villager_name"] == "Margot"
    assert matching["title"] == "Margot"
    assert "Test Rose" in matching["body"]
    assert matching["event_kind"] == "gift"
    assert matching["metadata"]["memory_id"] == 55
    assert matching["metadata"]["preference"] == "loved"
    assert "secret" not in matching["metadata"]

    filtered = await server_module.recent_notifications(
        kind="gift",
        actor_id="notification_test",
        target_id="margot",
        limit=5,
    )
    filtered_notifications = filtered["notifications"]
    assert len(filtered_notifications) == 1
    assert filtered_notifications[0]["id"] == f"event-{event_id}"
    assert filtered_notifications[0]["event_kind"] == "gift"
    assert filtered_notifications[0]["villager_id"] == "margot"

    fern_filtered = await server_module.recent_notifications(
        kind="gift",
        actor_id="notification_test",
        target_id="fern",
        limit=5,
    )
    assert len(fern_filtered["notifications"]) == 1
    assert fern_filtered["notifications"][0]["id"] == f"event-{fern_event_id}"
    assert fern_filtered["notifications"][0]["villager_id"] == "fern"

    empty_filtered = await server_module.recent_notifications(
        kind="conversation",
        actor_id="notification_test",
        target_id="fern",
        limit=5,
    )
    assert empty_filtered["notifications"] == []

    incremental = await server_module.recent_notifications(
        actor_id="notification_test",
        after_id=fern_event_id,
        limit=5,
    )
    incremental_ids = {item["id"] for item in incremental["notifications"]}
    assert f"event-{event_id}" in incremental_ids
    assert f"event-{fern_event_id}" not in incremental_ids
    assert f"event-{conversation_event_id}" not in incremental_ids

    no_new_notifications = await server_module.recent_notifications(after_id=event_id, limit=5)
    assert no_new_notifications["notifications"] == []


async def test_notification_summary_payload(server_module: ModuleType) -> None:
    first_id = server_module.memory_store.add_event(
        kind="conversation",
        actor_id="summary_test",
        target_id="margot",
        location="garden",
        summary="summary_test talked with Margot.",
        metadata={"memory_id": 61, "mood": "warm"},
    )
    second_id = server_module.memory_store.add_event(
        kind="gift",
        actor_id="summary_test",
        target_id="margot",
        location="town_square",
        summary="summary_test gave Margot a ribbon.",
        metadata={"memory_id": 62, "preference": "liked", "item_name": "Ribbon"},
    )
    server_module.memory_store.add_event(
        kind="gift",
        actor_id="summary_test",
        target_id="fern",
        location="garden",
        summary="summary_test gave Fern a pressed leaf.",
        metadata={"memory_id": 63, "preference": "liked", "item_name": "Pressed Leaf"},
    )

    summary = await server_module.notification_summary(actor_id="summary_test", target_id="margot")
    assert summary["latest_event_id"] == second_id
    assert summary["after_id"] is None
    assert summary["unseen_count"] == 2
    assert summary["has_unseen"] is True
    assert summary["filters"] == {
        "kind": None,
        "actor_id": "summary_test",
        "target_id": "margot",
    }

    incremental = await server_module.notification_summary(
        actor_id="summary_test",
        target_id="margot",
        after_id=first_id,
    )
    assert incremental["latest_event_id"] == second_id
    assert incremental["after_id"] == first_id
    assert incremental["unseen_count"] == 1
    assert incremental["has_unseen"] is True

    no_new = await server_module.notification_summary(
        actor_id="summary_test",
        target_id="margot",
        after_id=second_id,
    )
    assert no_new["latest_event_id"] == second_id
    assert no_new["unseen_count"] == 0
    assert no_new["has_unseen"] is False

    empty = await server_module.notification_summary(actor_id="summary_test", target_id="hugo")
    assert empty["latest_event_id"] is None
    assert empty["unseen_count"] == 0
    assert empty["has_unseen"] is False


async def test_notification_detail_payload(server_module: ModuleType) -> None:
    event_id = server_module.memory_store.add_event(
        kind="gift",
        actor_id="heather",
        target_id="margot",
        location="town_square",
        summary="heather gave Margot a tiny porcelain bell.",
        metadata={
            "memory_id": 88,
            "mood": "delighted",
            "preference": "loved",
            "item_id": "tiny_bell",
            "item_name": "Tiny Porcelain Bell",
            "secret": "not public",
        },
    )

    payload = await server_module.notification_detail(event_id)
    assert payload["id"] == f"event-{event_id}"
    assert payload["villager_id"] == "margot"
    assert payload["villager_name"] == "Margot"
    assert payload["title"] == "Margot"
    assert "Tiny Porcelain Bell" in payload["body"]
    assert payload["event_kind"] == "gift"
    assert payload["metadata"]["memory_id"] == 88
    assert payload["metadata"]["mood"] == "delighted"
    assert payload["metadata"]["preference"] == "loved"
    assert payload["metadata"]["item_id"] == "tiny_bell"
    assert payload["metadata"]["item_name"] == "Tiny Porcelain Bell"
    assert "secret" not in payload["metadata"]

    try:
        await server_module.notification_detail(event_id + 9999)
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Unknown notification detail request should raise HTTP 404.")


async def test_notification_cursor_payload(server_module: ModuleType) -> None:
    client_id = "cursor_contract_mobile"
    initial = await server_module.notification_cursor(client_id)
    latest_before = server_module.memory_store.query_events(limit=1)
    latest_before_id = latest_before[0].id if latest_before else None

    assert initial["client_id"] == client_id
    assert initial["last_event_id"] == 0
    assert initial["updated_at"] is None
    assert initial["summary"]["latest_event_id"] == latest_before_id
    assert initial["summary"]["after_id"] == 0
    assert initial["summary"]["unseen_count"] == server_module.memory_store.count_events(after_id=0)

    first_id = server_module.memory_store.add_event(
        kind="conversation",
        actor_id="cursor_test",
        target_id="margot",
        location="garden",
        summary="cursor_test talked with Margot.",
        metadata={"memory_id": 91, "mood": "warm"},
    )
    second_id = server_module.memory_store.add_event(
        kind="gift",
        actor_id="cursor_test",
        target_id="margot",
        location="town_square",
        summary="cursor_test gave Margot a tiny ribbon.",
        metadata={"memory_id": 92, "preference": "liked", "item_name": "Tiny Ribbon"},
    )

    updated = await server_module.update_notification_cursor(client_id, first_id)
    assert updated["client_id"] == client_id
    assert updated["last_event_id"] == first_id
    assert updated["updated_at"]
    assert updated["summary"]["latest_event_id"] == second_id
    assert updated["summary"]["after_id"] == first_id
    assert updated["summary"]["unseen_count"] == 1
    assert updated["summary"]["has_unseen"] is True

    stale_update = await server_module.update_notification_cursor(client_id, first_id - 1)
    assert stale_update["last_event_id"] == first_id
    assert stale_update["summary"]["unseen_count"] == 1

    advanced = await server_module.update_notification_cursor(client_id, second_id)
    assert advanced["last_event_id"] == second_id
    assert advanced["summary"]["latest_event_id"] == second_id
    assert advanced["summary"]["after_id"] == second_id
    assert advanced["summary"]["unseen_count"] == 0
    assert advanced["summary"]["has_unseen"] is False

    fetched = await server_module.notification_cursor(client_id)
    assert fetched["last_event_id"] == second_id
    assert fetched["summary"]["unseen_count"] == 0

    try:
        await server_module.notification_cursor("   ")
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("Blank notification cursor client id should raise HTTP 400.")


async def test_notification_inbox_payload(server_module: ModuleType) -> None:
    missing_cursor_client_id = "inbox_missing_cursor_mobile"
    missing_cursor = await server_module.notification_inbox(missing_cursor_client_id, limit=1)
    assert missing_cursor["client_id"] == missing_cursor_client_id
    assert missing_cursor["cursor"]["last_event_id"] == 0
    assert missing_cursor["cursor"]["updated_at"] is None
    assert missing_cursor["cursor"]["summary"]["after_id"] == 0
    assert missing_cursor["count"] == len(missing_cursor["notifications"])
    assert missing_cursor["count"] <= 1
    assert (
        missing_cursor["has_more"]
        is (missing_cursor["cursor"]["summary"]["unseen_count"] > missing_cursor["count"])
    )

    baseline_events = server_module.memory_store.query_events(limit=1)
    baseline_event_id = baseline_events[0].id if baseline_events else 0
    client_id = "inbox_contract_mobile"
    await server_module.update_notification_cursor(client_id, baseline_event_id)

    first_id = server_module.memory_store.add_event(
        kind="conversation",
        actor_id="inbox_test",
        target_id="margot",
        location="garden",
        summary="inbox_test talked with Margot about a ribbon spool.",
        metadata={"memory_id": 101, "mood": "warm"},
    )
    second_id = server_module.memory_store.add_event(
        kind="gift",
        actor_id="inbox_test",
        target_id="margot",
        location="town_square",
        summary="inbox_test gave Margot a blue ribbon.",
        metadata={"memory_id": 102, "preference": "liked", "item_name": "Blue Ribbon"},
    )
    third_id = server_module.memory_store.add_event(
        kind="gift",
        actor_id="inbox_test",
        target_id="fern",
        location="garden",
        summary="inbox_test gave Fern a pressed violet.",
        metadata={"memory_id": 103, "preference": "liked", "item_name": "Pressed Violet"},
    )

    first_batch = await server_module.notification_inbox(client_id, limit=2)
    assert first_batch["client_id"] == client_id
    assert first_batch["cursor"]["last_event_id"] == baseline_event_id
    assert first_batch["cursor"]["summary"]["unseen_count"] == 3
    assert first_batch["count"] == 2
    assert [item["id"] for item in first_batch["notifications"]] == [
        f"event-{first_id}",
        f"event-{second_id}",
    ]
    assert first_batch["next_cursor_event_id"] == second_id
    assert first_batch["has_more"] is True

    await server_module.update_notification_cursor(client_id, first_batch["next_cursor_event_id"])
    second_batch = await server_module.notification_inbox(client_id, limit=5)
    assert second_batch["cursor"]["last_event_id"] == second_id
    assert second_batch["cursor"]["summary"]["unseen_count"] == 1
    assert second_batch["count"] == 1
    assert second_batch["notifications"][0]["id"] == f"event-{third_id}"
    assert second_batch["next_cursor_event_id"] == third_id
    assert second_batch["has_more"] is False

    await server_module.update_notification_cursor(client_id, second_batch["next_cursor_event_id"])
    empty_batch = await server_module.notification_inbox(client_id, limit=5)
    assert empty_batch["cursor"]["last_event_id"] == third_id
    assert empty_batch["notifications"] == []
    assert empty_batch["count"] == 0
    assert empty_batch["next_cursor_event_id"] == third_id
    assert empty_batch["has_more"] is False

    try:
        await server_module.notification_inbox("   ")
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("Blank notification inbox client id should raise HTTP 400.")


async def test_relationship_detail_payload(server_module: ModuleType) -> None:
    initial = await server_module.relationship_detail("margot", "heather")

    assert initial["villager_id"] == "margot"
    assert initial["subject_id"] == "heather"
    assert initial["persisted"] is False
    assert initial["affection"] == 8
    assert initial["trust"] == 12
    assert initial["familiarity"] == 2
    assert initial["tension"] == 0
    assert initial["updated_at"] is None
    assert initial["metadata"] == {}
    assert server_module.memory_store.peek_relationship("margot", "heather") is None

    server_module.memory_store.get_relationship(
        "margot",
        "heather",
        {"affection": 8, "trust": 12, "familiarity": 2, "tension": 0},
    )
    server_module.memory_store.update_relationship(
        "margot",
        "heather",
        affection_delta=2,
        trust_delta=1,
        familiarity_delta=1,
        metadata={
            "last_gift": "Test Rose",
            "last_gift_preference": "loved",
            "last_memory_id": 77,
            "secret": "not public",
        },
    )

    persisted = await server_module.relationship_detail("margot", "heather")
    assert persisted["persisted"] is True
    assert persisted["affection"] == 10
    assert persisted["trust"] == 13
    assert persisted["familiarity"] == 3
    assert persisted["metadata"]["last_gift"] == "Test Rose"
    assert persisted["metadata"]["last_gift_preference"] == "loved"
    assert persisted["metadata"]["last_memory_id"] == 77
    assert "secret" not in persisted["metadata"]

    try:
        await server_module.relationship_detail("missing_villager", "heather")
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Unknown villager relationship request should raise HTTP 404.")


async def test_recent_memories_payload(server_module: ModuleType) -> None:
    gift_id = server_module.memory_store.add_memory(
        "margot",
        kind="gift",
        subject_id="heather",
        text="heather gave Margot a Test Rose.",
        salience=80,
        emotion="delighted",
        metadata={
            "item": {"item_id": "test_rose", "display_name": "Test Rose"},
            "preference": "loved",
            "context": {"location": "town_square", "secret": "not public"},
            "secret": "not public",
        },
    )
    server_module.memory_store.add_memory(
        "margot",
        kind="conversation",
        subject_id="heather",
        text="heather told Margot about moonlit lavender.",
        salience=65,
        emotion="warm",
        metadata={
            "conversation_id": "conversation-test",
            "player_text": "private raw player text",
            "world": {"time_label": "morning", "season": "spring", "weather": "clear"},
        },
    )

    payload = await server_module.recent_memories(
        villager_id="margot",
        subject_id="heather",
        kind="gift",
        limit=3,
    )
    memories = payload["memories"]
    assert len(memories) == 1
    matching = memories[0]
    assert matching["id"] == gift_id
    assert matching["villager_id"] == "margot"
    assert matching["kind"] == "gift"
    assert matching["subject_id"] == "heather"
    assert matching["salience"] == 80
    assert matching["emotion"] == "delighted"
    assert matching["metadata"]["item_id"] == "test_rose"
    assert matching["metadata"]["item_name"] == "Test Rose"
    assert matching["metadata"]["preference"] == "loved"
    assert matching["metadata"]["location"] == "town_square"
    assert "secret" not in matching["metadata"]

    conversation_payload = await server_module.recent_memories(
        villager_id="margot",
        subject_id="heather",
        kind="conversation",
        limit=3,
    )
    conversation_memory = conversation_payload["memories"][0]
    assert conversation_memory["metadata"]["conversation_id"] == "conversation-test"
    assert conversation_memory["metadata"]["world_time_label"] == "morning"
    assert conversation_memory["metadata"]["world_season"] == "spring"
    assert conversation_memory["metadata"]["world_weather"] == "clear"
    assert "player_text" not in conversation_memory["metadata"]

    try:
        await server_module.recent_memories(villager_id="missing_villager")
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Unknown villager memory request should raise HTTP 404.")


async def test_memory_detail_payload(server_module: ModuleType) -> None:
    influence_memory_id = server_module.memory_store.add_memory(
        "hugo",
        kind="villager_interaction",
        subject_id="fern",
        text="Hugo and Fern compared careful notes about the workshop kettle.",
        salience=57,
        emotion="content",
        metadata={
            "other_villager_id": "fern",
            "other_villager_name": "Fern",
            "topic": "workshop tea",
            "location": "workshop",
            "secret": "not public",
        },
    )
    memory_id = server_module.memory_store.add_memory(
        "margot",
        kind="conversation",
        subject_id="heather",
        text="heather asked Margot why Hugo remembered Fern's workshop kettle.",
        salience=73,
        emotion="warm",
        metadata={
            "conversation_id": "memory-detail-contract",
            "memories_used": [influence_memory_id, "404", "not-a-memory-id"],
            "social_memory_ids": [influence_memory_id, "not-a-memory-id"],
            "player_text": "private raw player text",
            "villager_reply": "private raw villager reply",
            "context": {"location": "town_square", "secret": "not public"},
            "world": {"time_label": "afternoon", "season": "spring", "weather": "clear"},
            "secret": "not public",
        },
    )
    event_id = server_module.memory_store.add_event(
        kind="conversation",
        actor_id="heather",
        target_id="margot",
        location="town_square",
        summary="heather asked Margot about Hugo and Fern.",
        metadata={"memory_id": memory_id, "secret": "not public"},
    )

    before = server_module.memory_store._connection.execute(
        "SELECT access_count, last_accessed_at FROM memories WHERE id = ?",
        (memory_id,),
    ).fetchone()
    payload = await server_module.memory_detail(memory_id)
    after = server_module.memory_store._connection.execute(
        "SELECT access_count, last_accessed_at FROM memories WHERE id = ?",
        (memory_id,),
    ).fetchone()

    assert before["access_count"] == 0
    assert before["last_accessed_at"] is None
    assert after["access_count"] == 0
    assert after["last_accessed_at"] is None
    assert payload["id"] == memory_id
    assert payload["villager_id"] == "margot"
    assert payload["kind"] == "conversation"
    assert payload["subject_id"] == "heather"
    assert payload["salience"] == 73
    assert payload["emotion"] == "warm"
    assert payload["metadata"]["conversation_id"] == "memory-detail-contract"
    assert payload["metadata"]["memories_used"] == [influence_memory_id, 404]
    assert payload["metadata"]["social_memory_ids"] == [influence_memory_id]
    assert payload["metadata"]["location"] == "town_square"
    assert payload["metadata"]["world_time_label"] == "afternoon"
    assert payload["metadata"]["world_season"] == "spring"
    assert payload["metadata"]["world_weather"] == "clear"
    assert "player_text" not in payload["metadata"]
    assert "villager_reply" not in payload["metadata"]
    assert "secret" not in payload["metadata"]

    recent_payload = await server_module.recent_memories(
        villager_id="margot",
        subject_id="heather",
        kind="conversation",
        limit=10,
    )
    matching_recent = next(memory for memory in recent_payload["memories"] if memory["id"] == memory_id)
    assert payload == matching_recent

    event_payload = await server_module.recent_events(
        kind="conversation",
        actor_id="heather",
        target_id="margot",
        limit=5,
    )
    matching_event = next(event for event in event_payload["events"] if event["id"] == event_id)
    assert matching_event["metadata"]["memory_id"] == memory_id
    assert await server_module.memory_detail(matching_event["metadata"]["memory_id"]) == payload

    influence_payload = await server_module.memory_detail(influence_memory_id)
    assert influence_payload["kind"] == "villager_interaction"
    assert influence_payload["subject_id"] == "fern"
    assert influence_payload["metadata"]["other_villager_id"] == "fern"
    assert influence_payload["metadata"]["other_villager_name"] == "Fern"
    assert influence_payload["metadata"]["topic"] == "workshop tea"
    assert influence_payload["metadata"]["location"] == "workshop"
    assert "secret" not in influence_payload["metadata"]

    try:
        await server_module.memory_detail(memory_id + 9999)
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Unknown memory detail request should raise HTTP 404.")


async def test_conversation_turns_payload(server_module: ModuleType) -> None:
    conversation_id = "contract-conversation"
    server_module.memory_store.add_conversation_turn(
        conversation_id,
        "margot",
        "heather",
        speaker="heather",
        text="I keep a tiny porcelain fox on the kitchen sill.",
        metadata={"context": {"location": "town_square", "secret": "not public"}},
    )
    server_module.memory_store.add_conversation_turn(
        conversation_id,
        "margot",
        "heather",
        speaker="margot",
        text="I'll remember the little fox.",
        metadata={"mood": "warm", "memories_used": [4, "5"], "secret": "not public"},
    )

    payload = await server_module.conversation_turns(conversation_id)
    assert payload["conversation_id"] == conversation_id
    turns = payload["turns"]
    assert len(turns) == 2
    assert turns[0]["speaker"] == "heather"
    assert turns[0]["text"].startswith("I keep")
    assert turns[0]["metadata"]["location"] == "town_square"
    assert "secret" not in turns[0]["metadata"]
    assert turns[1]["speaker"] == "margot"
    assert turns[1]["metadata"]["mood"] == "warm"
    assert turns[1]["metadata"]["memories_used"] == [4, 5]
    assert "secret" not in turns[1]["metadata"]

    try:
        await server_module.conversation_turns("missing-conversation")
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Unknown conversation transcript request should raise HTTP 404.")


async def test_away_tick_payload(server_module: ModuleType) -> None:
    payload = await server_module.away_tick(actor_id="margot", target_id="fern", location="tea_garden")

    assert payload["type"] == "away_interaction"
    assert payload["actor"]["id"] == "margot"
    assert payload["target"]["id"] == "fern"
    assert payload["topic"] == "tea"
    assert payload["event"]["kind"] == "villager_interaction"
    assert payload["event"]["location"] == "tea_garden"

    relationship = await server_module.relationship_detail("margot", "fern")
    assert relationship["persisted"] is True
    assert relationship["affection"] == 1
    assert relationship["trust"] == 1
    assert relationship["familiarity"] == 1
    assert relationship["metadata"]["last_interaction_topic"] == "tea"
    assert "secret" not in relationship["metadata"]

    graph = await server_module.relationships(villager_id="margot", limit=20)
    graph_edges = graph["relationships"]
    fern_edge = next(edge for edge in graph_edges if edge["subject_id"] == "fern")
    assert fern_edge["villager_id"] == "margot"
    assert fern_edge["metadata"]["last_interaction_topic"] == "tea"
    assert fern_edge["metadata"]["last_interaction_memory_id"]

    reverse_graph = await server_module.relationships(subject_id="margot", limit=20)
    assert any(edge["villager_id"] == "fern" for edge in reverse_graph["relationships"])

    memories = await server_module.recent_memories(
        villager_id="margot",
        subject_id="fern",
        kind="villager_interaction",
        limit=5,
    )
    assert len(memories["memories"]) == 1
    assert memories["memories"][0]["metadata"]["topic"] == "tea"
    assert memories["memories"][0]["metadata"]["location"] == "tea_garden"

    events = await server_module.recent_events(limit=5)
    matching = next(event for event in events["events"] if event["kind"] == "villager_interaction")
    assert matching["actor_id"] == "margot"
    assert matching["target_id"] == "fern"
    assert matching["metadata"]["topic"] == "tea"
    assert matching["metadata"]["actor_memory_id"]
    assert matching["metadata"]["target_memory_id"]
    assert matching["metadata"]["relationship_delta"]["affection"] == 1

    filtered_events = await server_module.recent_events(
        kind="villager_interaction",
        actor_id="margot",
        target_id="fern",
        limit=5,
    )
    assert len(filtered_events["events"]) == 1
    assert filtered_events["events"][0]["id"] == matching["id"]

    empty_events = await server_module.recent_events(
        kind="gift",
        actor_id="margot",
        target_id="fern",
        limit=5,
    )
    assert empty_events["events"] == []

    notifications = await server_module.recent_notifications(limit=5)
    matching_notification = next(
        item for item in notifications["notifications"] if item["event_kind"] == "villager_interaction"
    )
    assert matching_notification["villager_id"] == "fern"
    assert matching_notification["metadata"]["topic"] == "tea"

    filtered_notifications = await server_module.recent_notifications(
        kind="villager_interaction",
        actor_id="margot",
        target_id="fern",
        limit=5,
    )
    assert len(filtered_notifications["notifications"]) == 1
    assert filtered_notifications["notifications"][0]["id"] == f"event-{matching['id']}"
    assert filtered_notifications["notifications"][0]["villager_id"] == "fern"

    empty_notifications = await server_module.recent_notifications(
        kind="gift",
        actor_id="margot",
        target_id="fern",
        limit=5,
    )
    assert empty_notifications["notifications"] == []

    try:
        await server_module.away_tick(actor_id="margot", target_id="margot")
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("Same-villager away tick should raise HTTP 400.")


async def test_away_ticks_payload(server_module: ModuleType) -> None:
    payload = await server_module.away_ticks(
        count=2,
        actor_id="margot",
        target_id="fern",
        location="tea_garden",
    )

    assert payload["type"] == "away_interaction_batch"
    assert payload["requested_count"] == 2
    assert payload["count"] == 2
    assert len(payload["ticks"]) == 2
    assert all(tick["event"]["kind"] == "villager_interaction" for tick in payload["ticks"])
    assert all(tick["actor"]["id"] == "margot" for tick in payload["ticks"])
    assert all(tick["target"]["id"] == "fern" for tick in payload["ticks"])

    relationship = await server_module.relationship_detail("margot", "fern")
    assert relationship["affection"] == 3
    assert relationship["trust"] == 3
    assert relationship["familiarity"] == 3

    clamped = await server_module.away_ticks(
        count=99,
        actor_id="margot",
        target_id="fern",
        location="tea_garden",
    )
    assert clamped["requested_count"] == 99
    assert clamped["count"] == 12
    assert len(clamped["ticks"]) == 12

    filtered_events = await server_module.recent_events(
        kind="villager_interaction",
        actor_id="margot",
        target_id="fern",
        limit=20,
    )
    assert len(filtered_events["events"]) >= 15

    notifications = await server_module.recent_notifications(
        kind="villager_interaction",
        actor_id="margot",
        target_id="fern",
        limit=20,
    )
    assert len(notifications["notifications"]) >= 15

    try:
        await server_module.away_ticks(count=2, actor_id="margot", target_id="margot")
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("Same-villager away tick batch should raise HTTP 400.")


async def test_canonical_ws_payload_names(server_module: ModuleType) -> None:
    message_payload = await server_module.handle_ws_payload(
        {
            "type": "player_message",
            "player_id": "protocol_contract",
            "villager_id": "margot",
            "text": "Hello Margot, please remember that protocol smoke tests use root payload names.",
            "context": {"location": "town_square", "test": "canonical_ws_payload_names"},
        }
    )

    assert message_payload["type"] == "villager_reply"
    assert message_payload["villager_id"] == "margot"
    assert message_payload["display_name"] == "Margot"
    assert message_payload["memory_id"] > 0

    gift_payload = await server_module.handle_ws_payload(
        {
            "type": "gift_item",
            "player_id": "protocol_contract",
            "villager_id": "margot",
            "item": {"item_id": "dusty_rose"},
            "context": {"location": "town_square", "gift_source": "protocol_contract"},
        }
    )

    assert gift_payload["type"] == "villager_reply"
    assert gift_payload["villager_id"] == "margot"
    assert gift_payload["display_name"] == "Margot"
    assert gift_payload["memories_used"] == [gift_payload["memory_id"]]

    for legacy_type in ["hello", "begin", "say", "gift", "end", "set_name"]:
        legacy_payload = await server_module.handle_ws_payload(
            {
                "type": legacy_type,
                "player_id": "protocol_contract",
                "villager_id": "margot",
                "text": "legacy protocol should not be canonical",
            }
        )
        assert legacy_payload["type"] == "error"
        assert legacy_payload["message"] == f"Unknown message type: {legacy_type}"


async def test_unknown_ws_payload(server_module: ModuleType) -> None:
    payload = await server_module.handle_ws_payload({"type": "not_a_real_message"})

    assert payload["type"] == "error"
    assert "Unknown message type" in payload["message"]


def main() -> None:
    previous_db = os.environ.get("HH_MEMORY_DB")
    previous_provider = os.environ.get("HOLLOW_LLM_PROVIDER")
    with TemporaryDirectory() as tmp_dir:
        server_module = import_server_with_temp_db(tmp_dir)
        try:
            test_route_contract(server_module)
            asyncio.run(test_health_payload(server_module))
            asyncio.run(test_read_only_payloads(server_module))
            asyncio.run(test_client_bootstrap_payload(server_module))
            asyncio.run(test_client_inventory_payload(server_module))
            asyncio.run(test_catalog_gift_payload(server_module))
            asyncio.run(test_client_villager_context_payload(server_module))
            asyncio.run(test_client_villager_social_context_payload(server_module))
            asyncio.run(test_conversation_memory_influence_public_payload(server_module))
            asyncio.run(test_recent_events_payload(server_module))
            asyncio.run(test_event_detail_payload(server_module))
            asyncio.run(test_recent_notifications_payload(server_module))
            asyncio.run(test_notification_summary_payload(server_module))
            asyncio.run(test_notification_detail_payload(server_module))
            asyncio.run(test_notification_cursor_payload(server_module))
            asyncio.run(test_notification_inbox_payload(server_module))
            asyncio.run(test_relationship_detail_payload(server_module))
            asyncio.run(test_recent_memories_payload(server_module))
            asyncio.run(test_memory_detail_payload(server_module))
            asyncio.run(test_conversation_turns_payload(server_module))
            asyncio.run(test_away_tick_payload(server_module))
            asyncio.run(test_away_ticks_payload(server_module))
            asyncio.run(test_canonical_ws_payload_names(server_module))
            asyncio.run(test_unknown_ws_payload(server_module))
        finally:
            server_module.memory_store.close()
            if previous_db is None:
                os.environ.pop("HH_MEMORY_DB", None)
            else:
                os.environ["HH_MEMORY_DB"] = previous_db
            if previous_provider is None:
                os.environ.pop("HOLLOW_LLM_PROVIDER", None)
            else:
                os.environ["HOLLOW_LLM_PROVIDER"] = previous_provider

    print("PASS: FastAPI route and payload contract is stable.")


if __name__ == "__main__":
    main()
