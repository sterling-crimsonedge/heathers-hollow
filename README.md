# Heather's Hollow

> *A cozy village where every character remembers, grows, and surprises you.*

## Vision

Heather's Hollow is what happens when Animal Crossing meets persistent AI. The villagers aren't scripted — they're powered by Claude. They remember every conversation you've ever had, form their own opinions about you and each other, develop hobbies, hold grudges, fall in love, and slowly become someone you actually know.

A pumpkin you gave Margot last autumn might come up in conversation next spring. The grumpy shopkeeper might soften after you visit on his birthday three years in a row. The village won't reset. It will *grow*.

## Tech Stack

- **Game engine:** Godot 4 (GDScript)
- **AI server:** Python
- **Character intelligence:** Pluggable LLM provider, with Anthropic Claude, local Ollama, and deterministic fallback paths
- **Real-time link:** WebSocket between client and AI server

## Art Direction

Cottagecore kawaii — soft pastels, rounded forms, handcrafted textures, floral motifs, the warmth of ceramic and linen. Inspired by Animal Crossing, Neko Atsume, Bamboletta dolls, and old porcelain dishware. Every surface should feel like it was made by someone who loved making it.

See [`docs/ART_DIRECTION.md`](docs/ART_DIRECTION.md) for the full style guide.

## Platform

- **Primary:** Desktop and browser, with Bluetooth controller support (Switch Pro target)
- **Future:** Mobile companion app where villagers can "text" you about what's happening back in the hollow while you're away

## Status

Foundation prototype. The repo now contains detailed design docs, a Godot 4 starter scene, and a Python AI server scaffold with SQLite memory.

## Project Layout

```
game/      Godot 4 client — scenes, scripts, art, shaders
server/    Python AI server — personality, memory, conversation, world state
mobile/    Future companion app
docs/      Design documents
```

## Docs

- [`docs/GAME_DESIGN.md`](docs/GAME_DESIGN.md) — gameplay loop, mechanics, MVP scope
- [`docs/AI_ARCHITECTURE.md`](docs/AI_ARCHITECTURE.md) — how the villagers think and remember
- [`docs/ART_DIRECTION.md`](docs/ART_DIRECTION.md) — visual style guide
- [`docs/CLIENT_PROTOCOL.md`](docs/CLIENT_PROTOCOL.md) — canonical HTTP/WebSocket contract for Godot, browser, and companion clients
- [`docs/CONSOLIDATION_PLAN.md`](docs/CONSOLIDATION_PLAN.md) — source-of-truth plan for reconciling the Godot, browser demo, and server divergence

## Run the Prototype

### Prerequisites

- Python 3.12 or 3.13. The current smoke tests have been run with Python 3.12 through `uv`.
- Godot 4.x for the client. If `godot` or `godot4` is not on your shell path, open the `game/` folder from the Godot app.
- Optional: a live LLM provider. Use local Ollama for no-key prototyping, Anthropic Claude when `ANTHROPIC_API_KEY` is available, or deterministic fallback mode for tests.

### AI server

From the repo root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r server/requirements.txt
uvicorn server.api.server:app --reload --host 127.0.0.1 --port 8765
```

Or, without creating a persistent virtualenv:

```bash
uv run --python 3.12 --with-requirements server/requirements.txt uvicorn server.api.server:app --host 127.0.0.1 --port 8765
```

Optional Claude configuration:

```bash
export HOLLOW_LLM_PROVIDER=anthropic
export ANTHROPIC_API_KEY="your-key"
export ANTHROPIC_MODEL="claude-sonnet-4-5"
```

Optional local Ollama configuration:

```bash
ollama pull llama3.2
export HOLLOW_LLM_PROVIDER=ollama
export OLLAMA_BASE_URL="http://127.0.0.1:11434"
export OLLAMA_MODEL="llama3.2"
uvicorn server.api.server:app --reload --host 127.0.0.1 --port 8765
```

Provider selection uses `HOLLOW_LLM_PROVIDER=fallback|ollama|anthropic|auto`. `auto` tries Anthropic when `ANTHROPIC_API_KEY` is present and tries Ollama when `OLLAMA_BASE_URL` or `OLLAMA_MODEL` is explicitly set; otherwise it uses the deterministic fallback. If Ollama is unavailable, slow, or returns an invalid response, the server keeps the conversation playable by returning the in-character fallback. Godot connects to `ws://127.0.0.1:8765/ws/conversation`; `/ws` is also available as a shorter alias for tests and companion clients.

The canonical client contract is documented in [`docs/CLIENT_PROTOCOL.md`](docs/CLIENT_PROTOCOL.md). During consolidation, new clients must use root `player_message` and `gift_item` WebSocket payloads; the Claude worktree `begin` / `say` / `gift` streaming protocol is legacy reference-only.

Read-only server endpoints:

- `GET /health` confirms server status and returns a compact world/villager summary.
- `GET /client/bootstrap?client_id=heather_mobile&player_id=heather&notification_limit=5` returns startup world state, public villagers with home locations, starter inventory, and pending notification inbox state in one payload.
- `GET /client/inventory?player_id=heather` returns the starter giftable item payloads a client can send through the `gift_item` WebSocket path.
- `GET /client/villagers/margot/context?subject_id=heather` returns one villager's public profile, relationship state, recent memories, and recent events for interaction UI.
- `GET /client/villagers/margot/social-context?limit=10` returns one villager's public relationships with other villagers plus recent villager-to-villager memories and events.
- `GET /world` returns authoritative server world time, season, weather, and demo day length.
- `GET /villagers` returns public villager summaries.
- `GET /villagers/{villager_id}` returns one public villager profile without system prompt or private goals.
- `GET /relationships?villager_id=margot&limit=50` returns persisted public relationship edges for social graph/debug views.
- `GET /relationships/{villager_id}/{subject_id}` returns a public relationship snapshot, seeded from config when no persisted row exists.
- `GET /memories/recent?villager_id=margot&subject_id=heather&limit=10` returns a public memory timeline with safe metadata.
- `GET /memories/{memory_id}` opens a specific persisted memory from a timeline, transcript, event payload, or memory-influence id.
- `GET /conversations/{conversation_id}/turns` returns ordered player/villager transcript turns with safe metadata.
- `GET /events/recent?kind=gift&target_id=margot&after_id=12&limit=10` returns persisted world events, optionally filtered by kind, actor, target, and newest processed event id for clients such as the future mobile companion.
- `GET /events/{event_id}` opens a specific persisted event from the feed or a notification.
- `GET /notifications/summary?target_id=margot&after_id=12` returns latest event id and unseen notification-worthy event count without fetching full notification bodies.
- `GET /notifications/recent?kind=gift&target_id=margot&after_id=12&limit=10` returns deterministic mobile-style notifications composed from recent persisted events, with the same optional filters and cursor as the event feed.
- `GET /notifications/inbox?client_id=heather_mobile&limit=10` returns notifications newer than that client's persisted cursor, plus the next cursor event id to acknowledge after processing.
- `GET /notifications/cursor?client_id=heather_mobile` returns a persisted companion-client notification cursor plus an unseen summary after that cursor.
- `POST /notifications/cursor?client_id=heather_mobile&last_event_id=12` advances that client cursor monotonically after a companion client processes notifications.
- `GET /notifications/{event_id}` opens the composed mobile-style notification payload for one persisted event.
- `POST /world/away-tick?actor_id=margot&target_id=fern` simulates one deterministic villager-to-villager background interaction for demos/dev.
- `POST /world/away-ticks?count=3&actor_id=margot&target_id=fern` runs a bounded batch of away interactions for demos/dev and future companion catch-up jobs.

Public memory, relationship, event, and notification metadata is allowlisted so debug/mobile clients get useful ids, moods, gift details, memory-influence ids, and away-interaction topics without exposing raw private metadata. Memory detail payloads use the same public shape and redaction as the recent memory timeline.

The `gift_item` WebSocket payload may include the full public item payload from `/client/inventory` or only a starter `item_id`; known starter ids are expanded from the server catalog before relationship, memory, and event records are written.

For faster visible sky/time changes during a demo, run the server with a five-minute day:

```bash
export HOLLOW_DAY_LENGTH_SECONDS=300
```

To pre-load a deterministic Margot memory/gift storyline into a demo database:

```bash
python -m server.tools.seed_demo_state --db-path server/data/demo.sqlite3 --away-ticks 1
HH_MEMORY_DB=server/data/demo.sqlite3 uvicorn server.api.server:app --host 127.0.0.1 --port 8765
```

### Godot client

Open the `game/` folder in Godot 4 and run the project. The main scene spawns a small village, a player character, and Margot, the first test villager. On startup it requests `/client/bootstrap` to cache public villager profiles, server world time/weather, pending notification count, and the starter inventory when the server is available; Margot keeps offline fallback labels, the world/news HUD keeps readable fallbacks, and the Gift Rose action falls back to the `dusty_rose` item id if the HTTP bootstrap is unavailable. Talk and gift messages include the cached world snapshot as client interaction context when available, with safe prototype fallbacks when the bootstrap request is offline. Opening dialogue also starts a non-blocking read of `/client/villagers/{villager_id}/context`, caches the public response, and shows a compact public bond/memory/event summary plus a clipped latest-memory teaser when available without changing the current talk and gift controls. When a reply uses persisted memories, Godot shows a compact `Remembered N things` cue from the safe `memories_used` id list without exposing memory text. After conversation or gift replies, Godot refreshes that public context again so the summary can catch up to newly written memories, events, and relationship changes.

Controls:

- Move: WASD, arrow keys, D-pad, or left stick.
- Talk: `E`, Enter, or the controller A button.
- Gift starter rose: `G` near Margot, or use the `Gift Rose` button in dialogue.
- Camera orbit: `Q` / `R` or right stick horizontal.
- Close dialogue: Esc, Backspace, or controller B button.

### Browser demo

The root browser demo lives in `game/web/` and uses the same canonical server contract as Godot. It replaces the temporary root `codex-demo.html` path; that older single-file prototype is archived at `docs/prototypes/codex-demo.html` for reference only.

With the AI server running on port 8765, serve the browser client:

```bash
python3 -m http.server 8000 -d game/web
```

Open `http://127.0.0.1:8000/`. The browser demo loads `/client/bootstrap`, fetches `/client/villagers/{villager_id}/context` when a villager is selected, sends `player_message` and `gift_item` WebSocket payloads, and shows a clear offline state if the root server is not available.

### Smoke tests

These tests do not require a Claude API key:

```bash
python3 game/tests/test_godot_project_static.py
python3 game/tests/test_web_demo_static.py
python -m server.tests.test_away_interactions
python -m server.tests.test_conversation_relationship
python -m server.tests.test_demo_storyline
python -m server.tests.test_demo_seed
python -m server.tests.test_gift_relationship
uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_live_demo_stack
python -m server.tests.test_memory_roundtrip
python -m server.tests.test_mobile_notifications
python -m server.tests.test_mood
python -m server.tests.test_ollama_provider
python -m server.tests.test_personality_configs
python -m server.tests.test_social_memory_conversation
python -m server.tests.test_world_state
uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract
uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server
```

The Godot static check verifies `res://` references, scene/script links, input action coverage, required node names, bootstrap wiring for inventory, villager profiles, world status, read-only notification summary, shared interaction context, dialogue-time villager context fetches, post-interaction context refreshes, the public dialogue context summary, the latest public memory teaser, and the reply memory-influence cue without launching the editor.

The web demo static check verifies `game/web/` exists, uses the canonical root protocol, avoids the legacy Claude worktree WebSocket messages, and documents the browser run path.

The away interaction test verifies a villager-to-villager background tick creates reciprocal memories, relationship changes, events, and notifications.

The conversation relationship test verifies a personal conversation updates relationship scores, memory metadata, conversation turns, and event logs consistently.

The demo storyline test verifies the full "Margot remembers" path across conversation, gift, relationships, memories, events, and mobile notifications.

The demo seed test verifies `server.tools.seed_demo_state` can pre-load that memory/gift storyline plus villager-to-villager away activity into a SQLite database.

The gift relationship test verifies loved and neutral gifts update relationship scores, memory metadata, mood, and event logs consistently.

The live demo stack test starts an isolated uvicorn server, drives `/ws`, then verifies the HTTP relationship, memory, event, notification, world, and villager endpoints.

The mobile notification test verifies persisted conversation and gift events compose into safe notification payloads.

The Ollama provider test verifies provider selection, the `/api/chat` payload, and fallback behavior without requiring Ollama to be installed.

The social memory conversation test verifies that asking a villager about another villager can use persisted villager-to-villager memories and relationship state.

The API contract test verifies `/health`, `/client/bootstrap`, `/client/inventory`, `/client/villagers/{villager_id}/context`, `/client/villagers/{villager_id}/social-context`, `/world`, `/world/away-tick`, `/world/away-ticks`, `/villagers`, `/villagers/{villager_id}`, `/relationships`, `/relationships/{villager_id}/{subject_id}`, `/memories/recent`, `/memories/{memory_id}`, `/conversations/{conversation_id}/turns`, filtered and cursor-based `/events/recent`, `/events/{event_id}`, `/notifications/summary`, filtered and cursor-based `/notifications/recent`, `/notifications/inbox`, `/notifications/cursor`, `/notifications/{event_id}`, the `/ws` and `/ws/conversation` WebSocket aliases, and structured errors for unknown payload types.

The personality config test loads every villager JSON and checks prompt safety, day-phase mood baselines, relationship seed ranges, and required voice/preference fields.

The WebSocket test starts an isolated temporary server and verifies that Margot remembers both a conversation fact and a Dusty Rose gift across separate WebSocket sessions.

## Troubleshooting

- **Godot says the AI server is unavailable:** start the server first and confirm `http://127.0.0.1:8765/health` returns JSON.
- **No live LLM replies:** set `HOLLOW_LLM_PROVIDER=ollama` with Ollama running locally, or set `HOLLOW_LLM_PROVIDER=anthropic` plus `ANTHROPIC_API_KEY`. Fallback mode is expected to be simpler and deterministic.
- **Smoke test cannot import `fastapi`, `uvicorn`, or `websockets`:** install `server/requirements.txt` in your active environment, or use the `uv run --with-requirements` command above.
- **Switch Pro controller buttons feel swapped:** Godot receives controller labels through OS/SDL mappings. Gameplay uses named input actions in `game/scripts/player_controller.gd`; adjust mappings there rather than changing gameplay code.
- **Godot binary missing in shell:** this is fine for now. Open the `game/` directory manually from Godot 4 and run `res://scenes/main.tscn`.
