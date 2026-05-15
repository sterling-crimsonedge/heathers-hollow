# Heather's Hollow

> *A cozy village where every character remembers, grows, and surprises you.*

## Vision

Heather's Hollow is what happens when Animal Crossing meets persistent AI. The villagers aren't scripted — they're powered by Claude. They remember every conversation you've ever had, form their own opinions about you and each other, develop hobbies, hold grudges, fall in love, and slowly become someone you actually know.

A pumpkin you gave Margot last autumn might come up in conversation next spring. The grumpy shopkeeper might soften after you visit on his birthday three years in a row. The village won't reset. It will *grow*.

## Tech Stack

- **Game engine:** Godot 4 (GDScript)
- **AI server:** Python
- **Character intelligence:** Claude API
- **Real-time link:** WebSocket between client and AI server

## Art Direction

Cottagecore kawaii — soft pastels, rounded forms, handcrafted textures, floral motifs, the warmth of ceramic and linen. Inspired by Animal Crossing, Neko Atsume, Bamboletta dolls, and old porcelain dishware. Every surface should feel like it was made by someone who loved making it.

See [`docs/ART_DIRECTION.md`](docs/ART_DIRECTION.md) for the full style guide.

## Platform

- **Primary:** Desktop and browser, with Bluetooth controller support (Switch Pro target)
- **Future:** Mobile companion app where villagers can "text" you about what's happening back in the hollow while you're away

## Status

Early development. Currently scaffolding the project and shaping the design.

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
