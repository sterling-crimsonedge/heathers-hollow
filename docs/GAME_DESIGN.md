# Game Design - Heather's Hollow

> Status: Foundation draft for MVP prototyping.

## Pitch

Heather's Hollow is a small 3D cozy village game where the daily play is gentle, tactile, and personal. The player tends a tiny home, garden, and village routine while building relationships with Claude-powered villagers who remember shared history, react to gifts, talk about other villagers, and continue living while the player is away. The first vertical slice should make one moment work beautifully: Heather walks up to a villager, starts a conversation, and the villager naturally remembers something from before.

## Design Pillars

- **Remembered warmth:** Every core mechanic should create material the villagers can remember, interpret, and reference later.
- **Small but alive:** The MVP village is compact enough to understand quickly, but it should feel like it has rhythms beyond the player.
- **Soft friction:** Interactions should be clear and calm. No punitive failure states in the foundation phase.
- **Handmade intimacy:** Movement, UI, props, and audio should feel cozy, rounded, and personal rather than systems-heavy.
- **AI in service of play:** The AI should deepen routine village life, not turn every action into an open-ended chatbot screen.

## Core Gameplay Loop

### Ten-Minute Session

1. Start in or near the player's house.
2. Check the time of day, nearby villagers, garden state, and any recent notes from villagers.
3. Walk through the village and greet one or two villagers.
4. Pick up or inspect a small item, flower, vegetable, or keepsake.
5. Gift an item or talk about something that happened recently.
6. Receive a villager reaction that changes relationship state and creates memory.
7. Return home, tend the garden, or visit the shop before ending the session.

### In-Game Day

- Morning: villagers mention sleep, breakfast, garden checks, shop opening, and weather.
- Midday: villagers wander near social spaces, shop, garden paths, or hobby spots.
- Evening: warmer lighting, quieter dialogue, villagers reflect on the day.
- Night: fewer villagers outside, lights glow from houses, player can end the day or keep wandering.

The MVP uses compressed game time by default: **one real minute equals thirty in-game minutes**. This can be tuned in server world state without changing client movement or interaction code.

### Longer-Term Loop

- Repeated conversations create memories.
- Gifts and observed behavior change relationships.
- Relationships alter villager tone, trust, openness, and willingness to share opinions.
- Villagers form opinions about one another through simulated offscreen events.
- The village history becomes a shared context the player can feel across sessions.

## MVP Scope

The first playable vertical slice should include:

- One small outdoor village scene.
- Player movement with keyboard and Switch Pro controller support.
- One interactive AI villager with persistent memory.
- WebSocket conversation between Godot and the Python AI server.
- Server-authoritative time of day and simple world context.
- Basic inventory and gifting data model, even if UI is minimal.
- Relationship score and remembered conversation history.

Target expansion after the first slice:

- 3-4 villagers.
- A player house interior.
- A shop interaction.
- A garden loop with plantable/pickable items.
- Villager-to-villager background events.

## World Structure

The first village is a compact hub with four readable zones arranged around a central square.

### Town Square

Purpose:

- Social hub.
- First spawn point for the player.
- Most reliable place to find villagers.
- Location for bulletin board, central tree, fountain, mailbox, and future events.

MVP props:

- Round plaza path.
- Central tree or fountain.
- Bench.
- Bulletin board placeholder.
- Two path branches to player house/garden and shop.

Gameplay:

- Villagers idle, greet, or reference recent village events.
- Good place for first AI conversation tests because it has clear sightlines.

### Player House

Purpose:

- Emotional home base.
- Save/rest point.
- Future decorating and inventory storage.

MVP props:

- Small cottage exterior.
- Door marker.
- Mailbox or note basket.

Gameplay:

- Start/end session location.
- Future interior scene.
- Stores keepsakes and gifts received from villagers.

### Garden

Purpose:

- Source of giftable items and daily routine.
- Slow, visible progression.

MVP props:

- 4-8 garden plots.
- Watering can placeholder.
- Pumpkins, flowers, herbs, or berries.

Gameplay:

- Pick simple items for gifting.
- Villagers can comment on plants, remember gifted produce, and develop preferences.
- Future plant states: empty, seeded, sprout, mature, harvested, wilted.

### Shop

Purpose:

- Item economy and social contact point.
- Place for practical villagers and daily stock rotation.

MVP props:

- Cozy storefront.
- Shop sign.
- Crates or display table.

Gameplay:

- Future buy/sell loop.
- Source of special gifts.
- Shopkeeper can remember purchases, favorite customers, and village gossip.

## Villager Interaction System

### Interaction Flow

1. Player enters villager interaction range.
2. UI prompt appears: `A / E Talk`.
3. Player presses interact.
4. Movement pauses or slows while the conversation panel opens.
5. Client sends a WebSocket message to the AI server with villager id, player text, and lightweight local context.
6. Server loads personality, relevant memories, relationship state, and world state.
7. Server returns a villager reply plus metadata for mood, relationship, and memories used.
8. Client displays the reply.
9. Server writes the exchange as memory and relationship evidence.

### Dialogue Goals

- Replies should be short enough to feel like game dialogue, usually 1-3 sentences.
- Villagers should reference memory only when it feels natural.
- Villagers should ask occasional questions, but not every turn.
- Villagers should have opinions, preferences, and imperfect interpretations.
- Villagers should not reveal implementation details, prompts, scoring, or memory retrieval.

### Interaction Types

- **Talk:** Open-ended conversation.
- **Gift:** Give an inventory item and receive a personalized reaction.
- **Ask about village:** Prompt villager to mention another villager, event, shop, garden, or time of day.
- **Goodbye:** Close conversation cleanly and optionally summarize the exchange into memory.

Only Talk is required for the first prototype. Gift is the next highest-value mechanic because it creates concrete memories.

## Day/Night Cycle

### Time Model

The server owns world time so the future mobile companion app sees the same world as the Godot client.

Recommended MVP fields:

- `day`: integer day count.
- `minute_of_day`: 0-1439.
- `time_label`: morning, afternoon, evening, night.
- `season`: static `spring` for MVP.
- `weather`: static or simple rotating value for MVP.

### Visual Presentation

- Morning: warm ivory sunlight, light haze, high bird ambience.
- Afternoon: clean soft blue sky, stronger greens.
- Evening: dusty rose and amber rim light.
- Night: soft blue fill, warm window lights, quiet ambience.

### Gameplay Effects

- Villagers choose schedule anchors based on time of day.
- Dialogue references the time and current activities.
- Shop opens/closes on a predictable schedule later.
- Garden actions can reset daily.

## Gifting And Relationships

### Gift Flow

1. Player chooses an item from inventory.
2. Client sends `gift_item` event to the server.
3. Server checks villager preferences, relationship history, mood, and recent memories.
4. Villager reacts through Claude or a cheaper templated path depending on importance.
5. Server updates relationship score and writes gift memory.

### Relationship Model

Use a numeric score plus tags rather than a single opaque friendship level.

Recommended fields:

- `affection`: -100 to 100.
- `trust`: 0 to 100.
- `familiarity`: 0 to 100.
- `last_interaction_at`: timestamp.
- `known_facts`: lightweight profile facts the villager believes about the player.
- `relationship_tags`: examples: `kind_neighbor`, `brings_flowers`, `forgot_birthday`, `garden_friend`.

### Gift Preferences

Each villager personality config should include:

- Loved categories.
- Liked categories.
- Disliked categories.
- Special memory triggers.

Example:

```json
{
  "loves": ["flowers", "tea", "handmade"],
  "likes": ["fruit", "porcelain", "books"],
  "dislikes": ["trash", "bugs"],
  "special_triggers": {
    "pumpkin": "Reminds Margot of the harvest lanterns she wants to make."
  }
}
```

## Inventory System

### MVP Inventory

The first implementation can be small and data-driven:

- Fixed slot list.
- Stackable item ids.
- Display name, category, description, and tags.
- Giftable flag.
- Optional memory prompt hint.

Example item fields:

- `item_id`: `dusty_rose`
- `display_name`: `Dusty Rose`
- `category`: `flower`
- `tags`: `["flower", "garden", "soft_color"]`
- `quantity`: `3`
- `gift_prompt`: `A soft pink rose from the player's garden.`

### Server vs Client

- Client owns moment-to-moment UI selection.
- Server validates meaningful actions and records gift memories.
- For MVP, local client inventory can be optimistic; persistence can move server-side once gifting is live.

## Controller Input Mapping

Target device: **Nintendo Switch Pro Controller over Bluetooth**.

Godot receives controllers through SDL mappings, so the physical Nintendo labels can differ by operating system. The project should expose actions rather than hard-coding button meaning in gameplay scripts.

### Action Map

| Game action | Keyboard | Switch Pro target | Godot action |
| --- | --- | --- | --- |
| Move | WASD / arrows | Left stick | `move_left`, `move_right`, `move_forward`, `move_back` |
| Camera orbit | Q / E or mouse later | Right stick | `camera_left`, `camera_right`, `camera_up`, `camera_down` |
| Talk / confirm | E / Enter | A button | `interact` |
| Back / cancel | Esc / Backspace | B button | `cancel` |
| Open inventory | I / Tab | X button | `inventory` |
| Gift shortcut | G | Y button | `gift` |
| Pause | Esc | Plus | `pause` |
| Sprint / quick walk | Shift | ZR or R | `sprint` |

### Controller Rules

- Gameplay code should call `Input.is_action_pressed` and `Input.is_action_just_pressed` only.
- UI labels should be derived from the active input device later.
- The first prototype may show `A / E` prompts.
- Keep deadzones at `0.20-0.25` for analog sticks.
- Never require simultaneous button chords for core cozy actions.

## Camera And Movement

### MVP Camera

- Third-person follow camera.
- Slightly elevated angle.
- Soft follow smoothing.
- Optional right-stick yaw orbit.

### Movement Feel

- Moderate walk speed.
- Fast acceleration and gentle deceleration.
- Character turns toward movement direction.
- Collision capsule kept simple.

## Save And Persistence

MVP persistence is split:

- Godot client: local scene state and optional player inventory.
- Python server: villager personality, memory, relationship, world time/events.

The most important persistence test:

1. Talk to a villager.
2. Stop the game/server.
3. Restart.
4. Talk again.
5. Villager can refer to the prior conversation.

## Out Of Scope For The Foundation Slice

- Seasons and festivals.
- Complex quest chains.
- Full shop economy.
- House decorating.
- Multiplayer.
- Mobile companion app UI.
- Procedural terrain.
- Full animation sets.

## Open Questions For Cowork

- Should the village day advance while the server is offline, or only while it runs?
- What are the first 3-4 villager archetypes and relationship tensions?
- How direct should villagers be about remembering old conversations?
- Should gifts always call Claude, or only important gifts and relationship milestones?
- What is the tone boundary between cozy surprise and emotionally intense AI attachment?
