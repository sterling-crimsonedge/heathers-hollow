# AI Architecture — Heather's Hollow

## Goal

Villagers that feel like *people*. They remember, they grow, they surprise. Not chatbots in animal costumes.

The technical north star: a player who plays for a year should be able to ask Maple, *"Do you remember the first thing I ever gave you?"* — and Maple should remember.

## System overview

```
┌──────────────┐   WebSocket    ┌────────────────────────────────────┐
│ Game client  │ ─────────────► │  Python AI server (FastAPI)        │
│ (Three.js or │                │  ├─ Conversation engine             │
│  Godot)      │ ◄───────────── │  ├─ Memory store (SQLite)           │
└──────────────┘    streamed    │  ├─ Personality registry            │
                    responses   │  ├─ World state (time, weather)     │
                                │  ├─ Event bus                        │
                                │  └─ Claude API client                │
┌──────────────┐                │                                      │
│ Mobile app   │ ─── REST ────► │  Same server, different transport.   │
│ (future)     │ ◄── push ───── │  Villagers can "text" the player.    │
└──────────────┘                └────────────────────────────────────┘
```

The game client carries no character logic. It asks: *"who is here, what are they doing, what did they just say?"* The server is authoritative on personality, memory, mood, and world state.

## Personality

A villager is a `Personality` record with both static and dynamic fields.

### Static (the seed — never changes)

- **Name** — e.g. *Maple*
- **Archetype** — a one-line essence: *"a cheerful gardener who finds joy in small growing things"*
- **Core values** — 3–4 things they care about deeply (e.g. flowers, weather, neighbors)
- **Voice** — speech patterns, vocabulary tells, sentence length, signature expressions
- **Quirks** — small repeatable behaviors (Maple hums while she works, Bramble snorts when amused)
- **Backstory anchors** — 2–3 facts about their past they may reference

### Dynamic (drifts over time)

- **Mood** — current emotional state (see Mood section)
- **Energy** — how chatty / active they are right now
- **Relationship with player** — affection score (-100 to +100), trust score (0 to 100), familiarity (0 to 100, how well they know the player)
- **Relationships with other villagers** — same axes, per pair
- **Recent interests** — things they've been thinking about lately, populated by recent events
- **Drift notes** — small additions the system has made to their persona over time (*"has started keeping a journal since the player gifted her one"*)

### Prompt assembly

Every Claude call for a villager assembles a prompt with this structure:

```
[ system: cached personality block — static fields, rarely changes ]
[ system: villager's current dynamic state — mood, energy, relationships ]
[ system: world context — time of day, weather, who else is nearby, recent events ]
[ system: relevant memories — retrieved by salience for this conversation ]
[ conversation history — current session's turns ]
[ user: player's utterance ]
```

The static block is the largest and is the prime target for **prompt caching** (Anthropic API supports `cache_control` markers — we mark the personality block as ephemeral cached). This is the single biggest cost lever in the system.

## Memory

### What is a memory?

A **memory** is one of:

- **Utterance** — a thing the player or a villager said that was notable
- **Episode** — a higher-level summary of an interaction (*"the player gave Maple a sunflower on a rainy morning and she cried"*)
- **Fact** — something the villager learned about the player (*"player's mother lived in a coastal town"*)
- **Opinion** — a value judgment the villager has formed (*"player is thoughtful"*)
- **World event** — something that happened in the village that this villager witnessed (*"saw Bramble lose his temper at the shop"*)

### Schema

```sql
CREATE TABLE memories (
  id            INTEGER PRIMARY KEY,
  villager_id   TEXT NOT NULL,         -- which villager owns this memory
  kind          TEXT NOT NULL,         -- utterance | episode | fact | opinion | event
  content       TEXT NOT NULL,         -- the memory text itself
  participants  TEXT,                  -- JSON array: ['player', 'maple', ...]
  salience      REAL NOT NULL,         -- 0.0–1.0, how important this is
  emotional_valence REAL,              -- -1.0 to +1.0
  created_at    DATETIME NOT NULL,
  last_recalled DATETIME,              -- for decay / forgetting
  recall_count  INTEGER DEFAULT 0,
  embedding     BLOB,                  -- vector for semantic recall (optional MVP)
  tags          TEXT                   -- JSON array
);

CREATE TABLE relationships (
  villager_id   TEXT NOT NULL,
  target_id     TEXT NOT NULL,         -- 'player' or another villager
  affection     INTEGER DEFAULT 0,     -- -100..100
  trust         INTEGER DEFAULT 0,     -- 0..100
  familiarity   INTEGER DEFAULT 0,     -- 0..100
  updated_at    DATETIME NOT NULL,
  PRIMARY KEY (villager_id, target_id)
);

CREATE TABLE conversations (
  id            INTEGER PRIMARY KEY,
  villager_id   TEXT NOT NULL,
  player_id     TEXT NOT NULL,
  started_at    DATETIME NOT NULL,
  ended_at      DATETIME,
  summary       TEXT                   -- written at end of conversation
);

CREATE TABLE messages (
  id              INTEGER PRIMARY KEY,
  conversation_id INTEGER NOT NULL,
  role            TEXT NOT NULL,       -- 'player' | 'villager'
  content         TEXT NOT NULL,
  created_at      DATETIME NOT NULL,
  FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

CREATE TABLE gifts (
  id            INTEGER PRIMARY KEY,
  villager_id   TEXT NOT NULL,
  player_id     TEXT NOT NULL,
  item          TEXT NOT NULL,
  reaction      TEXT,
  given_at      DATETIME NOT NULL
);
```

### Retrieval

When assembling a prompt, the conversation engine retrieves the **N most relevant memories** for this villager and this conversation.

MVP scoring (no embeddings required):
```
score = salience
      + recency_weight * exp(-age_in_days / 30)
      + topical_weight * keyword_overlap(memory.content, recent_player_messages)
      + relationship_weight * (1 if memory mentions player else 0)
```

Top 8–12 memories make it into the prompt. Cheap, deterministic, good enough for the MVP. Embedding-based semantic recall is a future upgrade.

### Forgetting / summarization

Memory grows unbounded if we let it. Two strategies:

1. **Decay & prune.** Low-salience memories that haven't been recalled in 60+ in-game days get pruned.
2. **Episodic compression.** Every ~10 utterance-memories on the same topic get compressed by Claude into a single episode-memory (with a `summarized_from` pointer if we want to be fancy).

End-of-conversation hook: a small Claude call generates a `summary` for the conversation row + extracts new long-term memories (facts, opinions). This is where memory consolidation happens, modeled loosely on sleep-time replay.

## Mood

Each villager has a **mood state machine**.

```
States: content, happy, excited, melancholy, anxious, irritated, peaceful, lonely
```

Transitions are nudged by:
- **Time of day** (Bramble +irritated in morning, Sage +peaceful at dusk)
- **Recent interactions** (a kind word: +happy; ignored for days: +lonely)
- **Gifts** (loved gift: +excited; disliked gift: +irritated)
- **World events** (rain: Maple +melancholy unless she has rain boots, Bramble +content because rain = reading weather)
- **Drift toward baseline** (everyone slowly returns to their default mood over hours)

Mood is one of the dynamic fields in the personality and is injected into every prompt. It's not visible to the player as a number — they feel it through dialogue tone.

Implementation: a small finite-state machine per villager, ticked every minute by the world clock, with weighted transition probabilities. Heavy events override; ambient effects nudge.

## Conversation engine

### Flow

1. Player approaches villager → client sends `{type: "begin_conversation", villager: "maple", player_pos: [..]}`
2. Server creates a `conversation` row, returns greeting (Claude call with full prompt).
3. Player message → server appends to `messages`, retrieves relevant memories, calls Claude with cached personality block + dynamic state + retrieved memories + conversation history.
4. Response streamed back to client over WebSocket as deltas (so dialogue appears word-by-word).
5. On `end_conversation`: server writes summary + extracts new memories + updates relationship/mood.

### Tone & length

Built into the system prompt per villager. Maple's responses skew warmer and longer; Bramble's are clipped and dry; Clover's are bouncy and end in questions; Sage's are measured and metaphorical.

We give Claude an explicit length budget per response (e.g. `aim for 1–3 sentences, occasionally 4 if the moment calls for it`). This keeps the cadence of a chat, not a monologue.

### Cross-villager references

Each villager has a "mental model" of the others — basically, a small summary of what they think of each other. When a villager mentions another, the conversation engine can pull the relevant fragment ("Bramble thinks Clover is exhausting but secretly likes her") into the prompt.

## Villager-to-villager interactions

Villagers occasionally talk to each other in the world. Triggered by:
- Two villagers within proximity during an idle schedule slot
- A scheduled event (Maple drops off flowers at the shop)
- A world event they're both reacting to

The conversation engine runs a *two-sided* prompt: each villager's personality block is provided, and Claude generates a short exchange between them. The exchange is added as a **shared memory** to both, with appropriate POVs.

Cost-wise: keep these rare. 1–2 per in-game day, max. Player overhears them by being nearby.

## World state

Single source of truth, kept in memory + persisted to SQLite periodically.

```python
WorldState = {
  "in_game_time": datetime,
  "day_of_year": int,
  "time_of_day": "dawn" | "morning" | "midday" | "afternoon" | "evening" | "night",
  "weather": "clear" | "cloudy" | "rain",   # MVP: rotates simply
  "season": "spring" | "summer" | "autumn" | "winter",
  "villager_positions": {villager_id: (x, z)},
  "villager_activities": {villager_id: "tending garden" | "reading" | ...},
}
```

Every villager prompt includes a small "world context" snippet generated from this. The mobile companion app reads the same state.

## Event bus

In-process pub/sub for now (`asyncio.Queue` style). Events:

- `player.entered_village`
- `player.approached(villager_id)`
- `player.gave_gift(villager_id, item)`
- `villager.mood_changed(villager_id, old, new)`
- `world.time_advanced(new_time_of_day)`
- `world.weather_changed(new_weather)`

Villagers (and future systems) subscribe. The mobile push system, when it lands, subscribes to a curated subset and turns them into "texts" from villagers.

## Mobile companion notifications (future, but design here)

Premise: while you're away, the village keeps going. Occasionally a villager "texts" you about something that happened.

- Server runs a slow background tick when no client is connected.
- Mood/relationship events trigger candidate notifications.
- A small Claude call writes the text in the villager's voice (*"It rained on the marigolds today. I covered them with the green tarp. Thinking of you."* — Maple).
- Delivered via APNs / FCM push.
- The next time the player opens the game, those messages are part of the villager's memory ("did you get my text?").

This is why world state and event bus live on the server.

## Cost & performance

- **Per conversation turn:** ~2–4k input tokens (cached personality) + ~150 output tokens.
- **Prompt cache hit rate:** target >90% on personality block (it changes maybe once per session).
- **End-of-conversation extraction:** one extra short Claude call.
- **Background villager-to-villager:** budget 1–2 per in-game day.
- **Model choice:** Sonnet 4.6 (or Haiku 4.5 for low-stakes turns) — quality matters more than latency for cozy chat, but Haiku is fine for background events.

## Open questions

- **Embeddings now or later?** MVP uses keyword + recency. Vector recall is a clear upgrade once memory grows past a few hundred entries per villager.
- **Drift bounds.** How much can a villager's voice drift before they stop feeling like themselves? Lean: drift dynamic fields freely, never edit static fields automatically.
- **Trust calibration.** How much does the player learn about *you* from talking to villagers, vs. discover by overhearing?
- **Conflict.** Should villagers ever fight? (Lean: rarely, and reconcilably.)
- **The Heather question.** Heather is the player here. Should the game know she's Heather? (Probably — let her name herself, then the villagers can use it.)
