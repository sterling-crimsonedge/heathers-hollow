"""API server for Heather's Hollow.

FastAPI app with:
  - GET  /                   → tiny status JSON, sanity check
  - GET  /world              → current world state (time, weather, villagers)
  - GET  /villagers          → roster + spawn positions for the client
  - POST /player/name        → set the player's display name
  - WS   /ws                 → real-time conversation channel

Run:
    uvicorn server.api.server:app --host 0.0.0.0 --port 8765 --reload

Or just:
    python -m server.api.server
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..ai.conversation import ConversationEngine
from ..ai.memory import MemoryStore
from ..ai.personalities import ALL_VILLAGERS, get_villager, list_villagers
from ..world.events import (
    EVT_PLAYER_APPROACHED,
    EVT_PLAYER_ENTERED,
    EVT_PLAYER_GAVE_GIFT,
    EVT_PLAYER_SET_NAME,
    default_bus,
)
from ..world.state import WorldState


# --- bootstrap ---------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = REPO_ROOT / "server" / "data" / "hollow.db"

memory_store = MemoryStore(DB_PATH)
world = WorldState()
# Seed villager positions into the world so the client can fetch them.
for v in list_villagers():
    world.villager_positions[v.id] = v.spawn_position

engine = ConversationEngine(memory_store, world)


app = FastAPI(title="Heather's Hollow AI", version="0.1.0")

# Allow any origin during dev — the web demo is served from a static file server.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- REST --------------------------------------------------------------------

@app.get("/")
async def root():
    return {
        "service": "heathers-hollow",
        "claude": "live (via claude CLI)" if engine.using_real_claude else "stubbed (claude CLI not on PATH)",
        "villagers": [v.id for v in list_villagers()],
    }


@app.get("/world")
async def world_state():
    return world.to_dict()


@app.get("/villagers")
async def villagers():
    out = []
    for v in list_villagers():
        rel = memory_store.get_relationship(v.id, "player")
        out.append({
            "id": v.id,
            "name": v.name,
            "role": v.role,
            "color": v.color_hex,
            "spawn": list(v.spawn_position),
            "affection": rel.affection,
            "familiarity": rel.familiarity,
        })
    return {"villagers": out}


class PlayerNameIn(BaseModel):
    name: str


@app.post("/player/name")
async def set_player_name(body: PlayerNameIn):
    memory_store.set_player_name(body.name.strip())
    await default_bus.emit(EVT_PLAYER_SET_NAME, name=body.name)
    return {"ok": True, "name": body.name}


@app.get("/player")
async def player_profile():
    return {"name": memory_store.get_player_name()}


# --- WebSocket protocol ------------------------------------------------------
#
# Messages from client → server:
#   {"type": "hello"}
#   {"type": "begin", "villager": "maple"}
#   {"type": "say", "villager": "maple", "text": "good morning"}
#   {"type": "gift", "villager": "maple", "item": "sunflower"}
#   {"type": "end", "villager": "maple"}
#
# Messages from server → client:
#   {"type": "ready", "world": {...}, "villagers": [...]}
#   {"type": "greeting_chunk", "villager": "maple", "text": "..."}
#   {"type": "greeting_end", "villager": "maple"}
#   {"type": "reply_chunk", "villager": "maple", "text": "..."}
#   {"type": "reply_end", "villager": "maple"}
#   {"type": "summary", "villager": "maple", "text": "..."}
#   {"type": "world_tick", "world": {...}}
#   {"type": "error", "message": "..."}

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    # active conversations per villager id, for this socket
    active: dict[str, int] = {}

    await default_bus.emit(EVT_PLAYER_ENTERED)
    await ws.send_json({
        "type": "ready",
        "world": world.to_dict(),
        "villagers": [
            {"id": v.id, "name": v.name, "role": v.role,
             "color": v.color_hex, "spawn": list(v.spawn_position)}
            for v in list_villagers()
        ],
        "player_name": memory_store.get_player_name(),
        "claude_live": engine.using_real_claude,
    })

    # background world ticker — sends time updates every 5s
    async def tick_world():
        while True:
            try:
                await asyncio.sleep(5)
                await ws.send_json({"type": "world_tick", "world": world.to_dict()})
            except Exception:
                return

    ticker = asyncio.create_task(tick_world())

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "message": "invalid json"})
                continue
            await _handle_ws_message(ws, msg, active)
    except WebSocketDisconnect:
        pass
    finally:
        ticker.cancel()
        # close any dangling conversations gracefully
        for vid, conv_id in list(active.items()):
            try:
                villager = get_villager(vid)
                summary = await engine.end(villager, conv_id)
                # we can't send to a closed socket; this is best-effort persistence
            except Exception as e:
                print(f"[ws] failed to close conversation for {vid}: {e}")


async def _handle_ws_message(ws: WebSocket, msg: dict, active: dict[str, int]) -> None:
    msg_type = msg.get("type")

    if msg_type == "hello":
        await ws.send_json({"type": "ready", "world": world.to_dict()})
        return

    if msg_type == "begin":
        vid = msg.get("villager")
        if not vid or vid not in ALL_VILLAGERS:
            await ws.send_json({"type": "error", "message": f"unknown villager '{vid}'"})
            return
        villager = get_villager(vid)
        await default_bus.emit(EVT_PLAYER_APPROACHED, villager_id=vid)
        conv_id = engine.begin(villager)
        active[vid] = conv_id

        # stream the greeting
        async for chunk in engine.greeting(villager, conv_id):
            await ws.send_json({
                "type": "greeting_chunk",
                "villager": vid,
                "text": chunk,
            })
        await ws.send_json({"type": "greeting_end", "villager": vid})
        return

    if msg_type == "say":
        vid = msg.get("villager")
        text = (msg.get("text") or "").strip()
        if not vid or vid not in ALL_VILLAGERS:
            await ws.send_json({"type": "error", "message": f"unknown villager '{vid}'"})
            return
        if not text:
            return
        villager = get_villager(vid)
        conv_id = active.get(vid)
        if conv_id is None:
            conv_id = engine.begin(villager)
            active[vid] = conv_id

        async for chunk in engine.respond_streaming(villager, conv_id, text):
            await ws.send_json({
                "type": "reply_chunk",
                "villager": vid,
                "text": chunk,
            })
        await ws.send_json({"type": "reply_end", "villager": vid})
        return

    if msg_type == "gift":
        vid = msg.get("villager")
        item = (msg.get("item") or "").strip()
        if not vid or vid not in ALL_VILLAGERS:
            await ws.send_json({"type": "error", "message": f"unknown villager '{vid}'"})
            return
        if not item:
            await ws.send_json({"type": "error", "message": "gift requires an item"})
            return
        villager = get_villager(vid)
        await default_bus.emit(EVT_PLAYER_GAVE_GIFT, villager_id=vid, item=item)
        conv_id = active.get(vid)

        async for chunk in engine.record_gift(villager, conv_id, item):
            await ws.send_json({
                "type": "reply_chunk",
                "villager": vid,
                "text": chunk,
            })
        await ws.send_json({"type": "reply_end", "villager": vid})
        # link the conversation back in case engine.record_gift created one
        if vid not in active:
            # we can't easily fish the id back out; safe to leave as-is — the
            # next 'say' will rebegin if needed
            pass
        return

    if msg_type == "end":
        vid = msg.get("villager")
        if vid in active:
            conv_id = active.pop(vid)
            villager = get_villager(vid)
            summary = await engine.end(villager, conv_id)
            if summary:
                await ws.send_json({
                    "type": "summary",
                    "villager": vid,
                    "text": summary,
                })
        return

    if msg_type == "set_name":
        name = (msg.get("name") or "").strip()
        if name:
            memory_store.set_player_name(name)
            await default_bus.emit(EVT_PLAYER_SET_NAME, name=name)
            await ws.send_json({"type": "name_set", "name": name})
        return

    await ws.send_json({"type": "error", "message": f"unknown message type '{msg_type}'"})


# --- entrypoint --------------------------------------------------------------

def main():
    import uvicorn
    port = int(os.environ.get("PORT", "8765"))
    uvicorn.run("server.api.server:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
