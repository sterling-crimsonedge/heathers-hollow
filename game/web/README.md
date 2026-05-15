# Heather's Hollow Browser Demo

This is the root browser demo for consolidation work. It is a static client that consumes the canonical root FastAPI server contract documented in `docs/CLIENT_PROTOCOL.md`.

## Run

From the repo root, start the AI server:

```bash
uv run --python 3.12 --with-requirements server/requirements.txt uvicorn server.api.server:app --host 127.0.0.1 --port 8765
```

Then serve the web files:

```bash
python3 -m http.server 8000 -d game/web
```

Open:

```text
http://127.0.0.1:8000/
```

## Contract

- Startup uses `GET /client/bootstrap`.
- Villager context uses `GET /client/villagers/{villager_id}/context`.
- Conversation uses `ws://127.0.0.1:8765/ws/conversation`.
- Talking sends `player_message`.
- Gifting sends `gift_item` with the public item payload from bootstrap inventory.

The legacy Claude worktree `begin`, `say`, and `gift` WebSocket messages are intentionally not used here.

## Notes

- The demo remains useful when the server is offline: it shows a local village scene and clearly disables live conversations.
- The long-term primary client is still Godot. This browser client is a fast inspection surface for server memory, relationship, and conversation iteration.
