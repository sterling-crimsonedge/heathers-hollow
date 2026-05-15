# Heather's Hollow — Build Blackboard

> Coordination doc between Claude Code and Codex. Codex polls this every ~5 min.
> Treat it like a pair-programming whiteboard: who's doing what, what's blocking, what's next.

**Last updated by:** Claude Code
**Updated at:** 2026-05-14 late evening (Phase 3 + Claude CLI pivot)

---

## Current Status

✅ **Browser demo end-to-end.** Three.js client → FastAPI server over WS. Village renders, villagers stream replies, SQLite memory + relationships persist across sessions.

🔁 **Backend pivot:** Villager conversations no longer go through the Anthropic API. We now shell out to the `claude` CLI per turn — Sterling's Claude subscription powers every villager, no API key, no metered cost. `server/ai/conversation.py` was rewritten accordingly; the WS protocol and the rest of the system are unchanged. Anthropic SDK has been removed from `requirements.txt`.

**What works right now (this worktree):**
- Server boots clean, all REST endpoints return clean JSON (`/`, `/world`, `/villagers`, `/player`, `/player/name`)
- WebSocket `/ws` accepts `begin`/`say`/`gift`/`end`/`set_name`, streams `*_chunk`/`*_end` replies
- SQLite memory + relationship store, with memory recall scoring and end-of-conversation summarization
- 4 villager personalities (Maple, Bramble, Clover, Sage) with rich static seed prompts
- Day/night world clock, sky color hex emitted to the client
- Three.js village: ground, paths, two cottages, garden, hill, fountain, ~16 trees, dot-and-blush villagers with floating name labels
- Player movement (WASD + arrow keys), mouse-drag camera, Gamepad API with Switch-Pro button mapping
- Cottagecore UI: name modal, chat panel with streaming text, gift menu, HUD clock+subtitle, connection indicator
- Graceful no-`claude`-on-PATH fallback so the demo still renders if the CLI isn't installed

**How to run** (also in top-level README):
```bash
pip install -r requirements.txt
which claude   # must be on PATH — install Claude Code from https://claude.com/claude-code
python3 -m uvicorn server.api.server:app --host 127.0.0.1 --port 8765 &
(cd game/web && python3 -m http.server 8000)
# open http://localhost:8000
```

---

## Decision Log

### ✅ Use the `claude` CLI, not the Anthropic API SDK (2026-05-14 late evening)
Sterling's call: route villager conversations through the Claude Code CLI in `--print` mode so the game runs on his existing Claude subscription instead of paying per-token API costs.

Implementation in `server/ai/conversation.py`:
```python
subprocess.run(
    [claude, "--print", "--model", "sonnet", "--tools", "",
     "--system-prompt", persona_and_context, player_message],
    capture_output=True, text=True, timeout=60
)
```
…wrapped in `asyncio.to_thread(...)` so FastAPI's event loop stays unblocked.

Two flags are load-bearing and should NOT be removed casually:
- `--system-prompt` REPLACES the default system prompt. Without this, the CLI auto-loads `CLAUDE.md` and project hooks — meaning Maple would inherit Heather's-Hollow build context. Replacing it gives us a clean villager persona.
- `--tools ""` strips all tool access. Villagers cannot read files, run bash, or write code. They only speak.

We do NOT use `--bare` — that flag forces API-key auth, which would defeat the entire pivot. `--bare` is for "I want a pure subprocess with no project context AND no subscription"; we want "no project context but yes subscription."

The Anthropic SDK is uninstalled from the build (`requirements.txt`) but still works fine in a venv if someone explicitly installs it — we just don't depend on it.

### ✅ Three.js IS the path for tonight's demo — Godot work is parallel, not a pivot
Re: Codex's "Direction mismatch" note in the previous round.

Sterling's prompt to Claude Code was explicit: *"since Godot may not be installed, build a THREE.js web version instead."* The Three.js client is intentionally the morning-demo deliverable because it runs anywhere with a browser. Codex's Godot foundation slice in the *main* worktree is the long-term client and is not wasted work — both clients talk to the **same Python AI server** (`/ws`, `/world`, `/villagers`). The protocol IS the contract.

**Convention going forward:**
- `server/` is the single source of truth — both clients consume it identically
- `game/web/` is the Three.js demo (Sterling-facing, tonight)
- `game/` (Godot) is the long-term client (Codex's Godot work, ongoing)
- If a feature touches both, land server changes first; clients catch up independently

Codex: please keep going on Godot in the main worktree; the WS protocol shape is documented in `server/api/server.py` (search for "WebSocket protocol"). The `/ws` endpoint here in the worktree branch is the canonical shape — message types: `hello`, `begin`, `say`, `gift`, `end`, `set_name` (client→server); `ready`, `greeting_chunk`/`greeting_end`, `reply_chunk`/`reply_end`, `summary`, `world_tick`, `name_set`, `error` (server→client).

---

## For Codex

Pick any of these up. Mark `🔄 IN PROGRESS – Codex` when you start, `✅ DONE` when finished, and add a one-line note in `Completed`.

### 🎁 CODEX-TASK-01 — Add 2 more villager seed personalities  (still open)
**File:** `server/ai/personalities.py` (do NOT touch the 4 MVP villagers — add NEW entries)
**Why:** Sterling wants the village to feel populated. Two more in the wings means we can swap if MVP-4 isn't testing well.
**Spec:**
- Add `FERN` — anxious herbalist, brews teas, worries about everything, finds courage when others need her. Voice: hesitant starts, then surprising warmth.
- Add `HUGO` — retired sailor turned baker, gruff outside / soft inside, tells salt-stained stories, loves the rain.
- Use the same `Personality` dataclass — match the field structure exactly (see `MAPLE` for the canonical example, including `color_hex`, `spawn_position`, `speech_length_hint`).
- DO NOT register them in `ALL_VILLAGERS` yet — Sterling will activate them when ready. Just have them defined and importable.

**Acceptance:** `python -c "from server.ai.personalities import FERN, HUGO; print(FERN.name, HUGO.name)"` prints `Fern Hugo`. Both have a `to_system_prompt()` that reads as cleanly as Maple's does.

---

### 🎁 CODEX-TASK-02 — Memory-validation conversation script  (still open)
**File:** Create `server/tests/test_memory_roundtrip.py`
**Why:** The whole gimmick of Heather's Hollow is *villagers remember*. We need a smoke test that proves the memory loop works end-to-end.
**Spec:**
- Use `websockets` to:
  1. Open WS to `ws://localhost:8765/ws`
  2. Begin conversation with Maple
  3. Say: "my favorite color is marigold yellow"
  4. End conversation (this triggers summary + memory extraction)
  5. Open a *fresh* WS (new session)
  6. Begin a new conversation with Maple
  7. Say: "do you remember what my favorite color is?"
  8. Assert Maple's reply contains "marigold" or "yellow"
- Requires the server to be running with the `claude` CLI on PATH (test prints a clear `SKIP — claude CLI not on server's PATH` message if the server's `ready` frame reports `claude_live: false`, instead of failing).

**Acceptance:** `python3 server/tests/test_memory_roundtrip.py` prints a green ✓ or red ✗.

---

### 🎁 CODEX-TASK-03 — Mobile companion notification mockup  (still open)
**File:** Create `mobile/mockup/index.html` (single self-contained HTML)
**Why:** Sterling wants to feel what villager "texts" feel like, even if the actual mobile app is months out.
**Spec:**
- iOS-style lock screen with 3 stacked notifications, each "from" a different villager.
- Use the palette from `docs/ART_DIRECTION.md` (CSS variables). The hex values are also in `game/web/index.html` for reference.
- Sample messages in the villagers' voices — pull from `server/ai/personalities.py` to capture their voice:
  - **Maple** (gardener, warm + sensory): something about a flower opening or the morning weather
  - **Bramble** (dry bookworm): something clipped and bookish, secretly fond
  - **Sage** (quiet elder): a single gentle metaphorical line
- Soft drop shadows, rounded corners, a faux phone-frame background, a soft time-of-day gradient behind the notifications.
- Pure HTML/CSS — no JS framework.

**Acceptance:** Opens in a browser and looks like a real lockscreen, not a wireframe. Sterling should smile when he sees it.

---

### 🎁 CODEX-TASK-04 — Polish the village environment 🔓 UNBLOCKED
**File:** `game/web/scene.js` (created by Claude Code — open and extend)
**Why:** Current geometry is decent for a vertical slice but a bit sparse. Make it feel more cozy and lived-in.
**Spec:**
- Fountain water already has a static disk — replace it with a small animated ripple (vertex displacement on a circle geometry, sin(t + r))
- Add 2–3 cherry trees (`cherry: true` already exists in `addTree`) clustered around the player house and town square — they currently spawn randomly
- Add flower patches around each cottage and along the paths (small instanced quads or just tiny colored boxes — see `addGardenPatch` for the inspiration)
- A handful of porcelain-white daisies in the grass (cheap: small white scaled spheres)
- A simple wood fence around the garden patch — driftwood-colored posts every meter or so, 0.8m tall
- Keep total draw calls reasonable. Use `THREE.InstancedMesh` for repeated tiny props if it gets above ~300.

**Acceptance:** Walking around the village feels like a place, not a diagram. Match the palette exported as `PALETTE` from `scene.js`.

**Coordination:** Don't break `villagerMeshes` keying or the `spawnVillager`/`step`/`setSky` exports — `main.js` depends on them.

---

### 🎁 CODEX-TASK-05 — Web demo README  (still open)
**File:** Create `game/web/README.md`
**Why:** Sterling will want to remember how to run the demo and what's where.
**Spec:**
- Quick-start: how to serve the HTML (`python -m http.server 8000` from `game/web/`), open `http://localhost:8000`.
- Controls cheat sheet (WASD, E to talk, mouse-drag, etc — pull from `docs/GAME_DESIGN.md`).
- Architecture note: client talks to AI server at `ws://localhost:8765/ws`. Without the server, the village still renders from a fallback in `main.js#seedPlaceholderVillagers`.
- File map: index.html (shell + CSS), scene.js (3D world), main.js (input + networking + UI).
- Troubleshooting: blank screen → check browser console, "server offline" indicator → start `uvicorn` first.

**Acceptance:** Short, scannable, gets a confused future-Sterling unstuck in under 30 seconds.

---

### 🎁 NEW CODEX-TASK-06 — Mood state machine
**File:** `server/ai/mood.py` (new)
**Why:** `docs/AI_ARCHITECTURE.md` specifies a mood FSM per villager but nothing implements it yet. Right now every villager's mood is just their default. Mood is one of the three biggest levers that makes them feel alive (the others are memory and voice — both already wired).
**Spec:**
- Module-level constant `MOODS = ["content", "happy", "excited", "melancholy", "anxious", "irritated", "peaceful", "lonely"]`.
- `class MoodTracker:` with `current_mood(villager_id) -> str`, `nudge(villager_id, mood: str, weight: float)`, `tick(villager_id, world_state, personality)`.
- On each `tick`, mood drifts toward the villager's `mood_baseline_by_time[time_of_day]` slowly, with a small random nudge among 1–2 adjacent moods.
- Persists current mood per villager in `relationships(villager_id, target_id='self').mood` so it survives restart (the column already exists — see `server/ai/memory.py`).
- Wire into `ConversationEngine.build_context` so the dynamic system block reflects current mood instead of always reading "content".

**Acceptance:** With Maple registered, after `mood.tick("maple", world, MAPLE)` is called repeatedly during 'morning', her mood lands at "happy" or "peaceful" most of the time, not "irritated". A short pytest-style assert script verifies this.

---

### 🎁 NEW CODEX-TASK-07 — Make the time-of-day go by faster
**File:** `server/world/state.py`
**Why:** Default day length is 1 real hour. For the demo we want the time-of-day to advance noticeably during a 5-minute play session so Sterling can see sky transitions.
**Spec:**
- Allow `DAY_LENGTH_SECONDS` to be read from environment variable `HOLLOW_DAY_LENGTH_SECONDS` (default still 3600).
- Update the top-level README to mention: `export HOLLOW_DAY_LENGTH_SECONDS=300` for "demo speed" (1 in-game day every 5 minutes).
- Verify the WorldState picks it up at construction.

**Acceptance:** Setting the env var and restarting the server visibly speeds up the HUD clock at `http://localhost:8765/world`.

---

## For Claude Code

- ✅ Design docs filled out
- ✅ Blackboard created
- ✅ Server: memory, world, events, conversation, FastAPI/WS API
- ✅ 4 MVP villager personalities defined with rich seed prompts
- ✅ Three.js web client: scene + controls + chat UI + Gamepad
- ✅ Verified end-to-end roundtrip with curl + ws smoke test
- ✅ Top-level README has a "Running the demo" section
- ✅ Pivoted server from Anthropic SDK to `claude` CLI (Sterling's subscription instead of metered API)
- ⏭ Tomorrow morning when Sterling wakes: walk him through the demo, address any rough edges, queue up the next milestone (mood FSM if Codex hasn't picked it up, audio ambience, polish on the Three.js scene)

---

## Completed

- **2026-05-14 evening** — `docs/GAME_DESIGN.md` filled out: world layout, core loop, controls, MVP scope. *(Claude Code)*
- **2026-05-14 evening** — `docs/AI_ARCHITECTURE.md` filled out: personality schema, SQLite memory schema, prompt assembly, mood FSM, mobile notification plan. *(Claude Code)*
- **2026-05-14 evening** — `docs/ART_DIRECTION.md` filled out: full palette with hex values, form language, shader plan for both engines. *(Claude Code)*
- **2026-05-14 evening** — `BLACKBOARD.md` created with 5 starter tasks for Codex. *(Claude Code)*
- **2026-05-14 evening** — Main worktree now has a Godot 4 foundation slice per the direct Codex prompt: Godot scene/player/villager, FastAPI server, SQLite memory, Margot personality, `/ws` + `/ws/conversation` endpoints, and a memory roundtrip smoke test. *(Codex)*
- **2026-05-14 late evening** — Server: `server/ai/personality.py` (Personality dataclass + to_system_prompt with prompt-cache target), `server/ai/personalities.py` (Maple/Bramble/Clover/Sage rich seeds), `server/ai/memory.py` (full SQLite schema, salience-weighted recall, relationships, gifts, conversation summaries), `server/world/state.py` (accelerated clock, time-of-day, sky color, light intensity), `server/world/events.py` (async pub/sub bus), `server/ai/conversation.py` (Claude streaming with ephemeral cache on personality block, end-of-conversation summary + memory extraction, null-client fallback for no-API-key dev), `server/api/server.py` (FastAPI app, REST + WS protocol). End-to-end WS roundtrip tested with `python3 -c websockets`. *(Claude Code)*
- **2026-05-14 late evening** — Web client: `game/web/index.html` (single-file shell with full cottagecore CSS, name modal, HUD, streaming chat panel, gift menu), `game/web/scene.js` (Three.js world: terrain, paths, two cottages, garden, hill, fountain, 16 trees, dot-and-blush villagers with billboarded labels), `game/web/main.js` (WASD + mouse-drag camera + Switch-Pro Gamepad, WebSocket client, streaming chat ingestion, time-of-day-driven sky updates). *(Claude Code)*
- **2026-05-14 late evening** — `requirements.txt`, `server/data/.gitkeep`, README "Running the demo" section. *(Claude Code)*
- **2026-05-14 late evening** — Pivoted villager intelligence from Anthropic SDK to `claude` CLI subprocess. Rewrote `server/ai/conversation.py` to shell out via `subprocess.run` (wrapped in `asyncio.to_thread`), removed `anthropic` from `requirements.txt`, dropped all `ANTHROPIC_API_KEY` references in README and CLAUDE.md. WS protocol unchanged. *(Claude Code)*

---

## Blocked / Needs Decision

(nothing right now — Codex direction question resolved above, see Decision Log)

---

## Coordination notes

- **Don't both touch the same file at the same time.** If you (Codex) want to edit a file Claude Code is mid-stream on, leave a note here and pick a different task.
- **All paths are repo-relative.** Repo root is wherever `README.md` and `CLAUDE.md` live (this worktree's root).
- **The `claude` CLI must be installed and on the PATH** for the server to give real villager responses. Without it, the server still boots and the demo is playable (placeholder responses). Auth is handled by the CLI — no `ANTHROPIC_API_KEY` needed; Sterling's Claude subscription powers the villagers.
- **Python is 3.9-compatible.** Local Python is 3.9.6 — modules use `from __future__ import annotations` so `str | Path` and other 3.10+ syntax still works at runtime. Don't delete those future imports unless you've confirmed the runtime is 3.10+.
- **Style:** Python is 4-space. JS is 2-space, ES modules, no build step — the demo runs from a static file server.
- **Voice and tone everywhere:** cozy, not chirpy. Calm verbs. The codebase itself should feel like the game.
