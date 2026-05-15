"""Live HTTP/WebSocket smoke test for the morning demo stack.

Run from the repo root with server dependencies installed:

    python -m server.tests.test_live_demo_stack

Or without a persistent virtualenv:

    uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_live_demo_stack

The test starts an isolated uvicorn server, drives the real `/ws` route, and
then verifies the HTTP read endpoints against the same temporary SQLite state.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

import websockets


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def wait_for_health(url: str, process: subprocess.Popen[str], timeout_seconds: float = 10.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if process.poll() is not None:
            stderr = process.stderr.read() if process.stderr else ""
            raise RuntimeError(f"Server exited before health check passed:\n{stderr}")
        try:
            with urlopen(url, timeout=1.0) as response:
                if response.status == 200:
                    return
        except URLError:
            time.sleep(0.2)
    raise RuntimeError(f"Server did not become healthy at {url}")


def http_json(base_url: str, path: str, query: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{base_url}{path}"
    if query:
        url = f"{url}?{urlencode(query)}"
    with urlopen(url, timeout=2.0) as response:
        return json.loads(response.read().decode("utf-8"))


async def send_ws_payload(ws_url: str, payload: dict[str, Any]) -> dict[str, Any]:
    async with websockets.connect(ws_url, open_timeout=5) as websocket:
        greeting = json.loads(await websocket.recv())
        if greeting.get("type") != "server_status":
            raise RuntimeError(f"Expected server_status greeting, received: {greeting}")

        await websocket.send(json.dumps(payload))
        response = json.loads(await websocket.recv())
        if response.get("type") != "villager_reply":
            raise RuntimeError(f"Expected villager_reply, received: {response}")
        return response


async def drive_story(ws_url: str) -> dict[str, Any]:
    context = {"location": "town_square", "test": "live_demo_stack"}
    first = await send_ws_payload(
        ws_url,
        {
            "type": "player_message",
            "player_id": "heather",
            "villager_id": "margot",
            "text": "Margot, please remember that Heather keeps a tiny porcelain fox on the kitchen sill.",
            "context": context,
        },
    )
    recall = await send_ws_payload(
        ws_url,
        {
            "type": "player_message",
            "player_id": "heather",
            "villager_id": "margot",
            "text": "Do you remember what I keep on the kitchen sill?",
            "context": context,
        },
    )
    gift = await send_ws_payload(
        ws_url,
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
            "context": context,
        },
    )
    return {"first": first, "recall": recall, "gift": gift}


def assert_live_state(base_url: str, story: dict[str, Any]) -> None:
    recall_text = str(story["recall"]["text"]).lower()
    assert "porcelain" in recall_text or "fox" in recall_text or "sill" in recall_text, story["recall"]["text"]

    world = http_json(base_url, "/world")
    assert "time_label" in world
    assert "day_length_seconds" in world

    villager = http_json(base_url, "/villagers/margot")
    assert villager["display_name"] == "Margot"
    assert "system_prompt" not in villager
    assert "private_goals" not in villager

    relationship = http_json(base_url, "/relationships/margot/heather")
    assert relationship["persisted"] is True
    assert relationship["affection"] > 8
    assert relationship["trust"] > 12
    assert relationship["familiarity"] > 2
    assert relationship["metadata"]["last_gift"] == "Dusty Rose"
    assert relationship["metadata"]["last_gift_preference"] == "loved"

    conversation_memories = http_json(
        base_url,
        "/memories/recent",
        {"villager_id": "margot", "subject_id": "heather", "kind": "conversation", "limit": 10},
    )["memories"]
    fox_memory = next(memory for memory in conversation_memories if "porcelain fox" in memory["text"].lower())
    transcript = http_json(base_url, f"/conversations/{fox_memory['metadata']['conversation_id']}/turns")
    assert transcript["conversation_id"] == fox_memory["metadata"]["conversation_id"]
    assert len(transcript["turns"]) == 2
    assert transcript["turns"][0]["speaker"] == "heather"
    assert any("porcelain fox" in turn["text"].lower() for turn in transcript["turns"])
    assert transcript["turns"][0]["metadata"]["location"] == "town_square"
    assert transcript["turns"][1]["speaker"] == "margot"
    assert "mood" in transcript["turns"][1]["metadata"]

    gift_memories = http_json(
        base_url,
        "/memories/recent",
        {"villager_id": "margot", "subject_id": "heather", "kind": "gift", "limit": 10},
    )["memories"]
    assert len(gift_memories) == 1
    gift_memory = gift_memories[0]
    assert gift_memory["metadata"]["item_id"] == "dusty_rose"
    assert gift_memory["metadata"]["item_name"] == "Dusty Rose"
    assert gift_memory["metadata"]["preference"] == "loved"
    assert gift_memory["metadata"]["location"] == "town_square"

    events = http_json(base_url, "/events/recent", {"limit": 10})["events"]
    assert any(event["kind"] == "conversation" for event in events)
    assert any(event["kind"] == "gift" for event in events)

    notifications = http_json(base_url, "/notifications/recent", {"limit": 10})["notifications"]
    gift_notification = next(item for item in notifications if item["event_kind"] == "gift")
    assert gift_notification["villager_id"] == "margot"
    assert "Dusty Rose" in gift_notification["body"]
    assert gift_notification["metadata"]["preference"] == "loved"
    assert any(item["event_kind"] == "conversation" for item in notifications)


def run_with_temp_server() -> dict[str, Any]:
    port = find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    ws_url = f"ws://127.0.0.1:{port}/ws"

    with TemporaryDirectory() as tmp_dir:
        env = os.environ.copy()
        env["HH_MEMORY_DB"] = str(Path(tmp_dir) / "live_demo_stack.sqlite3")
        env.pop("ANTHROPIC_API_KEY", None)
        env["HOLLOW_LLM_PROVIDER"] = "fallback"

        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "server.api.server:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--log-level",
                "warning",
            ],
            cwd=Path(__file__).resolve().parents[2],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            wait_for_health(f"{base_url}/health", process)
            story = asyncio.run(drive_story(ws_url))
            assert_live_state(base_url, story)
            return story
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def main() -> None:
    story = run_with_temp_server()
    print("Recall reply:", story["recall"]["text"])
    print("Gift reply:", story["gift"]["text"])
    print("PASS: Live demo stack persisted WebSocket state and exposed it through HTTP endpoints.")


if __name__ == "__main__":
    main()
