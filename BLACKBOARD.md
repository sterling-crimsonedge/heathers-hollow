# Heather's Hollow Build Blackboard

> Shared coordination board for Codex and Claude. Treat this file as the durable handoff surface: read it before acting, update it after acting, and keep entries concrete.

**Repo:** `/Users/sterlingblood/Repos/heathers-hollow`  
**Created:** 2026-05-15  
**Current phase:** Foundation Planning & Prototyping  
**Primary engine decision:** Godot 4 + GDScript unless Sterling explicitly pivots.

## Protocol

- Read `CLAUDE.md`, `README.md`, and this blackboard before starting new work.
- Claim one task at a time by changing its status to `IN PROGRESS - <agent>`.
- When done, mark it `DONE - <agent>` and add a dated note under Completed.
- If blocked, add a short note under Blocked with the exact decision or missing input needed.
- Do not overwrite the other agent's in-progress files without leaving a note here first.
- Keep implementation aligned with the docs unless this blackboard records a newer decision.
- Codex should prioritize implementation, testing, integration, and small docs needed to run the slice.
- Claude/Cowork should prioritize research, design docs, architecture planning, art direction, and task decomposition.

## Current State

Codex has implemented the Godot-path foundation slice:

- Expanded `docs/GAME_DESIGN.md`, `docs/AI_ARCHITECTURE.md`, and `docs/ART_DIRECTION.md`.
- Added a Godot 4 project with `game/scenes/main.tscn`, `player.tscn`, `villager.tscn`.
- Added player movement and Switch Pro-style input mapping in `game/scripts/player_controller.gd`.
- Added a WebSocket Godot client in `game/scripts/conversation_client.gd`.
- Added a simple generated village scene and dialogue UI in `game/scripts/main.gd`.
- Added FastAPI server endpoints at `/ws` and `/ws/conversation`.
- Added SQLite memory, relationship state, world time, events, Margot personality JSON, and local fallback conversation.
- Added `server/tests/test_memory_roundtrip.py` to prove the memory loop without a Claude key.
- Added a starter Dusty Rose gift action in Godot and validated gift memory through the live WebSocket smoke test.
- Polished the README run path with prerequisites, `uv` command, smoke tests, and troubleshooting.
- Added `mobile/mockup/index.html`, a static lock-screen notification mockup for the future companion app.
- Added `HOLLOW_DAY_LENGTH_SECONDS` support so server world time can run at demo speed.
- Added a persistent `MoodTracker` and wired tracked mood into villager conversation prompts.
- Added inactive Fern and Hugo personality configs for future cast expansion.
- Added a static Godot project validation smoke test for reference, input action, and packed-scene node checks while editor validation is blocked.
- Added a FastAPI contract smoke test for `/health`, `/ws`, `/ws/conversation`, and unknown WebSocket payload errors.
- Expanded personality config validation so every villager JSON checks required voice/preference fields, relationship ranges, prompt guardrails, and supported mood baselines.
- Added gift relationship/event coverage and updated the gift path to publish and persist `gift` events.
- Added read-only HTTP endpoints for `/world`, `/villagers`, `/villagers/{villager_id}`, and `/events/recent`.
- Added conversation relationship/event coverage and a MemoryStore helper for reading conversation turns by conversation id.
- Added deterministic mobile notification composition from persisted events plus `/notifications/recent`.
- Added a public relationship snapshot endpoint at `/relationships/{villager_id}/{subject_id}` that returns seeded defaults without creating rows.
- Added a public memory timeline endpoint at `/memories/recent` with villager/subject/kind filters and safe metadata.
- Added a north-star demo storyline smoke test that exercises Margot remembering a fact, receiving a gift, and surfacing relationship/memory/event/notification state.
- Added a live demo stack smoke test that starts uvicorn, drives `/ws`, and verifies HTTP read endpoints against the same persisted state.
- Added a deterministic demo seed utility at `server.tools.seed_demo_state` for pre-loading Margot's memory/gift storyline into a SQLite DB.
- Added a conversation transcript endpoint at `/conversations/{conversation_id}/turns` for opening memory timeline conversation ids into ordered turns.
- Added a deterministic away interaction tick that creates villager-to-villager memories, relationship changes, events, and notifications.
- Added a relationship graph endpoint at `/relationships` for persisted player/villager and villager/villager relationship edges.
- Extended the deterministic demo seed utility so preloaded demo databases include Margot/Fern away activity by default.
- Added filtering to `/events/recent` by event kind, actor, and target for client/debug story-thread views.
- Added matching filtering to `/notifications/recent` by event kind, actor, and target for mobile/client notification views.
- Added `POST /world/away-ticks` for bounded batches of background villager interactions.
- Added `after_id` cursors to `/events/recent` and `/notifications/recent` for incremental client polling.
- Added `GET /events/{event_id}` for opening a persisted event from a feed or notification.
- Added allowlisted public event metadata for `/events/recent` and `/events/{event_id}`.
- Added `GET /notifications/summary` for cheap mobile/client polling of unseen notification-worthy events.
- Added `GET /notifications/{event_id}` for opening one persisted event as a composed mobile-style notification payload.
- Added persisted notification cursors through `GET /notifications/cursor` and `POST /notifications/cursor`.
- Added `GET /notifications/inbox` for companion clients to read notifications newer than their persisted cursor without mutating read state.
- Added `GET /client/bootstrap` so clients can fetch world, public villagers, and pending notification inbox state with one startup request.
- Added `GET /client/villagers/{villager_id}/context` for fetching one villager's public interaction context.
- Added `GET /client/villagers/{villager_id}/social-context` for fetching one villager's public social graph context with other villagers.
- Conversation replies can now retrieve referenced villager social memories and relationship state when Heather asks about another villager.
- Conversation memories and events now expose sanitized memory-influence id lists so clients can explain why a villager remembered something.
- Added `GET /memories/{memory_id}` for opening one public memory payload from timelines, transcripts, events, or memory-influence ids.
- Added `GET /client/inventory` with a server-owned starter gift inventory including Dusty Rose and other prototype gift payloads.
- The `gift_item` path now normalizes known starter item ids from the server catalog before scoring, persisting memories, or logging events.
- `GET /client/bootstrap` now includes starter inventory along with world, public villagers, and notification inbox state.
- The Godot prototype now fetches `/client/bootstrap` on startup, caches world/villager/inventory payloads, and uses the server-provided Dusty Rose item for gifting when available.
- Public villager bootstrap summaries now include home locations, and the Godot prototype applies server-provided villager profiles to the existing Margot scene when available.
- The Godot prototype now displays a compact world status HUD populated from bootstrap world time, season, and weather when the server is available.
- The Godot prototype now displays a read-only bootstrap notification summary count without acknowledging notification cursors.
- Godot talk and gift payloads now include shared bootstrap-aware interaction context with world day, clock, time label, season, and weather fallbacks.
- Opening dialogue in Godot now starts a non-blocking villager context request and caches an allowlisted public context payload by villager id for future memory/relationship UI.
- The Godot dialogue panel now shows a compact public context summary from cached villager context: relationship tone/scores plus recent memory and event counts.
- Godot refreshes the active villager's public context after successful conversation and gift replies, with a single queued refresh if an existing request is already in flight.
- The Godot dialogue panel now also shows a clipped latest public memory teaser from cached villager context when available, hidden safely when no public memory is cached.
- The Godot dialogue panel now surfaces a compact reply memory-influence cue ("Remembered N thing(s)") read from `memories_used` on `villager_reply` payloads, hidden when the list is absent or empty and reset on dialogue close or before new talk/gift sends.

Validation run:

- `python3 game/tests/test_godot_project_static.py`
- `python3 -m compileall server`
- `python3 -m server.tests.test_away_interactions`
- `python3 -m server.tests.test_conversation_relationship`
- `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_demo_storyline`
- `python3 -m server.tests.test_demo_seed`
- `python3 -m server.tests.test_gift_relationship`
- `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_live_demo_stack`
- `python3 -m server.tests.test_memory_roundtrip`
- `python3 -m server.tests.test_mobile_notifications`
- `python3 -m server.tests.test_mood`
- `python3 -m server.tests.test_personality_configs`
- `python3 -m server.tests.test_social_memory_conversation`
- `python3 -m server.tests.test_world_state`
- `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`
- `uv run --python 3.12 --with-requirements server/requirements.txt ...` to import the FastAPI app and verify WebSocket routes.
- `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`
- `git diff --check`

Not validated yet:

- Godot editor/runtime launch. No `godot` or `godot4` binary was available in Codex shell.
- Live Claude API path. The server supports it when `ANTHROPIC_API_KEY` is set, but the smoke test used fallback mode.

## Direction Notes

- A nested `.claude/worktrees/.../BLACKBOARD.md` mentioned a Three.js browser demo. That conflicts with the direct project prompt, which specified Godot 4. Codex kept the Godot path and added `/ws` as a compatibility alias.
- If Sterling wants a temporary browser demo overnight, record that here as an explicit decision before moving primary client work away from Godot.
- **2026-05-15 heartbeat sync:** Claude/Cowork's nested blackboard now says the Three.js browser demo is the morning-demo path and Godot remains the long-term client. Do not merge the nested worktree into main casually; use the root blackboard to record which pieces should be promoted.

## Task Queue

### HH-001 - Verify Godot Project Opens

**Status:** BLOCKED - Codex  
**Owner:** Codex  
**Goal:** Open the `game/` project in Godot 4 when a Godot binary is available, fix any GDScript or scene import errors, and record the exact Godot version.

**Acceptance:**

- `game/project.godot` opens.
- `main.tscn` runs.
- Player can move.
- Talk prompt appears near Margot.
- Dialogue panel opens and attempts WebSocket connection.

### HH-002 - Add Live WebSocket Smoke Test

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Add a script that starts or targets the FastAPI server and verifies `/ws` or `/ws/conversation` roundtrip behavior with Margot.

**Acceptance:**

- Script documents how to run it.
- It sends one remembered fact, reconnects or starts a fresh client, asks about that fact, and reports pass/fail.
- It works without `ANTHROPIC_API_KEY` through fallback mode.

### HH-003 - Expand MVP Villager Cast Plan

**Status:** TODO  
**Owner:** Claude/Cowork  
**Goal:** Define the first 3-4 villagers with distinct personalities, relationships, preferences, and visual motifs.

**Acceptance:**

- Add or update docs with villager ids, names, archetypes, likes/dislikes, speaking voice, and relationship tensions.
- Flag which villager should be implemented after Margot.

### HH-004 - Implement Second Villager Config

**Status:** BLOCKED - Codex  
**Owner:** Codex  
**Goal:** After HH-003 identifies the next villager, add their JSON config and update the scene/server path enough to support selecting that villager.

**Acceptance:**

- New personality config in `server/data/personalities/`.
- Server can load the new villager.
- Godot can spawn the second villager with a distinct id/name.

### HH-005 - Inventory And Gift Prototype

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Add a minimal client-side gift action using the existing server `gift_item` path.

**Acceptance:**

- Player can press the gift action near Margot.
- Client sends a hardcoded starter item first, such as `Dusty Rose`.
- Server writes a `gift` memory and returns a relationship-aware response.
- Follow-up conversation can reference the gift.

### HH-006 - Mood And Relationship Tuning Notes

**Status:** TODO  
**Owner:** Claude/Cowork  
**Goal:** Review the initial relationship/mood model and suggest tuning rules for cozy but believable behavior.

**Acceptance:**

- Add notes under `docs/AI_ARCHITECTURE.md` or this blackboard.
- Include relationship deltas for talk, liked gift, loved gift, disliked gift, repeated visits, and neglect.

### HH-007 - README Run Path Polish

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Make the README quick-start airtight for future Sterling.

**Acceptance:**

- Server setup includes Python version recommendation.
- Godot launch steps are clear.
- Troubleshooting covers missing server, missing API key, and controller mapping.

### HH-008 - Mobile Notification Mockup

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Create a static mobile companion lock-screen mockup showing villager text notifications in the Heather's Hollow palette.

**Acceptance:**

- Add `mobile/mockup/index.html`.
- Self-contained HTML/CSS, no framework.
- Shows three stacked notifications from Maple, Bramble, and Sage.
- Uses palette values from `docs/ART_DIRECTION.md`.
- Opens directly in a browser as a polished static mockup.

### HH-009 - Configurable Demo Day Length

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Let the server world clock read `HOLLOW_DAY_LENGTH_SECONDS` so the demo can show visible time-of-day changes in a short play session.

**Acceptance:**

- `WorldState.create_default()` reads `HOLLOW_DAY_LENGTH_SECONDS`.
- Default remains one in-game day per 3600 real seconds.
- README documents `export HOLLOW_DAY_LENGTH_SECONDS=300` for demo speed.
- A small test verifies the environment variable changes world-clock speed.

### HH-010 - Mood State Machine

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Add a lightweight persistent mood tracker so villagers have slowly drifting emotional state instead of only per-message mood labels.

**Acceptance:**

- Add `server/ai/mood.py` with a `MOODS` list and `MoodTracker`.
- Persist villager self mood in existing relationship metadata for `subject_id='self'`.
- Conversation prompts and replies use tracked mood plus message nudges.
- A smoke test verifies a morning villager drifts toward a warm baseline and away from irritated states.

### HH-011 - Bench Villager Personality Configs

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Add Fern and Hugo as inactive, loadable personality configs adapted from Cowork's cast-expansion task.

**Acceptance:**

- Add `server/data/personalities/fern.json` and `server/data/personalities/hugo.json`.
- Do not spawn them in Godot or change active gameplay flow.
- Both load through `PersonalityStore`.
- A smoke test verifies their names and prompt blocks are distinguishable.

### HH-012 - Static Godot Project Validation

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Add a no-editor static smoke test for the Godot project while HH-001 is blocked by missing Godot runtime.

**Acceptance:**

- Verify `game/project.godot` main scene exists.
- Verify `res://` scene and script references resolve to files in `game/`.
- Verify runtime-created input actions cover the actions used by GDScript.
- Verify scene nodes referenced by `$NodeName` exist in their packed scenes.
- Document the command in README or the blackboard validation list.

### HH-013 - FastAPI Contract Smoke Test

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Add a lightweight server API contract test so route aliases and health payloads stay stable for Godot and future companion clients.

**Acceptance:**

- Import the FastAPI app with an isolated temporary SQLite DB.
- Verify `/health` is registered and returns `ok`, `world`, and `villagers`.
- Verify both WebSocket aliases `/ws` and `/ws/conversation` are registered.
- Verify unknown WebSocket payload types return a structured error response.
- Document the command in README or the blackboard validation list.

### HH-014 - Personality Config Schema Validation

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Expand personality-config smoke coverage so every JSON villager config follows the current server contract.

**Acceptance:**

- Validate every `server/data/personalities/*.json` file, not only Fern and Hugo.
- Verify file stem matches `id` and display names, traits, values, likes, dislikes, goals, and system prompt are populated.
- Verify relationship starting values are valid integer ranges.
- Verify `mood_baseline_by_time` keys are known day phases and values are supported mood ids.
- Keep the existing Fern/Hugo distinct prompt assertions.

### HH-015 - Gift Relationship Event Coverage

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Ensure the server gift path updates memory, relationship state, mood, and event logs consistently.

**Acceptance:**

- Add an engine-level test for a loved gift and a neutral gift.
- Verify loved gifts raise affection/trust more than neutral gifts.
- Verify gift memories preserve item metadata and preference.
- Publish and persist a `gift` event with memory id and preference metadata.
- Re-run the existing lightweight server/client smoke checks.

### HH-016 - Read-Only Server State Endpoints

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Add stable HTTP read endpoints for world state, villager summaries, villager detail, and recent events for Godot/web/mobile clients.

**Acceptance:**

- Add `/world`, `/villagers`, `/villagers/{villager_id}`, and `/events/recent`.
- Keep villager responses public; do not expose system prompts or private goals.
- Return persisted recent events with metadata for mobile companion-style clients.
- Extend the API contract smoke test to cover the new routes and payload shapes.
- Document the endpoints in README.

### HH-017 - Conversation Relationship Event Coverage

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Add direct engine-level coverage for conversation memory, relationship, turn, and event behavior.

**Acceptance:**

- Add a test for a personal positive conversation with Margot.
- Verify conversation relationship deltas for affection, trust, and familiarity.
- Verify conversation memory metadata includes conversation id, player text, reply, world, and context.
- Verify two conversation turns are stored in order.
- Verify live and persisted `conversation` events include memory id and mood metadata.

### HH-018 - Mobile Notification Feed Prototype

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Add a deterministic server-side notification feed that turns persisted events into mobile companion-style notification payloads.

**Acceptance:**

- Add a notification composer for recent conversation and gift events.
- Add `GET /notifications/recent` with clamped `limit`.
- Keep payloads simple: id, villager id/name, title, body, event kind, created_at, metadata.
- Cover the endpoint and composer in tests without requiring Claude/API access.
- Document the endpoint in README.

### HH-019 - Relationship Snapshot Endpoint

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Add a stable HTTP endpoint clients can use to inspect a villager's relationship state with Heather or another subject without exposing private personality prompts.

**Acceptance:**

- Add a read path that does not create relationship rows just by reading.
- Add `GET /relationships/{villager_id}/{subject_id}` with clamped public score fields and safe metadata.
- Return seeded starting values when no persisted relationship exists.
- Cover the endpoint in the API contract smoke test.
- Document the endpoint in README.

### HH-020 - Recent Memory Timeline Endpoint

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Add a read-only memory timeline endpoint for client debugging, companion UI, and the morning demo so Sterling can see what villagers actually remember.

**Acceptance:**

- Add a non-mutating memory query helper that can filter by villager, subject, and memory kind.
- Add `GET /memories/recent` with clamped `limit`.
- Return public memory payloads with text, salience, emotion, timestamps, and safe metadata only.
- Cover route registration, filtering, and metadata redaction in the API contract smoke test.
- Document the endpoint in README.

### HH-021 - North Star Demo Storyline Smoke Test

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Add one deterministic smoke test that exercises the full "Margot remembers" demo path across conversation, gift, relationships, memories, events, and mobile notifications.

**Acceptance:**

- Use an isolated temporary SQLite database and fallback conversation mode.
- Send a personal fact, ask Margot to recall it, give a Dusty Rose, and query read endpoints.
- Verify the reply references the remembered fact.
- Verify relationship, memory timeline, event feed, and notification payloads reflect the interaction.
- Document the command in README and the blackboard validation list.

### HH-022 - Live Demo Stack HTTP/WS Smoke Test

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Add a single live-stack smoke test that starts the FastAPI server, drives the WebSocket conversation path, then verifies the HTTP read endpoints against the same persisted state.

**Acceptance:**

- Start an isolated uvicorn server on a temporary port and temporary SQLite database.
- Use the real `/ws` WebSocket route for conversation and gifting.
- Query `/relationships`, `/memories/recent`, `/events/recent`, `/notifications/recent`, `/world`, and `/villagers/{id}` over HTTP.
- Verify the remembered fact, Dusty Rose gift, relationship state, memory timeline, event feed, and notification feed.
- Document the command in README and the blackboard validation list.

### HH-023 - Demo State Seed Script

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Add a small CLI utility that seeds a polished Margot memory/gift storyline into a SQLite DB for demos without requiring live Claude access.

**Acceptance:**

- Add a module runnable with `python -m ...`.
- Use fallback mode by default so output is deterministic and offline.
- Support an optional `--db-path` for isolated or persistent demo databases.
- Print the key reply, relationship, memory, event, and notification counts.
- Add a smoke test with a temporary DB and document the command in README.

### HH-024 - Conversation Transcript Endpoint

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Add a read-only conversation transcript endpoint so a memory timeline conversation id can be opened into the actual player/villager turns for demo and debugging.

**Acceptance:**

- Add `GET /conversations/{conversation_id}/turns`.
- Return ordered player/villager turns with ids, speakers, text, timestamps, and safe metadata.
- Redact raw private metadata while preserving useful context such as location, mood, and memories used.
- Return 404 for unknown conversation ids.
- Cover the route in the API contract smoke test and document it in README.

### HH-025 - Away Villager Interaction Tick

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Add the first deterministic villager-to-villager interaction tick so villagers can form memories and relationships while Heather is away.

**Acceptance:**

- Add an engine that selects two villagers, chooses a cozy shared topic, writes reciprocal memories, updates relationship scores, and persists an event.
- Add a server endpoint for triggering one away tick in demo/dev mode.
- Ensure notifications and event feeds can surface the interaction safely.
- Add smoke coverage without requiring Claude/API access.
- Document the command/endpoint in README and the blackboard validation list.

### HH-026 - Relationship Graph Endpoint

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Add a read-only relationship graph endpoint so clients can inspect persisted player/villager and villager/villager relationship edges.

**Acceptance:**

- Add a non-mutating relationship query helper with optional villager and subject filters.
- Add `GET /relationships` returning persisted public relationship snapshots.
- Include safe relationship metadata for gifts, mood, and away-interaction topics.
- Cover filtering and metadata redaction in the API contract smoke test.
- Document the endpoint in README and the blackboard validation list.

### HH-027 - Demo Seed Away Activity

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Extend the demo seed utility so a preloaded demo database includes villager-to-villager away activity in addition to Margot's player memory/gift storyline.

**Acceptance:**

- Add an `--away-ticks` option to `server.tools.seed_demo_state`.
- Seed at least one deterministic Margot/Fern away interaction by default.
- Include away interaction, relationship graph, event, and notification counts in the seed summary.
- Extend the demo seed smoke test to verify away memories, relationships, and notifications.
- Document the option in README and the blackboard validation list.

### HH-028 - Filtered Event Feed Endpoint

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Let clients filter the persisted event feed by kind, actor, and target so Godot/mobile/debug views can inspect specific story threads without scanning unrelated events.

**Acceptance:**

- Add a non-mutating event query helper with optional `kind`, `actor_id`, and `target_id` filters.
- Extend `GET /events/recent` with those filters while preserving the current unfiltered response shape.
- Cover filtered gift and villager-to-villager event reads in the API contract smoke test.
- Document the filtered endpoint in README and the blackboard validation list.

### HH-029 - Filtered Notification Feed Endpoint

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Let companion/client views request notifications for a specific event kind, actor, or villager target without composing unrelated recent events.

**Acceptance:**

- Extend `GET /notifications/recent` with optional `kind`, `actor_id`, and `target_id` filters.
- Reuse the persisted event query path so notification filtering matches `/events/recent` ordering and limits.
- Cover filtered gift and villager-to-villager notifications in API contract tests.
- Document the filtered notification endpoint in README and the blackboard validation list.

### HH-030 - Batch Away Interaction Endpoint

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Let demos and future companion jobs advance several background villager interactions with one bounded request.

**Acceptance:**

- Add an engine/API path that runs a clamped batch of away interaction ticks.
- Return a stable payload with requested count, actual count, and individual tick summaries.
- Cover route registration, relationship accumulation, events, and notification visibility in smoke tests.
- Document the batch endpoint in README and the blackboard validation list.

### HH-031 - Incremental Event And Notification Cursors

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Let mobile/client pollers request only events newer than the last event id they already processed.

**Acceptance:**

- Add an `after_id` cursor filter to the persisted event query helper.
- Extend `GET /events/recent` and `GET /notifications/recent` with `after_id` while preserving existing filters and response shapes.
- Cover incremental event and notification reads in API contract tests.
- Document the cursor parameter in README and the blackboard validation list.

### HH-032 - Event Detail Endpoint

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Let clients open a specific persisted event id from an event feed or notification into a stable event detail payload.

**Acceptance:**

- Add a read-only event lookup helper that does not mutate event state.
- Add `GET /events/{event_id}` returning the same public payload shape as `/events/recent`.
- Return HTTP 404 for unknown event ids.
- Cover route registration, successful lookup, and 404 behavior in API contract tests.
- Document the endpoint in README and the blackboard validation list.

### HH-033 - Public Event Metadata Redaction

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Keep event feed/detail payloads useful for clients while preventing raw private event metadata from leaking through public HTTP endpoints.

**Acceptance:**

- Add a public event metadata filter for `/events/recent` and `/events/{event_id}`.
- Preserve useful event metadata such as memory ids, mood, gift preference/item, away-interaction topic, and relationship delta.
- Redact arbitrary private metadata keys from public event payloads.
- Cover redaction in API contract tests for event feed and event detail.
- Document the metadata behavior in README and the blackboard validation list.

### HH-034 - Notification Poll Summary Endpoint

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Let mobile/client pollers cheaply check whether new notification-worthy events exist without fetching the full notification feed.

**Acceptance:**

- Add a non-mutating event count helper that supports the same kind, actor, target, and `after_id` filters as event queries.
- Add `GET /notifications/summary` returning latest event id, unseen count, `has_unseen`, cursor, and active filters.
- Keep the endpoint derived from persisted events so it matches `/notifications/recent`.
- Cover route registration, filtered counts, and empty-state behavior in API contract tests.
- Document the endpoint in README and the blackboard validation list.

### HH-035 - Notification Detail Endpoint

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Let clients open one persisted event id directly into the composed mobile-style notification payload.

**Acceptance:**

- Add `GET /notifications/{event_id}` using the same notification composer as `/notifications/recent`.
- Return HTTP 404 for unknown event ids.
- Preserve notification metadata allowlisting and villager display names.
- Cover route registration, successful lookup, and 404 behavior in API contract tests.
- Document the endpoint in README and the blackboard validation list.

### HH-036 - Persisted Notification Cursor

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Let a future mobile companion client persist the last notification event it has processed so polling can resume without only relying on caller-held state.

**Acceptance:**

- Add SQLite-backed notification cursor storage keyed by `client_id`.
- Add `GET /notifications/cursor` and `POST /notifications/cursor` endpoints.
- Keep cursor updates idempotent and monotonic so stale clients do not move the cursor backward.
- Cover route registration, missing-cursor defaults, updates, and summary integration in API contract tests.
- Document the endpoint in README and the blackboard validation list.

### HH-037 - Notification Inbox Endpoint

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Let a future mobile companion client fetch only notifications newer than its persisted cursor without mutating read state.

**Acceptance:**

- Add `GET /notifications/inbox` keyed by `client_id`.
- Use the stored cursor as the `after_id` for notification composition.
- Return cursor state, notification count, next cursor event id, and `has_more`.
- Cover missing-cursor and advanced-cursor behavior in API contract tests.
- Document the endpoint in README and the blackboard validation list.

### HH-038 - Client Bootstrap Endpoint

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Let Godot or the future mobile companion fetch initial world, villager, and pending notification state with one startup request.

**Acceptance:**

- Add `GET /client/bootstrap`.
- Include server world snapshot and public villager summaries.
- Include read-only notification inbox payload for the supplied `client_id`.
- Cover route registration, payload shape, and cursor-aware notification behavior in API contract tests.
- Document the endpoint in README and the blackboard validation list.

### HH-039 - Villager Client Context Endpoint

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Let a client fetch one villager's public profile, relationship state, recent memories, and recent events before opening an interaction UI.

**Acceptance:**

- Add `GET /client/villagers/{villager_id}/context`.
- Include world snapshot, public villager detail, public relationship snapshot, recent public memories, and recent public events.
- Keep system prompts, private goals, raw memory metadata, and raw event metadata out of the payload.
- Cover route registration, successful context payload, metadata redaction, and unknown-villager 404 in API contract tests.
- Document the endpoint in README and the blackboard validation list.

### HH-040 - Villager Social Context Endpoint

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Let a client fetch one villager's public social graph context with other villagers, including recent villager-to-villager memories and events.

**Acceptance:**

- Add `GET /client/villagers/{villager_id}/social-context`.
- Include public villager summary, persisted relationship edges involving that villager, recent `villager_interaction` memories, and recent `villager_interaction` events.
- Keep system prompts, private goals, raw relationship metadata, raw memory metadata, and raw event metadata out of the payload.
- Cover route registration, successful payload, metadata redaction, target-side event inclusion, and unknown-villager 404 in API contract tests.
- Document the endpoint in README and the blackboard validation list.

### HH-041 - Conversation Social Memory Recall

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Let villager conversations use relevant villager-to-villager memories and relationship state when Heather asks about another villager.

**Acceptance:**

- Detect referenced villager names/ids in player text.
- Retrieve recent `villager_interaction` memories and persisted relationship state for referenced villagers.
- Include that social context in Claude prompts and fallback replies without inventing events.
- Return social memory ids in `memories_used` when they influenced a reply.
- Add deterministic smoke coverage for asking Margot about Fern after an away interaction.

### HH-042 - Public Conversation Memory Influence Metadata

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Persist and expose safe memory-influence ids for conversation memories and events so clients can explain why a villager remembered something.

**Acceptance:**

- Persist `memories_used` and `social_memory_ids` on conversation memory metadata.
- Persist `memories_used` and `social_memory_ids` on conversation event metadata.
- Expose those id lists through public memory and event payloads with integer-only sanitization.
- Extend deterministic social-memory conversation coverage to verify private metadata remains redacted while public payloads expose the influence ids.

### HH-043 - Memory Detail Endpoint

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Let clients open one persisted memory id from a memory timeline, transcript, event payload, or influence list.

**Acceptance:**

- Add a read-only memory lookup helper that does not mutate access counters.
- Add `GET /memories/{memory_id}` returning the same public payload shape as `/memories/recent`.
- Return HTTP 404 for unknown memory ids.
- Cover route registration, successful lookup, metadata allowlisting, and 404 behavior in API contract tests.
- Document the endpoint in README and the blackboard validation list.

### HH-044 - Starter Inventory Endpoint

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Give Godot and future companion/debug clients a server-owned starter inventory of giftable item payloads instead of relying only on hardcoded client data.

**Acceptance:**

- Add a small static starter inventory/catalog module with item ids, display names, categories, tags, gift prompts, and quantities.
- Add `GET /client/inventory?player_id=heather` returning public giftable item payloads that can be sent through the existing `gift_item` WebSocket path.
- Include the Dusty Rose starter gift currently used by Godot.
- Cover route registration, payload shape, item ordering, and metadata safety in API contract tests.
- Document the endpoint in README and the blackboard validation list.

### HH-045 - Gift Catalog Normalization

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Let clients send a minimal starter inventory `item_id` through `gift_item` and have the server expand it from the catalog before relationship, memory, and event logic runs.

**Acceptance:**

- Add an inventory lookup/normalization helper that returns safe public gift item fields only.
- Update the conversation gift path to normalize incoming items before scoring preferences or persisting metadata.
- Known starter item ids should override stale or partial client fields with server catalog values.
- Unknown item ids should still be accepted with sanitized fallback fields for prototyping.
- Cover catalog-only gifts and stale client payload redaction in gift/API/WebSocket smoke tests.
- Document the behavior in README and the blackboard validation list.

### HH-046 - Bootstrap Inventory Payload

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Include the starter gift inventory in the one-call client bootstrap payload so Godot/mobile clients can initialize world, villagers, notifications, and giftable items together.

**Acceptance:**

- Extend `GET /client/bootstrap` with a `player_id` parameter.
- Include an `inventory` payload that matches `GET /client/inventory`.
- Keep system prompts, private goals, preferences, and internal sort order out of bootstrap inventory items.
- Preserve existing notification cursor behavior and blank-client validation.
- Cover bootstrap inventory shape and blank-player-id behavior in API contract tests.
- Document the expanded bootstrap payload in README and the blackboard validation list.

### HH-047 - Godot Bootstrap Inventory Wiring

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Have the Godot prototype fetch `/client/bootstrap` on startup and use the server-provided starter inventory for gifting when available.

**Acceptance:**

- Add a Godot HTTP bootstrap request that reads world/villager/inventory startup payloads without blocking WebSocket conversation.
- Cache the bootstrap `inventory.items` list and prefer the server-provided `dusty_rose` payload for the Gift Rose action.
- Keep a safe fallback gift item id so gifting still works when the HTTP bootstrap request fails.
- Preserve existing WebSocket talk/gift controls and controller mappings.
- Extend the static Godot test to verify bootstrap inventory wiring while runtime validation remains blocked.
- Document the client behavior in README and the blackboard validation list.

### HH-048 - Godot Bootstrap Villager Data Wiring

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Use the `/client/bootstrap` villager payload to hydrate Godot villager data instead of relying only on hardcoded Margot labels.

**Acceptance:**

- Cache bootstrap public villagers by id after startup.
- Apply server-provided `display_name` and `home_location` to the existing Margot scene when available.
- Keep the existing hardcoded Margot fallback so the prototype still works offline.
- Preserve the current talk/gift interaction flow and WebSocket ids.
- Extend the static Godot test to verify villager bootstrap data wiring.

### HH-049 - Godot Bootstrap World Status HUD

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Surface the `/client/bootstrap` world snapshot in the Godot prototype so Heather can see server-authoritative time/weather state.

**Acceptance:**

- Add a small, unobtrusive Godot UI label for world time, season, and weather.
- Populate it from cached `bootstrap_world` when the HTTP bootstrap succeeds.
- Keep an offline fallback label so the scene still reads cleanly before or without the server.
- Preserve existing dialogue, talk, gift, and controller behavior.
- Extend the static Godot test to verify world-status bootstrap wiring.

### HH-050 - Godot Bootstrap Notification Summary

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Use the `/client/bootstrap` notification inbox payload to give the Godot prototype a tiny pending-news indicator without turning it into a full companion UI.

**Acceptance:**

- Cache the bootstrap `notifications` payload when the startup request succeeds.
- Add a small optional HUD label that shows pending notification count or a quiet no-news fallback.
- Keep notification cursor state read-only; do not acknowledge or mutate notification cursors from Godot.
- Preserve existing world HUD, dialogue, talk, gift, and controller behavior.
- Extend the static Godot test to verify notification bootstrap wiring.

### HH-051 - Godot Bootstrap Context Payload Wiring

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Include cached bootstrap world context in Godot talk and gift payloads so server/debug records can see what the client believed was happening when the interaction started.

**Acceptance:**

- Add a helper that builds shared interaction context from villager context plus cached bootstrap world fields.
- Use the helper for both player messages and gifts.
- Keep safe fallback values when the HTTP bootstrap is unavailable.
- Preserve existing talk/gift controls, server ids, and HUD behavior.
- Extend the static Godot test to verify shared context wiring.

### HH-052 - Godot Villager Context Fetch On Dialogue

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Let the Godot prototype fetch `/client/villagers/{villager_id}/context` when dialogue opens so future UI can show recent memories, relationship state, and nearby events without blocking conversation.

**Acceptance:**

- Add a non-blocking HTTP request path for the active villager's public context when opening dialogue.
- Cache the latest context payload by villager id.
- Keep dialogue, talk, and gift behavior working if the context request fails.
- Do not expose private/system prompt fields in Godot-side logs or UI.
- Extend the static Godot test to verify villager context request wiring.

### HH-053 - Godot Dialogue Context Summary

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Surface the cached villager context in the dialogue panel as a small public memory/relationship summary once the non-blocking context request returns.

**Acceptance:**

- Add a compact dialogue context label or row that is empty/offline-safe until context is cached.
- Show only public, player-useful context such as recent memory count, recent event count, and relationship tone/score.
- Update the label when the active villager's context request completes without interrupting typing, talk, or gift flows.
- Keep private/system prompt fields out of UI and logs.
- Extend the static Godot test to verify context summary UI wiring.

### HH-054 - Godot Context Refresh After Interactions

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Refresh the active villager's public context after successful conversation replies and gifts so the dialogue summary reflects newly written memories, events, and relationship changes without reopening dialogue.

**Acceptance:**

- Trigger a non-blocking active-villager context refresh after a villager reply arrives.
- Trigger a non-blocking active-villager context refresh after a gift reply arrives.
- Avoid duplicate refresh storms if a context request is already in flight for the same villager.
- Preserve current dialogue text, input focus, talk/gift controls, and fallback behavior.
- Extend the static Godot test to verify post-interaction context refresh wiring.

### HH-055 - Godot Latest Memory Teaser

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Make the dialogue context summary feel more like memory by showing a short, public latest-memory teaser from the cached villager context when one exists.

**Acceptance:**

- Extract the newest public memory text from cached villager context without exposing raw/private metadata.
- Add a compact one-line teaser under or alongside the existing bond summary.
- Truncate long memory text so it cannot stretch the dialogue panel.
- Keep the teaser hidden/offline-safe when no public memories are cached.
- Extend the static Godot test to verify latest-memory teaser wiring.

### HH-056 - Godot Reply Memory Influence Status

**Status:** DONE - Codex  
**Owner:** Codex  
**Goal:** Surface when a villager reply used persisted memories by showing a short, public status cue from WebSocket reply metadata.

**Acceptance:**

- Read `memories_used` from `villager_reply` payloads without fetching or exposing raw memory text.
- Add a compact cue such as `Remembered 2 things` in the dialogue status or context area when the list is non-empty.
- Keep the cue hidden/noisy-state-free when `memories_used` is absent or empty.
- Preserve the existing mood status, talk/gift flow, and context summary refresh behavior.
- Extend the static Godot test to verify reply memory-influence status wiring.

## Completed

- **2026-05-15 - Codex:** Created repo-root blackboard and added the initial overnight coordination protocol.
- **2026-05-15 - Codex:** Completed HH-002. Added `server/tests/test_websocket_roundtrip.py`, which can target a running server or start an isolated temporary uvicorn server, reconnect over `/ws`, and verify Margot remembers a fact across WebSocket sessions. Added explicit `websockets` dependency to `server/requirements.txt`.
- **2026-05-15 - Codex:** Completed HH-005. Added `G` / `Gift Rose` client flow for a hardcoded Dusty Rose starter item, improved server gift preference matching so Margot loves flower/handmade gifts, and extended the live WebSocket smoke test to verify gift memory across sessions.
- **2026-05-15 - Codex:** Completed HH-007. Expanded README quick-start with prerequisites, virtualenv and `uv` server commands, fallback/API-key behavior, smoke tests, and troubleshooting for server connection, dependencies, controller mapping, and missing shell Godot binary. Re-ran `python3 -m compileall server`, `python3 -m server.tests.test_memory_roundtrip`, and `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`.
- **2026-05-15 - Codex:** Completed HH-008. Added `mobile/mockup/index.html`, a self-contained iOS-style lock-screen mockup with Maple, Bramble, and Sage notifications using the Heather's Hollow palette. Validated with `python3` HTML parser and added a link from `mobile/README.md`.
- **2026-05-15 - Codex:** Completed HH-009. `WorldState.create_default()` now reads `HOLLOW_DAY_LENGTH_SECONDS` with a 3600-second default, snapshots include `day_length_seconds`, README documents `export HOLLOW_DAY_LENGTH_SECONDS=300`, and `server/tests/test_world_state.py` verifies demo-speed clock behavior. Re-ran compile, memory, world-state, and live WebSocket smoke tests.
- **2026-05-15 - Codex:** Completed HH-010. Added `server/ai/mood.py` with persistent relationship-metadata mood state, added Margot's time-of-day mood baselines, wired tracked mood into `ConversationEngine`, and added `server/tests/test_mood.py`. Re-ran compile, mood, world-state, memory, and live WebSocket smoke tests.
- **2026-05-15 - Codex:** Completed HH-011. Added inactive `fern.json` and `hugo.json` personality configs adapted from Cowork's Fern/Hugo cast notes, plus `server/tests/test_personality_configs.py` to verify they load and produce distinct prompt blocks. Re-ran compile, personality, mood, memory, and live WebSocket smoke tests.
- **2026-05-15 - Codex:** Completed HH-012. Added `game/tests/test_godot_project_static.py`, which checks `project.godot` main scene wiring, all `res://` references, runtime input action coverage, and `$NodeName` references against packed scenes without requiring the Godot editor. Documented it in README and ran `python3 game/tests/test_godot_project_static.py` plus `python3 -m compileall server`.
- **2026-05-15 - Codex:** Completed HH-013. Added `server/tests/test_api_contract.py`, which imports the FastAPI app with a temporary SQLite DB and verifies `/health`, `/ws`, `/ws/conversation`, and structured errors for unknown payload types. Documented it in README and ran `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `python3 game/tests/test_godot_project_static.py`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_world_state`, and `python3 -m compileall server`.
- **2026-05-15 - Codex:** Completed HH-014. Expanded `server/tests/test_personality_configs.py` from a Fern/Hugo-only smoke test into an all-config schema check covering file stem/id consistency, populated voice/preference fields, prompt guardrails, relationship seed ranges, and supported mood baselines. Documented the coverage in README and ran `python3 -m server.tests.test_personality_configs`, `python3 -m compileall server`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_memory_roundtrip`, `python3 game/tests/test_godot_project_static.py`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, and `python3 -m server.tests.test_world_state`.
- **2026-05-15 - Codex:** Completed HH-015. Updated `ConversationEngine.handle_gift()` to seed villager identity/starting relationship and publish plus persist `gift` events with memory id, item, mood, and preference metadata. Added `MemoryStore.get_recent_events()` and `server/tests/test_gift_relationship.py` to verify loved vs neutral gift relationship deltas, memory metadata, mood, live events, and persisted events. Documented the test in README and ran `python3 -m server.tests.test_gift_relationship`, `python3 -m compileall server`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_world_state`, `python3 game/tests/test_godot_project_static.py`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, and `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`.
- **2026-05-15 - Codex:** Completed HH-016. Added read-only FastAPI endpoints for `/world`, `/villagers`, `/villagers/{villager_id}`, and `/events/recent`, with public villager summaries that omit system prompts and private goals. Extended `server/tests/test_api_contract.py` to cover route registration, payload shape, 404 behavior for unknown villagers, and recent event output. Documented endpoints in README and ran `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `python3 -m compileall server`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_world_state`, `python3 game/tests/test_godot_project_static.py`, and `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`.
- **2026-05-15 - Codex:** Completed HH-017. Added `ConversationTurnRecord` plus `MemoryStore.get_conversation_turns()` and `server/tests/test_conversation_relationship.py` to verify a personal positive conversation updates affection/trust/familiarity, writes memory metadata, stores two ordered conversation turns, and publishes/persists a `conversation` event with memory id and mood metadata. Documented the test in README and ran `python3 -m server.tests.test_conversation_relationship`, `python3 -m compileall server`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_world_state`, `python3 game/tests/test_godot_project_static.py`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, and `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`.
- **2026-05-15 - Codex:** Completed HH-018. Added `server/mobile/notifications.py`, `server/tests/test_mobile_notifications.py`, and `GET /notifications/recent`, composing safe deterministic mobile-style notifications from persisted gift/conversation events while only exposing selected metadata. Extended API contract coverage and README endpoint docs. Ran `python3 -m server.tests.test_mobile_notifications`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `python3 -m compileall server`, `python3 -m server.tests.test_conversation_relationship`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_world_state`, `python3 game/tests/test_godot_project_static.py`, and `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`.
- **2026-05-15 - Codex:** Completed HH-019. Added `MemoryStore.peek_relationship()` plus `GET /relationships/{villager_id}/{subject_id}` so clients can read public relationship scores and safe metadata while preserving seeded defaults without creating rows. Extended API contract coverage and README endpoint docs. Ran `python3 -m compileall server`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_conversation_relationship`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_mobile_notifications`, `python3 game/tests/test_godot_project_static.py`, and `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`.
- **2026-05-15 - Codex:** Completed HH-020. Added `MemoryStore.query_memories()` and `GET /memories/recent` so clients can inspect recent memories by villager, subject, and kind without mutating retrieval counters or exposing raw private metadata. Extended API contract coverage and README endpoint docs. Ran `python3 -m compileall server`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_conversation_relationship`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_mobile_notifications`, `python3 game/tests/test_godot_project_static.py`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, and `python3 -m server.tests.test_world_state`.
- **2026-05-15 - Codex:** Completed HH-021. Added `server/tests/test_demo_storyline.py`, a deterministic north-star smoke test that sends Margot a bluebell teacup memory, confirms fallback recall, gives a Dusty Rose, and verifies relationship, memory timeline, event feed, and notification payloads. Documented the command in README. Ran `python3 -m compileall server`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_demo_storyline`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `python3 -m server.tests.test_conversation_relationship`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_mobile_notifications`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_world_state`, `python3 game/tests/test_godot_project_static.py`, and `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`.
- **2026-05-15 - Codex:** Completed HH-022. Added `server/tests/test_live_demo_stack.py`, which starts an isolated uvicorn server, sends a porcelain-fox memory and Dusty Rose gift through the real `/ws` route, then verifies `/relationships`, `/memories/recent`, `/events/recent`, `/notifications/recent`, `/world`, and `/villagers/margot` over HTTP. Documented the command in README. Ran `python3 -m compileall server`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_live_demo_stack`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_demo_storyline`, `python3 -m server.tests.test_conversation_relationship`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_mobile_notifications`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_world_state`, `python3 game/tests/test_godot_project_static.py`, and `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`.
- **2026-05-15 - Codex:** Completed HH-023. Added `server/tools/seed_demo_state.py`, a runnable CLI/function that forces fallback mode by default and seeds Margot's porcelain-fox memory plus Dusty Rose gift into a selected SQLite DB. Added `server/tests/test_demo_seed.py` and README instructions for `python -m server.tools.seed_demo_state --db-path server/data/demo.sqlite3`. Ran `python3 -m compileall server`, `python3 -m server.tests.test_demo_seed`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_demo_storyline`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_live_demo_stack`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `python3 -m server.tests.test_memory_roundtrip`, `python3 game/tests/test_godot_project_static.py`, `python3 -m server.tests.test_conversation_relationship`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_mobile_notifications`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_world_state`, and `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`.
- **2026-05-15 - Codex:** Completed HH-024. Added `GET /conversations/{conversation_id}/turns`, returning ordered transcript turns with safe metadata for location, mood, and memories used. Extended API contract coverage and the live demo stack test to open a conversation id from `/memories/recent` and verify the transcript. Documented the endpoint in README. Ran `python3 -m compileall server`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_live_demo_stack`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_demo_storyline`, `python3 -m server.tests.test_demo_seed`, `python3 -m server.tests.test_conversation_relationship`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_mobile_notifications`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_world_state`, `python3 game/tests/test_godot_project_static.py`, and `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`.
- **2026-05-15 - Codex:** Completed HH-025. Added `server/world/away.py` with `AwayInteractionEngine`, `POST /world/away-tick`, safe away-interaction notification metadata/body handling, and `server/tests/test_away_interactions.py`. The tick currently picks/accepts two villagers, chooses a shared cozy topic such as tea, writes reciprocal `villager_interaction` memories, nudges mutual relationship scores, persists a `villager_interaction` event, and surfaces it through notifications. Documented the endpoint and test in README. Ran `python3 -m compileall server`, `python3 -m server.tests.test_away_interactions`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_live_demo_stack`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_demo_storyline`, `python3 -m server.tests.test_demo_seed`, `python3 -m server.tests.test_memory_roundtrip`, `python3 game/tests/test_godot_project_static.py`, `python3 -m server.tests.test_conversation_relationship`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_mobile_notifications`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_world_state`, and `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`.
- **2026-05-15 - Codex:** Completed HH-026. Added `MemoryStore.query_relationships()` and `GET /relationships` with villager/subject filters, public relationship snapshots, and safe metadata for gifts, mood, and away-interaction topics. Extended API contract coverage to verify graph filtering after an away tick, plus metadata redaction. Documented the endpoint in README. Ran `python3 -m compileall server`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `python3 -m server.tests.test_away_interactions`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_live_demo_stack`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_demo_storyline`, `python3 -m server.tests.test_demo_seed`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_conversation_relationship`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_mobile_notifications`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_world_state`, `python3 game/tests/test_godot_project_static.py`, and `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`.
- **2026-05-15 - Codex:** Completed HH-027. Extended `server.tools.seed_demo_state` with `--away-ticks` defaulting to one Margot/Fern tea-garden away interaction, plus away memory counts, relationship edge counts, and latest notification details in the seed summary. Expanded `server/tests/test_demo_seed.py` to verify away memories, Margot/Fern relationship state, relationship graph edges, events, and notifications from the seeded DB. Updated README seed instructions to show `--away-ticks 1`. Ran `python3 -m compileall server`, `python3 -m server.tests.test_demo_seed`, `python3 -m server.tools.seed_demo_state --db-path /tmp/heathers-hollow-seed-smoke.sqlite3 --away-ticks 1 --json`, `python3 -m server.tests.test_away_interactions`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_demo_storyline`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_live_demo_stack`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_conversation_relationship`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_mobile_notifications`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_world_state`, `python3 game/tests/test_godot_project_static.py`, and `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`.
- **2026-05-15 - Codex:** Completed HH-028. Added `MemoryStore.query_events()` with optional `kind`, `actor_id`, and `target_id` filters, updated `GET /events/recent` to use it while preserving the response shape, and extended API contract coverage for filtered gift plus villager interaction event reads. Updated README endpoint docs. Ran `python3 -m compileall server`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `python3 -m server.tests.test_away_interactions`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_demo_storyline`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_live_demo_stack`, `python3 -m server.tests.test_demo_seed`, `python3 -m server.tests.test_mobile_notifications`, `python3 game/tests/test_godot_project_static.py`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_conversation_relationship`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_world_state`, and `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`.
- **2026-05-15 - Codex:** Completed HH-029. Extended `GET /notifications/recent` with optional `kind`, `actor_id`, and `target_id` filters using the same `MemoryStore.query_events()` path as `/events/recent`, then expanded API contract coverage for filtered Margot/Fern gift notifications and filtered Margot/Fern away-interaction notifications. Updated README endpoint docs. Ran `python3 -m compileall server`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `python3 -m server.tests.test_mobile_notifications`, `python3 -m server.tests.test_away_interactions`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_demo_storyline`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_live_demo_stack`, `python3 -m server.tests.test_demo_seed`, `python3 game/tests/test_godot_project_static.py`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_conversation_relationship`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_world_state`, and `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`.
- **2026-05-15 - Codex:** Completed HH-030. Added `AwayInteractionEngine.run_ticks()` and `POST /world/away-ticks`, returning a stable batch payload with requested count, clamped actual count, and individual tick payloads. Extended away/API contract tests for route registration, clamping, accumulated Margot/Fern relationship state, filtered events, and filtered notifications. Updated README endpoint docs. Ran `python3 -m compileall server`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `python3 -m server.tests.test_away_interactions`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_demo_storyline`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_live_demo_stack`, `python3 -m server.tests.test_demo_seed`, `python3 -m server.tests.test_mobile_notifications`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_conversation_relationship`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_world_state`, `python3 game/tests/test_godot_project_static.py`, and `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`.
- **2026-05-15 - Codex:** Completed HH-031. Added `after_id` to `MemoryStore.query_events()`, `GET /events/recent`, and `GET /notifications/recent` so mobile/client pollers can fetch only persisted events newer than their last processed event id while preserving existing kind/actor/target filters. Extended API contract coverage for incremental events and notifications, and updated README endpoint docs. Ran `python3 -m compileall server`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `python3 -m server.tests.test_mobile_notifications`, `python3 -m server.tests.test_away_interactions`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_demo_storyline`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_live_demo_stack`, `python3 -m server.tests.test_demo_seed`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_conversation_relationship`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_world_state`, `python3 game/tests/test_godot_project_static.py`, and `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`.
- **2026-05-15 - Codex:** Completed HH-032. Added `MemoryStore.get_event()` and `GET /events/{event_id}` so clients can open a persisted event from an event feed or notification into the same public payload shape used by `/events/recent`, with 404 behavior for unknown ids. Extended API contract coverage and updated README endpoint docs. Ran `python3 -m compileall server`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `python3 -m server.tests.test_mobile_notifications`, `python3 -m server.tests.test_away_interactions`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_demo_storyline`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_live_demo_stack`, `python3 -m server.tests.test_demo_seed`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_conversation_relationship`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_world_state`, `python3 game/tests/test_godot_project_static.py`, and `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`.
- **2026-05-15 - Codex:** Completed HH-033. Added `PUBLIC_EVENT_METADATA_KEYS` and `public_event_metadata()` so `/events/recent` and `/events/{event_id}` expose useful event metadata such as memory ids, mood, gift item/preference, away-interaction topic, and relationship delta while redacting arbitrary private keys. Extended API contract coverage for event feed/detail redaction and updated README metadata docs. Ran `python3 -m compileall server`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `python3 -m server.tests.test_mobile_notifications`, `python3 -m server.tests.test_away_interactions`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_demo_storyline`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_live_demo_stack`, `python3 -m server.tests.test_demo_seed`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_conversation_relationship`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_world_state`, `python3 game/tests/test_godot_project_static.py`, and `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`.
- **2026-05-15 - Codex:** Completed HH-034. Added `MemoryStore.count_events()` and `GET /notifications/summary`, returning `latest_event_id`, `after_id`, `unseen_count`, `has_unseen`, and active filters for cheap companion/client polling. The endpoint uses the same persisted event filters as `/notifications/recent`. Extended API contract coverage for route registration, filtered summary counts, cursor behavior, and empty states. Updated README endpoint docs. Ran `python3 -m compileall server`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `python3 -m server.tests.test_mobile_notifications`, `python3 -m server.tests.test_away_interactions`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_demo_storyline`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_live_demo_stack`, `python3 -m server.tests.test_demo_seed`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_conversation_relationship`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_world_state`, `python3 game/tests/test_godot_project_static.py`, and `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`.
- **2026-05-15 - Codex:** Completed HH-035. Added `GET /notifications/{event_id}` so a feed, summary poller, or future companion client can open one persisted event directly as a composed mobile-style notification payload, with 404 behavior and existing metadata allowlisting. Extended API contract coverage and updated README endpoint docs. Ran `python3 -m compileall server`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `python3 -m server.tests.test_mobile_notifications`, `python3 -m server.tests.test_away_interactions`, `python3 -m server.tests.test_demo_seed`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_conversation_relationship`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_world_state`, `python3 game/tests/test_godot_project_static.py`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_demo_storyline`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_live_demo_stack`, and `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`.
- **2026-05-15 - Codex:** Completed HH-036. Added SQLite-backed notification cursor storage keyed by `client_id`, plus `GET /notifications/cursor` and `POST /notifications/cursor` endpoints that return the stored cursor with an unseen summary and advance monotonically so stale clients cannot move it backward. Extended API contract coverage and updated README endpoint docs. Ran `python3 -m compileall server`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `python3 -m server.tests.test_mobile_notifications`, `python3 -m server.tests.test_away_interactions`, `python3 -m server.tests.test_demo_seed`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_conversation_relationship`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_world_state`, `python3 game/tests/test_godot_project_static.py`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_demo_storyline`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_live_demo_stack`, and `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`.
- **2026-05-15 - Codex:** Completed HH-037. Added `GET /notifications/inbox`, which reads a companion client's persisted cursor, returns the next oldest-unseen notification batch, reports `next_cursor_event_id`, and leaves cursor advancement to the existing explicit `POST /notifications/cursor` acknowledgement path. Extended `MemoryStore.query_events()` with an opt-in ascending order for cursor-safe batching, updated API contract coverage, and documented the endpoint in README. Ran `python3 -m compileall server`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `python3 -m server.tests.test_mobile_notifications`, `python3 -m server.tests.test_away_interactions`, `python3 -m server.tests.test_demo_seed`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_conversation_relationship`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_world_state`, `python3 game/tests/test_godot_project_static.py`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_demo_storyline`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_live_demo_stack`, and `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`.
- **2026-05-15 - Codex:** Completed HH-038. Added `GET /client/bootstrap`, which returns a server world snapshot, public villager summaries, and the read-only notification inbox for a supplied `client_id` without mutating notification cursors. Reused public villager and inbox payloads so system prompts remain private and companion clients still acknowledge through `POST /notifications/cursor`. Extended API contract coverage and README endpoint docs. Ran `python3 -m compileall server`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `python3 -m server.tests.test_mobile_notifications`, `python3 -m server.tests.test_away_interactions`, `python3 -m server.tests.test_demo_seed`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_conversation_relationship`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_world_state`, `python3 game/tests/test_godot_project_static.py`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_demo_storyline`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_live_demo_stack`, and `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`.
- **2026-05-15 - Codex:** Completed HH-039. Added `GET /client/villagers/{villager_id}/context`, which returns a world snapshot, one villager's public detail, public relationship state for a subject, recent public memories, and recent public events for interaction UI startup. The endpoint reuses existing public serializers so system prompts, private goals, and raw memory/event metadata remain hidden. Extended API contract coverage for route registration, metadata redaction, and unknown-villager 404, then updated README endpoint docs. Ran `python3 -m compileall server`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `python3 -m server.tests.test_mobile_notifications`, `python3 -m server.tests.test_away_interactions`, `python3 -m server.tests.test_demo_seed`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_conversation_relationship`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_world_state`, `python3 game/tests/test_godot_project_static.py`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_demo_storyline`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_live_demo_stack`, and `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`.
- **2026-05-15 - Codex:** Completed HH-040. Added `GET /client/villagers/{villager_id}/social-context`, which returns one villager's public summary, persisted relationship edges involving that villager, recent `villager_interaction` memories, and recent `villager_interaction` events where the villager is actor or target. The endpoint reuses public serializers so private prompts/goals and raw metadata stay hidden. Extended API contract coverage for route registration, successful payload, relationship/memory/event redaction, target-side event inclusion, and unknown-villager 404, then updated README endpoint docs. Ran `python3 -m compileall server`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `python3 -m server.tests.test_mobile_notifications`, `python3 -m server.tests.test_away_interactions`, `python3 -m server.tests.test_demo_seed`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_conversation_relationship`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_world_state`, `python3 game/tests/test_godot_project_static.py`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_demo_storyline`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_live_demo_stack`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`, and `git diff --check`.
- **2026-05-15 - Codex:** Completed HH-041. Updated `ConversationEngine` so player text that names another villager retrieves recent `villager_interaction` memories and persisted relationship state for that villager, includes that social context in Claude prompts, and uses it in fallback replies. Added `server/tests/test_social_memory_conversation.py`, which runs a Margot/Fern away interaction and verifies Margot references Fern's tea-garden memory when Heather asks about Fern. Updated README smoke-test docs. Ran `python3 -m compileall server`, `python3 -m server.tests.test_social_memory_conversation`, `python3 -m server.tests.test_conversation_relationship`, `python3 -m server.tests.test_away_interactions`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_mobile_notifications`, `python3 -m server.tests.test_demo_seed`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_world_state`, `python3 game/tests/test_godot_project_static.py`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_demo_storyline`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_live_demo_stack`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`, and `git diff --check`.
- **2026-05-15 - Codex:** Completed HH-042. Conversation memory and event metadata now persist `memories_used` and `social_memory_ids`, while public memory/event serializers expose those lists through integer-only sanitization. Extended `server/tests/test_social_memory_conversation.py` and `server/tests/test_api_contract.py` to verify raw persistence, public payload exposure, and redaction of private player text/context details. Updated README metadata docs. Ran `python3 -m compileall server`, `python3 -m server.tests.test_social_memory_conversation`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `python3 -m server.tests.test_conversation_relationship`, `python3 -m server.tests.test_away_interactions`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_mobile_notifications`, `python3 -m server.tests.test_demo_seed`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_world_state`, `python3 game/tests/test_godot_project_static.py`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_demo_storyline`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_live_demo_stack`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`, and `git diff --check`.
- **2026-05-15 - Codex:** Completed HH-043. Added `MemoryStore.get_memory()` plus `GET /memories/{memory_id}` so clients can open a persisted memory id from timelines, transcript metadata, events, or influence lists without mutating access counters. Reused public memory serialization for metadata redaction and extended API contract coverage for route registration, successful lookup, public payload parity, metadata allowlisting, access-counter stability, and 404 behavior. Updated README endpoint/API-contract docs. Ran `python3 -m compileall server`, `python3 game/tests/test_godot_project_static.py`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `python3 -m server.tests.test_social_memory_conversation`, `python3 -m server.tests.test_conversation_relationship`, `python3 -m server.tests.test_away_interactions`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_mobile_notifications`, `python3 -m server.tests.test_demo_seed`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_world_state`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_demo_storyline`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_live_demo_stack`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`, and `git diff --check`.
- **2026-05-15 - Codex:** Completed HH-044. Added `server/world/inventory.py` with a static starter gift inventory and `GET /client/inventory`, returning public item payloads with ids, names, categories, tags, quantities, and gift prompts that can be sent through the existing `gift_item` WebSocket path. The catalog includes the current Godot Dusty Rose gift plus Chamomile Bundle, Porcelain Button, and Smooth Pebble starter items. Extended API contract coverage for route registration, stable ordering, payload shape, metadata safety, and blank-player-id errors. Updated README endpoint/API-contract docs. Ran `python3 -m compileall server`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_conversation_relationship`, `python3 -m server.tests.test_social_memory_conversation`, `python3 -m server.tests.test_away_interactions`, `python3 -m server.tests.test_mobile_notifications`, `python3 -m server.tests.test_demo_seed`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_world_state`, `python3 game/tests/test_godot_project_static.py`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_demo_storyline`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_live_demo_stack`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`, and `git diff --check`.
- **2026-05-15 - Codex:** Completed HH-045. Added catalog lookup and safe gift-item normalization in `server/world/inventory.py`, then wired `ConversationEngine.handle_gift()` to expand known starter `item_id`s before preference scoring, memory persistence, and event logging. Known catalog ids now override stale/partial client fields; unknown item ids still use sanitized fallback fields for prototyping. Extended gift/API contract tests for catalog-only gifts, stale client payload override, raw metadata redaction, and unknown-item fallback, and updated the live WebSocket roundtrip to send a stale/minimal Dusty Rose payload. Updated README gift behavior docs. Ran `python3 -m compileall server`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_conversation_relationship`, `python3 -m server.tests.test_social_memory_conversation`, `python3 -m server.tests.test_away_interactions`, `python3 -m server.tests.test_mobile_notifications`, `python3 -m server.tests.test_demo_seed`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_world_state`, `python3 game/tests/test_godot_project_static.py`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_demo_storyline`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_live_demo_stack`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`, and `git diff --check`.
- **2026-05-15 - Codex:** Completed HH-046. Extended `GET /client/bootstrap` with a `player_id` parameter and an `inventory` payload that reuses the same public starter inventory shape as `GET /client/inventory`, so clients can initialize world state, public villagers, pending notifications, and giftable starter items in one read. Preserved notification cursor behavior and added blank-player-id validation. Updated README bootstrap endpoint docs and API contract coverage for inventory parity, metadata safety, and validation. Ran `python3 -m compileall server`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_conversation_relationship`, `python3 -m server.tests.test_social_memory_conversation`, `python3 -m server.tests.test_away_interactions`, `python3 -m server.tests.test_mobile_notifications`, `python3 -m server.tests.test_demo_seed`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_world_state`, `python3 game/tests/test_godot_project_static.py`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_demo_storyline`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_live_demo_stack`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`, and `git diff --check`.
- **2026-05-15 - Codex:** Completed HH-047. Updated `game/scripts/main.gd` to create a non-blocking `HTTPRequest` for `/client/bootstrap`, cache bootstrap world/villager/inventory data, and prefer the server-provided `dusty_rose` inventory payload for Gift Rose while keeping a safe item-id fallback. Extended the no-editor Godot static test for bootstrap inventory wiring and updated README client behavior docs. Ran `python3 game/tests/test_godot_project_static.py`, `python3 -m compileall server`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_conversation_relationship`, `python3 -m server.tests.test_social_memory_conversation`, `python3 -m server.tests.test_away_interactions`, `python3 -m server.tests.test_mobile_notifications`, `python3 -m server.tests.test_demo_seed`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_world_state`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_demo_storyline`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_live_demo_stack`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`, and `git diff --check`.
- **2026-05-15 - Codex:** Completed HH-048. Added public `home_location` values to villager summaries, cached Godot bootstrap villagers by id, and added `Villager.apply_public_profile()` so the existing Margot scene can apply server-provided display name and home location while retaining offline fallbacks. Updated dialogue status/player-id wiring, README client docs, and static/API contract coverage. Ran `python3 game/tests/test_godot_project_static.py`, `python3 -m compileall server`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_conversation_relationship`, `python3 -m server.tests.test_social_memory_conversation`, `python3 -m server.tests.test_away_interactions`, `python3 -m server.tests.test_mobile_notifications`, `python3 -m server.tests.test_demo_seed`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_world_state`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_demo_storyline`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_live_demo_stack`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`, and `git diff --check`.
- **2026-05-15 - Codex:** Completed HH-049. Added a compact Godot world status HUD with an offline fallback, wired bootstrap world snapshots through `_apply_bootstrap_world()`, and formatted server clock, time label, season, and weather for display. Extended static Godot coverage for world-status bootstrap wiring and updated README client/static-test docs. Ran `python3 game/tests/test_godot_project_static.py`, `python3 -m compileall server`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `python3 -m server.tests.test_world_state`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_conversation_relationship`, `python3 -m server.tests.test_social_memory_conversation`, `python3 -m server.tests.test_away_interactions`, `python3 -m server.tests.test_mobile_notifications`, `python3 -m server.tests.test_demo_seed`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_demo_storyline`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_live_demo_stack`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`, and `git diff --check`.
- **2026-05-15 - Codex:** Completed HH-050. Added a read-only Godot notification summary HUD label, cached the `/client/bootstrap` `notifications` payload, and displayed pending note counts with a quiet fallback without calling cursor acknowledgement endpoints. Extended static Godot coverage for notification bootstrap wiring and updated README client/static-test docs. Ran `python3 game/tests/test_godot_project_static.py`, `python3 -m compileall server`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `python3 -m server.tests.test_mobile_notifications`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_conversation_relationship`, `python3 -m server.tests.test_social_memory_conversation`, `python3 -m server.tests.test_away_interactions`, `python3 -m server.tests.test_demo_seed`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_world_state`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_demo_storyline`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_live_demo_stack`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`, and `git diff --check`.
- **2026-05-15 - Codex:** Completed HH-051. Added `_interaction_context()` plus bootstrap world fallback helpers in `game/scripts/main.gd` so talk and gift WebSocket payloads share villager context, `client_time`, and world day/clock/time label/season/weather context; Gift Rose adds `gift_source` as extra context through the same helper. Extended static Godot coverage for shared interaction context and updated README client/static-test docs. Ran `python3 game/tests/test_godot_project_static.py`, `python3 -m compileall server`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_conversation_relationship`, `python3 -m server.tests.test_social_memory_conversation`, `python3 -m server.tests.test_away_interactions`, `python3 -m server.tests.test_mobile_notifications`, `python3 -m server.tests.test_demo_seed`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_world_state`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_demo_storyline`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_live_demo_stack`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`, and `git diff --check`.
- **2026-05-15 - Codex:** Completed HH-052. Added a non-blocking Godot `HTTPRequest` for `/client/villagers/{villager_id}/context` when dialogue opens, with public allowlisted caching in `villager_context_by_id` and no UI/log exposure of private prompt fields. Dialogue, talk, and gift flows remain unchanged if the request fails. Extended static Godot coverage and README client/static-test docs. Ran `python3 game/tests/test_godot_project_static.py`, `python3 -m compileall server`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_conversation_relationship`, `python3 -m server.tests.test_social_memory_conversation`, `python3 -m server.tests.test_away_interactions`, `python3 -m server.tests.test_mobile_notifications`, `python3 -m server.tests.test_demo_seed`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_world_state`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_demo_storyline`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_live_demo_stack`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`, and `git diff --check`.
- **2026-05-15 - Codex:** Completed HH-053. Added a hidden-by-default `dialogue_context_label` that fills from cached public villager context when available, showing relationship tone, affection/trust scores, recent memory count, and recent event count. The summary updates when the active villager's context request completes and clears safely when dialogue closes, without exposing private prompt fields or changing talk/gift controls. Extended static Godot coverage and README client/static-test docs. Ran `python3 game/tests/test_godot_project_static.py`, `python3 -m compileall server`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_conversation_relationship`, `python3 -m server.tests.test_social_memory_conversation`, `python3 -m server.tests.test_away_interactions`, `python3 -m server.tests.test_mobile_notifications`, `python3 -m server.tests.test_demo_seed`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_world_state`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_demo_storyline`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_live_demo_stack`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`, and `git diff --check`.
- **2026-05-15 - Codex:** Completed HH-054. Added in-flight villager context request tracking and a single pending-refresh marker so Godot refreshes active villager context after successful `villager_reply` messages from both talk and gift flows without restarting a same-villager request already in progress. The refresh preserves dialogue text, input focus, and controls, and updates the cached summary after the HTTP context response returns. Extended static Godot coverage and README client/static-test docs. Ran `python3 game/tests/test_godot_project_static.py`, `python3 -m compileall server`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_conversation_relationship`, `python3 -m server.tests.test_social_memory_conversation`, `python3 -m server.tests.test_away_interactions`, `python3 -m server.tests.test_mobile_notifications`, `python3 -m server.tests.test_demo_seed`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_world_state`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_demo_storyline`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_live_demo_stack`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`, and `git diff --check`.
- **2026-05-15 - Codex:** Completed HH-056. Added a hidden-by-default `dialogue_influence_label` under the Godot dialogue context/memory labels, and wired `_on_server_message` to call a new `_update_dialogue_influence_status(message)` that reads `memories_used` from `villager_reply` payloads and renders a compact "Remembered N thing(s)" cue. The cue hides itself when `memories_used` is missing, non-array, or empty, clears on dialogue close via `_clear_dialogue_context_summary()`, and clears before new talk/gift sends so stale influence cues do not linger during pending requests; mood status, talk/gift flow, and existing context summary refresh behavior are preserved. Extended `game/tests/test_godot_project_static.py` with `test_main_reply_memory_influence_status_wiring` covering label creation, helper signatures, `memories_used` parsing, the cue strings, clipping, and that the cue does not expose raw memory text or private fields. Ran `python3 game/tests/test_godot_project_static.py`, `python3 -m compileall server`, `python3 -m server.tests.test_away_interactions`, `python3 -m server.tests.test_conversation_relationship`, `python3 -m server.tests.test_demo_seed`, `python3 -m server.tests.test_gift_relationship`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_mobile_notifications`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_social_memory_conversation`, `python3 -m server.tests.test_world_state`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_demo_storyline`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_live_demo_stack`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`, `git diff --check`, and `command -v godot || command -v godot4` (still unavailable).
- **2026-05-15 - Codex:** Completed HH-055. Added a hidden-by-default `dialogue_memory_label` under the Godot dialogue bond summary, extracting only the newest public memory `text` from cached villager context, normalizing line breaks, truncating long text, and clearing safely when no public memory is cached. Extended static Godot coverage and README client/static-test docs. Ran `python3 game/tests/test_godot_project_static.py`, `python3 -m compileall server`, `python3 -m server.tests.test_away_interactions`, `python3 -m server.tests.test_conversation_relationship`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_demo_storyline`, `python3 -m server.tests.test_demo_seed`, `python3 -m server.tests.test_gift_relationship`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_live_demo_stack`, `python3 -m server.tests.test_memory_roundtrip`, `python3 -m server.tests.test_mobile_notifications`, `python3 -m server.tests.test_mood`, `python3 -m server.tests.test_personality_configs`, `python3 -m server.tests.test_social_memory_conversation`, `python3 -m server.tests.test_world_state`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_api_contract`, `uv run --python 3.12 --with-requirements server/requirements.txt python -m server.tests.test_websocket_roundtrip --start-server`, `git diff --check`, and `command -v godot || command -v godot4` (still unavailable).

## Blocked

- Godot runtime validation is blocked until a Godot 4 binary is available in the shell or the app is opened manually.
- HH-004 is blocked until HH-003 defines the next villager to implement.

## Notes For Overnight Automation

Last Codex heartbeat check: **2026-05-15 07:28 MDT / 2026-05-15 13:28 UTC**. Completed HH-056 Godot reply memory-influence status follow-up. Godot runtime validation remains blocked until a Godot 4 binary is available. No new TODO tasks owned by Codex remain in the queue; HH-001 and HH-004 stay blocked (Godot binary, HH-003 cast decision). Outstanding TODOs for Claude/Cowork: HH-003 (villager cast plan) and HH-006 (mood/relationship tuning notes).

Codex heartbeat should:

1. Read this file.
2. Pick the highest-priority `TODO` task owned by Codex that is not blocked.
3. Mark it `IN PROGRESS - Codex`.
4. Implement and test within the repo.
5. Update this file with status, completed notes, commands run, and blockers.
6. Leave user-facing summaries concise in the thread.
