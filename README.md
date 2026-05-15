# Heather's Hollow

> *A cozy village where every character remembers, grows, and surprises you.*

## Vision

Heather's Hollow is what happens when Animal Crossing meets persistent AI. The villagers aren't scripted — they're powered by Claude. They remember every conversation you've ever had, form their own opinions about you and each other, develop hobbies, hold grudges, fall in love, and slowly become someone you actually know.

A pumpkin you gave Margot last autumn might come up in conversation next spring. The grumpy shopkeeper might soften after you visit on his birthday three years in a row. The village won't reset. It will *grow*.

## Tech Stack

- **Game engine:** Godot 4 (GDScript) — long-term client; a Three.js web demo is the current vertical slice
- **AI server:** Python (FastAPI)
- **Character intelligence:** the [`claude` CLI](https://claude.com/claude-code) (Claude Code) — each villager turn shells out to `claude --print`, so conversations use your Claude subscription rather than a metered API key
- **Real-time link:** WebSocket between client and AI server

## Art Direction

Cottagecore kawaii — soft pastels, rounded forms, handcrafted textures, floral motifs, the warmth of ceramic and linen. Inspired by Animal Crossing, Neko Atsume, Bamboletta dolls, and old porcelain dishware. Every surface should feel like it was made by someone who loved making it.

See [`docs/ART_DIRECTION.md`](docs/ART_DIRECTION.md) for the full style guide.

## Platform

- **Primary:** Desktop and browser, with Bluetooth controller support (Switch Pro target)
- **Future:** Mobile companion app where villagers can "text" you about what's happening back in the hollow while you're away

## Status

Early development. A playable browser-based vertical slice exists — see "Running the demo" below.

## Running the demo

The demo is a Three.js web client talking to a Python AI server over WebSocket. The Godot client comes later — same backend.

**One-time setup:**

```bash
python3 -m pip install -r requirements.txt

# The `claude` CLI must be installed and on your PATH for the villagers to
# actually think. Without it, the server still boots and the village still
# renders — villagers just give a canned in-character placeholder.
# Install: https://claude.com/claude-code
which claude   # should print a path, e.g. /Users/you/.local/bin/claude
```

No API key needed — `claude` uses your existing Claude subscription via the
CLI's built-in OAuth / keychain auth.

**Two terminals:**

```bash
# terminal 1 — the AI server (port 8765)
python3 -m uvicorn server.api.server:app --host 127.0.0.1 --port 8765

# terminal 2 — a tiny static server for the web client (port 8000)
cd game/web && python3 -m http.server 8000
```

Then open `http://localhost:8000` in a browser. WASD to move, mouse-drag to look, walk up to a villager and press `E` to talk. Switch Pro controller works over Bluetooth via the Gamepad API.

SQLite memory persists at `server/data/hollow.db` — delete it to reset all villager relationships.

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
