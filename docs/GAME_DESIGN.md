# Game Design — Heather's Hollow

## Pitch

You wake up in a small village tucked into a sun-warmed valley. The neighbors know your name. They remember the pumpkin you gave them last autumn, the rainy afternoon you sheltered under the shop awning together, the song you both hummed without realizing it. Heather's Hollow is a cozy life sim where the villagers are not scripted — they are real personalities, powered by Claude, who remember every conversation and grow alongside you. You wander, you tend a garden, you chat, you give small gifts. The village quietly becomes a place you know.

## Core loop

### A 10-minute session
1. Open the game; arrive in the town square at the current time of day.
2. Check in on 1–2 villagers — say hello, hear what's on their mind today.
3. Wander to the garden, pick a flower or vegetable.
4. Give the flower to a villager who'd appreciate it; watch their reaction.
5. Close the game — the villager remembers.

### A day
- Morning: villagers are out (Maple tending her flower bed, Clover skipping around).
- Midday: shop is open, Bramble is reading on his bench.
- Evening: Sage is on the hill watching the sunset.
- Night: lanterns light the path; one or two night-owl villagers linger in the square.

### A week
- Relationships shift. A villager you've gifted multiple times starts saving you a seat. A villager you ignored grows distant.
- Villagers reference past conversations spontaneously: *"You know, I keep thinking about what you said about your mother."*
- Small village events (the seasonal market, a quiet birthday) emerge from the world state.

## World layout (MVP)

A compact, walkable village. No fast travel needed — you can cross it in 60 seconds.

```
                    ╔════════════════╗
                    ║   Sage's Hill  ║   (overlook, evening spot)
                    ╚════════╤═══════╝
                             │
                       ┌─────┴──────┐
                       │ Town Square│ ← fountain, benches, bulletin board
                       │  (center)  │
                       └─┬────┬───┬─┘
                         │    │   │
              ┌──────────┘    │   └──────────┐
              │               │              │
       ╔══════╧═════╗   ╔═════╧═════╗   ╔════╧═══════╗
       ║  Garden    ║   ║  The Shop ║   ║ Your House ║
       ║ (Maple's)  ║   ║ (Bramble) ║   ║            ║
       ╚════════════╝   ╚═══════════╝   ╚════════════╝
```

- **Town square** — fountain at center, benches, bulletin board for village news. Default gathering point.
- **Player's house** — small cottage, your save/sleep point. Interior is one room.
- **Garden** — Maple's domain. Flower beds, vegetable rows. Player can pick produce here.
- **Shop** — Bramble's shop. Sells seeds, tools, small gifts. Open 10:00–18:00.
- **Sage's Hill** — slight rise on the edge of town with a single old tree and a bench. Sage is here most evenings.
- **Path & treeline** — cottagecore landscaping connecting the four corners. A clovered field where Clover plays.

## Villagers (MVP cast — 4)

| Name   | Role             | Vibe                                              |
|--------|------------------|---------------------------------------------------|
| Maple  | Gardener         | Cheerful, optimistic, loves flowers and weather.  |
| Bramble| Shopkeeper       | Grumpy bookworm, dry humor, secretly cares deeply.|
| Clover | Energetic youth  | Curious, asks questions, infectious enthusiasm.   |
| Sage   | Wise elder       | Gentle metaphors, long memory, quiet warmth.      |

Full personality details in [AI_ARCHITECTURE.md](AI_ARCHITECTURE.md).

## Villager interaction

### Approach & talk
- Walk within ~2m of a villager → a small prompt appears (`[E] Talk to Maple`).
- Press the interact button → camera eases, chat UI fades in.
- Player types a message (keyboard) or selects from suggested openers (controller).
- Villager responds. Conversation continues until player exits.
- Exiting closes the chat UI; the villager waves or returns to their idle behavior.

### Gifting
- Open inventory while in conversation → select an item → confirm gift.
- Villager's reaction depends on:
  - Their personality (Maple loves flowers; Bramble appreciates books)
  - Their current mood
  - Memory of past gifts (giving the same thing every time gets less excited)
  - The world state (a warm blanket lands differently in winter)
- Reaction is dialogue + a small mood/relationship shift, persisted to memory.

### Idle observation
- You don't have to talk. Sitting on a bench near villagers is itself a thing you can do.
- Villagers occasionally chat with each other; if you're nearby you overhear a snippet.

## Day/night cycle

- **Real time, accelerated.** 1 in-game day = 1 real hour by default (configurable).
- **Time of day affects:**
  - Lighting (warm dawn, bright midday, golden hour, blue dusk, lantern-lit night)
  - Which villagers are where
  - What villagers talk about ("you're up early!" / "couldn't sleep?")
  - Mood baselines (Bramble grumpier in the morning, Sage gentler at night)
- **Sleeping** at the player's house skips to the next dawn.

## Inventory

Lightweight. Capacity ~20 slots in MVP.

- **Categories:** flowers, vegetables, books, trinkets, food
- **Per-item:** name, sprite, short description, optional "memory tag" (e.g. *"first pumpkin of the season"*)
- **Acquired by:** picking from garden, buying at shop, finding around the village, occasional gifts from villagers

Inventory is opened with `Y` (controller) or `Tab` (keyboard). A simple grid UI overlays the screen.

## Controls

### Keyboard + Mouse (primary for demo)
| Action          | Key                  |
|-----------------|----------------------|
| Move            | WASD / Arrow keys    |
| Camera          | Mouse look           |
| Interact / Talk | E or Space           |
| Inventory       | Tab                  |
| Sleep / Menu    | Esc                  |
| Send chat       | Enter                |
| Exit chat       | Esc                  |

### Switch Pro Controller (via Gamepad API)
| Action          | Button               |
|-----------------|----------------------|
| Move            | Left stick           |
| Camera          | Right stick          |
| Interact / Talk | A (east button)      |
| Cancel / Back   | B (south button)     |
| Inventory       | Y (north button)     |
| Quick gift      | X (west button)      |
| Menu            | + (plus)             |
| Map             | – (minus)            |
| Run             | ZL (hold)            |
| Camera recenter | R3 (right stick click)|

The Switch Pro controller maps cleanly through the browser Gamepad API. Buttons 0/1/2/3 are B/A/Y/X (Nintendo layout), axes 0/1 are left stick, axes 2/3 are right stick.

## Saving

- **Auto-save** on sleep, on closing chat, on quitting.
- **Save data lives on the server** (SQLite), not the client. This is intentional — the mobile companion app needs to read the same state.
- The client carries no character knowledge; it asks the server who's around, what they're doing, and what they remember.

## Out of scope for MVP

- Seasons & weather (placeholder: time-of-day only)
- Festivals / scheduled events
- Romance arcs
- Crafting & farming progression
- Multiplayer / village visiting
- Mobile companion app (architecture supports it; UI comes later)
- Combat (there is none; this is a peaceful game)

## Design pillars

1. **Villagers are people, not menus.** If a feature compromises how real they feel, cut the feature.
2. **Cozy over compelling.** No timers, no failure states, no FOMO. The game waits for you.
3. **Small and deep.** Four villagers you truly know beats forty you don't.
4. **Quiet emergence.** Most of the magic is the villager remembering something you forgot you told them.

## Open questions

- Item economy: do you pay for things, or is the shop barter-based?
- Should villagers age over real time, or only in-game time?
- How visible should mood/relationship be in UI? (Lean: invisible — let dialogue carry it.)
- Snippet overhearing — fully Claude-generated, or templated with personality slots?
