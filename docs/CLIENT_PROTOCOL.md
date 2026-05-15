# Heather's Hollow Client Protocol

This is the canonical client/server contract for Heather's Hollow. Godot, the browser demo, and future companion clients should use this root server protocol.

Do not treat the Claude worktree browser protocol as canonical. Its `begin` / `say` / `gift` / `end` streaming messages are legacy reference material only.

## Server

Run the root FastAPI server on port `8765`:

```bash
uv run --python 3.12 --with-requirements server/requirements.txt uvicorn server.api.server:app --host 127.0.0.1 --port 8765
```

Primary base URLs:

- HTTP: `http://127.0.0.1:8765`
- WebSocket: `ws://127.0.0.1:8765/ws/conversation`
- WebSocket alias: `ws://127.0.0.1:8765/ws`

## Startup Reads

Clients should initialize from `GET /client/bootstrap`:

```text
GET /client/bootstrap?client_id=godot_client&player_id=heather&notification_limit=5
```

The response includes:

- `world`: current day, clock, season, weather, and demo day length.
- `villagers`: public villager summaries.
- `inventory`: public starter gift items for the selected player id.
- `notifications`: read-only inbox payload for the supplied client id.

Clients should fetch per-villager UI context lazily when an interaction opens:

```text
GET /client/villagers/{villager_id}/context?subject_id=heather&memory_limit=5&event_limit=5
```

The response includes public `villager`, `relationship`, `memories`, `events`, and `world` data. It must not include system prompts, private goals, raw player text, or raw private metadata.

## WebSocket Messages

On connect, the server sends:

```json
{
  "type": "server_status",
  "message": "Heather's Hollow AI server connected.",
  "world": {}
}
```

### Player Message

Client sends:

```json
{
  "type": "player_message",
  "player_id": "heather",
  "villager_id": "margot",
  "text": "Do you remember the teacup I told you about?",
  "context": {
    "location": "town_square",
    "client_time": "morning",
    "world": {
      "day": 1,
      "clock": "08:00",
      "time_label": "morning",
      "season": "spring",
      "weather": "clear"
    }
  }
}
```

Server replies:

```json
{
  "type": "villager_reply",
  "villager_id": "margot",
  "display_name": "Margot",
  "text": "I do remember...",
  "mood": "warm",
  "relationship": {},
  "memories_used": [1, 2],
  "memory_id": 3,
  "world": {}
}
```

### Gift Item

Client sends the public item payload from `/client/inventory` when available:

```json
{
  "type": "gift_item",
  "player_id": "heather",
  "villager_id": "margot",
  "item": {
    "item_id": "dusty_rose",
    "display_name": "Dusty Rose"
  },
  "context": {
    "location": "town_square",
    "gift_source": "starter_inventory"
  }
}
```

Server replies with the same `villager_reply` shape. `memories_used` may include the new gift memory id.

## Legacy Worktree Protocol

The Claude worktree browser demo used these client message types:

- `hello`
- `begin`
- `say`
- `gift`
- `end`
- `set_name`

Those messages are not accepted by the root server and should not be reintroduced during consolidation. When promoting the browser demo into root `game/web/`, translate its networking layer to `player_message` and `gift_item` instead of adding compatibility for the legacy protocol.

## Integration Rules

- Add server behavior before client behavior.
- Keep root `server/` as the single source of truth.
- Keep `.claude/worktrees/` reference-only.
- Prefer `/client/bootstrap` over hardcoded villager lists.
- Prefer `/client/inventory` item payloads over string gift names.
- Use `memories_used`, `memory_id`, `/memories/{id}`, and `/conversations/{id}/turns` for explainability UI without exposing private metadata.
