# Heather's Hollow Consolidation Plan

This document is the merge plan after the overnight split between the root Codex/Godot track and the Claude/Cowork browser-demo worktrees.

## What Went Wrong

Coordination existed as text, but it did not function as engineering coordination. The agents wrote to different worktrees, used different runtime assumptions, and allowed two server/client contracts to evolve independently:

- The root repo followed the original Godot + FastAPI + SQLite plan.
- Claude/Cowork worktrees built a Three.js browser demo with a different WebSocket protocol and a different personality/server model.
- A standalone `codex-demo.html` was added in the root as a temporary browser surface, but it is not the same as Claude's `game/web/` Three.js client.
- The blackboards recorded status after the fact, but did not force a single canonical server contract before client work continued.

The result is useful work on both sides, but not a coherent game yet.

## Source Of Truth Decisions

These decisions should hold until Sterling explicitly changes them.

1. **Root repo is canonical.** Worktree files under `.claude/worktrees/` are references, not merge targets.
2. **`server/` in the root repo is canonical.** It has the richer memory, relationship, event, notification, inventory, context, and test coverage.
3. **Godot remains the long-term primary client.** The browser client is a playable inspection/demo client, not a replacement.
4. **A browser client is still worth keeping.** It gives fast visual iteration while Godot runtime access remains blocked.
5. **One protocol only.** Browser and Godot clients must consume the root server contract:
   - HTTP: `/client/bootstrap`, `/client/inventory`, `/client/villagers/{id}/context`, `/world`, `/villagers`, `/memories`, `/events`, `/notifications`
   - WebSocket: `/ws` or `/ws/conversation` with `player_message` and `gift_item` payloads returning `villager_reply`
   - Detailed reference: `docs/CLIENT_PROTOCOL.md`
6. **Do not merge Claude's server wholesale.** Extract ideas only: Three.js scene, richer web controls/UI, possible streaming UX later.
7. **LLM provider should be pluggable.** For local play without an Anthropic key, add Ollama as the next provider behind the existing deterministic fallback. Claude API can remain optional.

## Keep, Port, Rewrite, Drop

### Keep In Root

- Root `server/` memory model, relationship model, world/events, notification endpoints, inventory catalog, and tests.
- Root `server/data/personalities/*.json` config format.
- Root Godot project and static Godot test.
- Root `mobile/mockup/`.
- Root README smoke-test list, with updates as consolidation lands.

### Port From Claude Worktrees

- `game/web/index.html`, `game/web/main.js`, and `game/web/scene.js` as the proper browser demo location.
- Three.js village feel: terrain, paths, cottages, trees, floating labels, camera/movement/gamepad patterns.
- Browser demo README ideas.
- Villager concepts Maple/Bramble/Clover/Sage only after converting them into root JSON personality configs or design docs.

### Rewrite While Porting

- Rewrite Claude's browser networking to the root server contract.
- Replace `begin`/`say`/`gift`/`end` and chunk events with root `player_message`/`gift_item` and `villager_reply`.
- Replace Claude's `/player`, `/player/name`, and `ready` assumptions with `/client/bootstrap` and `/client/villagers/{id}/context`.
- Use root inventory item payloads instead of browser string gifts.
- Use root `display_name`, `home_location`, `species`, `archetype`, and relationship/context fields.

### Drop Or Defer

- Claude CLI subprocess provider as the default path. It was useful for a no-key experiment, but Sterling now wants Ollama/local iteration and lower latency.
- Claude worktree server schema as a merge target.
- Standalone root `codex-demo.html` as a permanent surface. Keep it only as a throwaway reference until `game/web/` works against root server, then delete or archive it.
- Streaming chunk protocol until the canonical non-streaming client is stable. Add streaming later as an extension, not a second protocol.

## Consolidation Work Queue

### CONS-001 - Freeze Root Server Contract

Owner: Codex

Goal: document and test the canonical client contract so all clients target the same API.

Acceptance:

- Add a compact protocol section to README or `docs/`.
- Ensure API contract tests cover the exact WebSocket payload names used by clients.
- Explicitly document that Claude branch `begin`/`say`/`gift` is legacy and not canonical.

### CONS-002 - Add Ollama Provider Behind Root Conversation Engine

Owner: Codex
Status: Done 2026-05-15. Implemented as `HOLLOW_LLM_PROVIDER=fallback|ollama|anthropic|auto` with fakeable Ollama tests and deterministic fallback.

Goal: support local LLM iteration without Anthropic keys or Claude Code CLI latency.

Acceptance:

- Add provider selection such as `HOLLOW_LLM_PROVIDER=fallback|ollama|anthropic|auto`.
- Add `OLLAMA_BASE_URL` defaulting to `http://127.0.0.1:11434`.
- Add `OLLAMA_MODEL` defaulting to a reasonable local model name.
- Call Ollama `/api/chat` with `stream: false`, a system prompt from the existing prompt builder, and one user message.
- Preserve deterministic fallback if Ollama is not running, times out, or returns an invalid payload.
- Add tests using a fake Ollama client/path without requiring Ollama installed.

### CONS-003 - Promote Browser Demo Into `game/web/`

Owner: Codex
Status: Done 2026-05-15. Root `game/web/` now uses `/client/bootstrap`, `/client/villagers/{id}/context`, `player_message`, and `gift_item`; the old root `codex-demo.html` is archived under `docs/prototypes/`.

Goal: move from the throwaway `codex-demo.html` and Claude worktree web files to a root `game/web/` browser demo.

Acceptance:

- Add `game/web/index.html`, `game/web/main.js`, `game/web/scene.js`, and `game/web/README.md`.
- The browser demo loads villagers from root `/client/bootstrap`.
- Selecting a villager fetches root `/client/villagers/{id}/context`.
- Talking sends root `player_message`; gifting sends root `gift_item`.
- The UI shows root memory/context/reply metadata where available.
- It degrades visibly when the server is offline.

### CONS-004 - Bring Web Demo Visual Polish Forward

Owner: Codex or Claude/Cowork

Goal: make the promoted browser demo feel like a place, not a protocol tester.

Acceptance:

- Port Three.js village scene basics from Claude worktree.
- Keep draw calls reasonable.
- Add visible player movement, villager labels, cozy lighting, and controller-friendly interaction.
- Do not change server protocol.

### CONS-005 - Reconcile Villager Cast

Owner: Claude/Cowork for design, Codex for implementation

Goal: decide whether MVP cast is Margot/Fern/Hugo or Maple/Bramble/Clover/Sage, then express it in root JSON configs.

Acceptance:

- Design doc declares MVP cast and next villager priority.
- All active villagers have JSON configs under `server/data/personalities/`.
- Server tests cover all active configs.
- Browser and Godot clients can list/spawn the active cast from root `/client/bootstrap` and `/villagers`.

### CONS-006 - Remove Or Archive Divergent Artifacts

Owner: Codex

Goal: prevent future agents from accidentally treating stale worktree/server files as canonical.

Acceptance:

- `BLACKBOARD.md` points to this consolidation plan.
- `.claude/worktrees/` is explicitly marked reference-only in the blackboard.
- Temporary `codex-demo.html` is removed or moved under `docs/prototypes/` after `game/web/` works.
- README no longer presents two different ways to run incompatible clients.

## Immediate Order

1. Freeze root server contract.
2. Add Ollama provider to root server.
3. Promote a root `game/web/` client that uses the root contract.
4. Port visual polish into that client.
5. Reconcile villager cast.
6. Clean up stale artifacts.

This sequence prevents more UI work from landing on the wrong protocol and gives Sterling a playable browser demo without sacrificing the Godot path.
