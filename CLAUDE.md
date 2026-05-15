# Heather's Hollow — Context for Claude Code

## What this is

A personal project: a cozy 3D village game being built as a gift for Heather (Sterling's partner). The working title is the project name.

## What makes it different

The unique differentiator is **AI-powered characters with persistent memory.** Villagers are not scripted NPCs — they're driven by Claude. Each one has a persistent personality, remembers every conversation across sessions, forms opinions, evolves over time, and reacts to world events. The game's appeal lives or dies on whether those characters feel real.

When implementing villager-facing features, the default question is: *"does this make the villagers feel more like people?"* If a shortcut would compromise that, flag it.

## Art direction

Cottagecore kawaii. Inspired by Animal Crossing, Neko Atsume, Bamboletta dolls, and porcelain dishware. Soft pastels, rounded forms, handcrafted textures, floral motifs, ceramic and linen warmth. See `docs/ART_DIRECTION.md` for the full guide as it develops.

## Tech stack

- **Engine:** Godot 4 with GDScript (long-term target). A Three.js web demo (`game/web/`) is the current vertical slice — same WebSocket protocol, runs anywhere with a browser.
- **AI backend:** Python (FastAPI) server. Villager conversations are powered by the **Claude Code CLI** — `server/ai/conversation.py` shells out to `claude --print` per turn, so the game uses Sterling's Claude subscription rather than the metered Anthropic API. There is no `ANTHROPIC_API_KEY` dependency; auth is handled by the CLI.
- **Transport:** WebSocket between game client and AI server (REST for state queries).
- **Controller:** Switch Pro controller over Bluetooth (browser Gamepad API; native in Godot).

### Why the CLI, not the SDK

We don't use the `anthropic` Python SDK. Each villager turn calls `claude --print --system-prompt <persona+context> --tools "" "<player message>"`. `--tools ""` strips tool access (villagers just talk), and `--system-prompt` REPLACES the default — which means project context (this CLAUDE.md, hooks, agents) does NOT leak into Maple's head. If you're editing `conversation.py`, preserve those two flags.

## MVP scope

The first milestone is a small, complete vertical slice:

- A small village: town square, player's house, garden, shop
- 3–4 AI villagers, each with a distinct personality
- Day/night cycle
- Basic interaction (talk, gift) and a working memory loop

Resist scope creep beyond this until the MVP feels good. Seasons, weather, festivals, romance arcs, and the mobile app all come later.

## Future direction

A mobile companion app where villagers "text" the player about events back home while they're away from the game. The AI server should be designed with this in mind — conversation and event systems should not assume the game client is the only consumer.

## Repo layout

```
game/      Godot 4 client
server/    Python AI server (ai/, world/, api/)
mobile/    Future companion app (placeholder)
docs/      Design docs (GAME_DESIGN, AI_ARCHITECTURE, ART_DIRECTION)
```

## Conventions

- The game and server are separate concerns — keep the client thin on character logic, fat on presentation. Personality and memory live on the server.
- World state (time, weather, events) is authoritative on the server so the future mobile app can share it.
- Prefer iterating on one villager deeply over adding more shallow ones.
