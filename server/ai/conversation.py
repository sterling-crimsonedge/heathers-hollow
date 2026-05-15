"""Conversation engine — uses the Claude Agent SDK for villager turns.

We use the Claude Code SDK (`claude-code-sdk`) so each villager call goes
through Sterling's Claude subscription rather than the metered Anthropic
API. The SDK handles auth via OAuth / keychain; no API key needed.

Each call:
  - Sets a custom `system_prompt` (the villager's persona + context) that
    REPLACES the default system prompt, so CLAUDE.md / hooks / agents do
    NOT contaminate the villager's persona.
  - Sets `allowed_tools=[]` (no tools — the villager just talks, never
    edits files or runs shell commands).

If the `claude-code-sdk` package is not installed, we degrade gracefully
to a null client that returns a friendly in-character placeholder so the
demo is still playable. See `_NullClient`.

We don't get true token-by-token streaming from the SDK in this mode, but
the WS protocol stays the same — we chunk the response post-hoc so the
chat UI still pours text out word-by-word.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import AsyncIterator, Optional

from .memory import Memory, MemoryStore
from .personality import Personality
from ..world.state import WorldState


# Model alias the Claude CLI understands ("sonnet" -> latest Sonnet)
MAIN_MODEL = "sonnet"
SUMMARY_MODEL = "haiku"

# How long to wait for a single villager turn before giving up.
CLAUDE_TIMEOUT_SECONDS = 60

# Chunk size when synthesizing streaming output so the WS doesn't fire
# a hundred tiny messages per word.
STREAM_CHUNK_CHARS = 6


@dataclass
class TurnContext:
    villager: Personality
    conversation_id: int
    world: WorldState
    player_name: Optional[str]
    recent_memories: list[Memory]
    recent_summaries: list[str]
    relationship_affection: int
    relationship_familiarity: int
    gift_history: list[dict]


# --- prompt assembly ---------------------------------------------------------

def build_static_persona_block(villager: Personality) -> str:
    """The stable persona portion — same every call for a given villager."""
    return villager.to_system_prompt()


def build_dynamic_context_block(ctx: TurnContext) -> str:
    """Mood, world, memories, relationship — changes per turn."""
    lines: list[str] = []

    lines.append("Current moment in the village:")
    lines.append(f"  {ctx.world.context_for_prompt()}")
    lines.append("")

    lines.append("How you currently feel about the player:")
    lines.append(f"  {_describe_relationship(ctx.relationship_affection, ctx.relationship_familiarity)}")
    if ctx.player_name:
        lines.append(f"  Their name is {ctx.player_name}.")
    lines.append("")

    if ctx.recent_memories:
        lines.append("Things you remember that might be relevant right now:")
        for m in ctx.recent_memories:
            lines.append(f"  - ({m.kind}) {m.content}")
        lines.append("")

    if ctx.recent_summaries:
        lines.append("Recent times you've talked with this player:")
        for s in ctx.recent_summaries:
            lines.append(f"  - {s}")
        lines.append("")

    if ctx.gift_history:
        lines.append("Recent gifts they've given you:")
        for g in ctx.gift_history[:5]:
            lines.append(f"  - {g['item']}")
        lines.append("")

    lines.append(
        "Speak naturally as yourself. Don't list your memories — let what's "
        "relevant color what you say. If nothing in particular jumps out, just "
        "be present in this moment with them. Respond with ONLY your spoken "
        "reply — no narration, no 'Maple says:', no quotation marks around the "
        "whole thing. One short paragraph at most."
    )
    return "\n".join(lines)


def build_transcript_block(history: list[dict], villager_name: str) -> str:
    """Serialize prior conversation turns so the stateless call sees context."""
    if not history:
        return ""
    lines = ["Earlier in this conversation today:"]
    for m in history:
        if m["role"] == "player":
            lines.append(f"  THEM: {m['content']}")
        else:
            lines.append(f"  YOU ({villager_name}): {m['content']}")
    return "\n".join(lines)


def assemble_system_prompt(ctx: TurnContext, history: list[dict]) -> str:
    """Full system prompt for one villager turn."""
    parts = [
        build_static_persona_block(ctx.villager),
        "",
        build_dynamic_context_block(ctx),
    ]
    transcript = build_transcript_block(history, ctx.villager.name)
    if transcript:
        parts.append("")
        parts.append(transcript)
    return "\n".join(parts)


def _describe_relationship(affection: int, familiarity: int) -> str:
    """Translate numeric scores into a phrase the model can feel."""
    if familiarity < 5:
        return "You barely know them yet. Polite, curious, a little reserved."
    if affection >= 50:
        return "You are very fond of them. They have become a real part of your days here."
    if affection >= 20:
        return "You like them. They feel like a friend, even if a new one."
    if affection >= -5:
        return "Neutral, friendly — a neighbor you don't dislike."
    if affection >= -30:
        return "You have some reservations about them. You're not warm, exactly."
    return "You don't really care for them. You're polite, but distant."


# --- Claude Agent SDK client -------------------------------------------------

class _NullClient:
    """Used when the `claude-code-sdk` isn't installed — keeps the demo running."""

    available = False

    async def call(self, *, system_prompt: str, user_prompt: str, model: str = MAIN_MODEL) -> str:
        return (
            "(There's a soft pause. A small breeze moves through the cherry "
            "blossoms. The villager smiles, but no words come — perhaps the "
            "Claude Code SDK isn't installed on this machine yet.)"
        )


class ClaudeSDKClient:
    """Calls Claude via the Agent SDK (`claude-code-sdk`).

    Uses the SDK's `query()` async iterator with:
      - `system_prompt` to replace the default system prompt
      - `allowed_tools=[]` to disable all tools
      - `max_turns=1` so the model responds once and stops

    Auth goes through the Claude subscription (OAuth/keychain) — no API
    key needed.
    """

    available = True

    async def call(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str = MAIN_MODEL,
    ) -> str:
        from claude_code_sdk import query, ClaudeCodeOptions, AssistantMessage, TextBlock

        options = ClaudeCodeOptions(
            system_prompt=system_prompt,
            model=model,
            allowed_tools=[],      # no tool use — villager just talks
            max_turns=1,           # single response, no agentic loop
        )

        result_parts: list[str] = []
        try:
            async for message in asyncio.wait_for(
                _collect_sdk_messages(query(prompt=user_prompt, options=options), result_parts),
                timeout=CLAUDE_TIMEOUT_SECONDS,
            ):
                pass  # collection happens inside the helper
        except asyncio.TimeoutError:
            print(f"[claude-sdk] timeout after {CLAUDE_TIMEOUT_SECONDS}s")
            return ""
        except Exception as e:
            print(f"[claude-sdk] error: {e}")
            return ""

        return "".join(result_parts).strip()


async def _collect_sdk_messages(aiter, parts: list[str]):
    """Walk the SDK async iterator, pulling text blocks into `parts`."""
    from claude_code_sdk import AssistantMessage, TextBlock

    async for message in aiter:
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    parts.append(block.text)
        yield message


# --- conversation engine -----------------------------------------------------

class ConversationEngine:
    """High-level interface: handles state, memory writes, Claude SDK calls."""

    def __init__(self, store: MemoryStore, world: WorldState):
        self.store = store
        self.world = world

        try:
            import claude_code_sdk  # noqa: F401
            print("[conversation] Claude Code SDK available (subscription auth).")
            self.client: ClaudeSDKClient | _NullClient = ClaudeSDKClient()
        except ImportError:
            print("[conversation] `claude-code-sdk` not installed — using null client (canned responses).")
            print("[conversation] Install with: pip install claude-code-sdk")
            self.client = _NullClient()

    @property
    def using_real_claude(self) -> bool:
        return self.client.available

    def begin(self, villager: Personality, player_id: str = "player") -> int:
        return self.store.start_conversation(villager.id, player_id)

    async def end(self, villager: Personality, conversation_id: int) -> Optional[str]:
        """Close conversation, write summary + extracted memories."""
        messages = self.store.get_messages(conversation_id)
        if not messages:
            self.store.end_conversation(conversation_id, summary=None)
            return None

        summary: Optional[str] = None
        memories: list[dict] = []

        if self.client.available:
            try:
                raw = await self._summarize(villager, messages)
            except Exception as e:
                print(f"[conversation] summarize failed: {e}")
                raw = ""

            if raw:
                parsed = _safe_parse_json(raw)
                if isinstance(parsed, dict):
                    summary = parsed.get("summary")
                    memories = parsed.get("memories") or []

        # Fallback summary from last player message
        if not summary:
            for m in reversed(messages):
                if m["role"] == "player":
                    summary = f"Talked with the player about: {m['content'][:80]}"
                    break

        self.store.end_conversation(conversation_id, summary=summary)

        for mem in memories:
            try:
                content = str(mem.get("content", "")).strip()
                if not content:
                    continue
                self.store.add_memory(
                    villager.id,
                    kind=str(mem.get("kind", "fact")),
                    content=content,
                    participants=["player", villager.id],
                    salience=float(mem.get("salience", 0.5)),
                )
            except Exception as e:
                print(f"[conversation] memory write skipped: {e}")

        self.store.update_relationship(
            villager.id, "player",
            familiarity_delta=1,
            affection_delta=1,
        )
        return summary

    async def _summarize(self, villager: Personality, messages: list[dict]) -> str:
        transcript = "\n".join(f"{m['role'].upper()}: {m.get('content', '')}" for m in messages)
        system = (
            f"You help maintain {villager.name}'s long-term memory in a cozy "
            "village life-sim. Given a short conversation transcript between the "
            "player and the villager, produce a JSON object with two fields:\n"
            '  "summary": one warm sentence summarizing the conversation from '
            "the villager's POV.\n"
            '  "memories": an array of 0 to 4 short third-person facts/opinions '
            "the villager should remember long-term about the player. Each item "
            'must include "content" (string), "kind" (one of: fact, opinion, '
            'episode), and "salience" (0.0-1.0).\n'
            "Respond with ONLY the JSON object — no prose around it, no markdown "
            "code fences."
        )
        return await self.client.call(
            system_prompt=system,
            user_prompt=transcript,
            model=SUMMARY_MODEL,
        )

    def build_context(
        self, villager: Personality, conversation_id: int, *, query: str = ""
    ) -> TurnContext:
        rel = self.store.get_relationship(villager.id, "player")
        memories = self.store.recall(villager.id, query=query, limit=8)
        summaries = self.store.recent_conversation_summaries(villager.id, limit=3)
        gifts = self.store.gift_history(villager.id)
        name = self.store.get_player_name()
        return TurnContext(
            villager=villager,
            conversation_id=conversation_id,
            world=self.world,
            player_name=name,
            recent_memories=memories,
            recent_summaries=summaries,
            relationship_affection=rel.affection,
            relationship_familiarity=rel.familiarity,
            gift_history=gifts,
        )

    async def _generate_reply(
        self,
        villager: Personality,
        conversation_id: int,
        user_prompt: str,
        *,
        query: str = "",
    ) -> str:
        """Single source of truth for villager generation. Returns full text."""
        ctx = self.build_context(villager, conversation_id, query=query or user_prompt)
        history = self.store.get_messages(conversation_id)
        system_prompt = assemble_system_prompt(ctx, history)
        return await self.client.call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

    async def respond_streaming(
        self,
        villager: Personality,
        conversation_id: int,
        player_message: str,
    ) -> AsyncIterator[str]:
        """Yield reply chunks; persist the player message + final reply."""
        self.store.add_message(conversation_id, "player", player_message)
        self.store.add_memory(
            villager.id,
            kind="utterance",
            content=f"Player said: {player_message}",
            participants=["player", villager.id],
            salience=0.4,
        )

        text = ""
        try:
            text = await self._generate_reply(villager, conversation_id, player_message)
        except Exception as e:
            print(f"[conversation] generate_reply failed: {e}")
            text = f"({villager.name} seems lost in thought for a moment.)"

        if not text:
            text = f"({villager.name} smiles, but doesn't seem to know what to say just now.)"

        async for chunk in _chunk_for_streaming(text):
            yield chunk

        self.store.add_message(conversation_id, "villager", text)

    async def respond_blocking(
        self,
        villager: Personality,
        conversation_id: int,
        player_message: str,
    ) -> str:
        chunks: list[str] = []
        async for ch in self.respond_streaming(villager, conversation_id, player_message):
            chunks.append(ch)
        return "".join(chunks).strip()

    async def greeting(
        self, villager: Personality, conversation_id: int
    ) -> AsyncIterator[str]:
        """Generate an opening line from the villager (no player turn yet)."""
        prompt = "[The player has just walked up and is looking at you. Greet them naturally.]"
        text = ""
        try:
            text = await self._generate_reply(
                villager, conversation_id, prompt, query="hello greeting"
            )
        except Exception as e:
            print(f"[conversation] greeting failed: {e}")
            text = f"({villager.name} looks up and gives you a small wave.)"

        if not text:
            text = f"({villager.name} smiles in greeting.)"

        async for chunk in _chunk_for_streaming(text):
            yield chunk

        self.store.add_message(conversation_id, "villager", text)

    async def record_gift(
        self,
        villager: Personality,
        conversation_id: Optional[int],
        item: str,
    ) -> AsyncIterator[str]:
        """Player gives a gift. Villager reacts. Yields reaction text."""
        liked = item.lower() in {l.lower() for l in villager.likes}
        disliked = item.lower() in {d.lower() for d in villager.dislikes}

        affect = 5 if liked else (-3 if disliked else 1)
        self.store.update_relationship(
            villager.id, "player",
            affection_delta=affect, familiarity_delta=1,
        )

        self.store.log_gift(villager.id, "player", item)
        self.store.add_memory(
            villager.id,
            kind="episode",
            content=f"The player gave me a {item}.",
            participants=["player", villager.id],
            salience=0.7 if liked or disliked else 0.5,
            emotional_valence=(0.6 if liked else (-0.4 if disliked else 0.1)),
            tags=["gift"],
        )

        conv_id = conversation_id or self.begin(villager)
        synthetic = f"[The player has just offered you a {item}. React in your own voice.]"
        self.store.add_message(conv_id, "player", synthetic)

        text = ""
        try:
            text = await self._generate_reply(
                villager, conv_id, synthetic, query=f"gift {item}"
            )
        except Exception as e:
            print(f"[conversation] gift react failed: {e}")
            text = f"({villager.name} accepts the {item} quietly.)"

        if not text:
            text = f"({villager.name} turns the {item} over in their hands, thoughtful.)"

        async for chunk in _chunk_for_streaming(text):
            yield chunk

        self.store.add_message(conv_id, "villager", text)


# --- helpers -----------------------------------------------------------------

async def _chunk_for_streaming(text: str) -> AsyncIterator[str]:
    """Yield the response in small chunks with tiny delays so the WS protocol
    still produces a streaming feel even though the SDK returns the full
    text in one shot."""
    if not text:
        return
    for i in range(0, len(text), STREAM_CHUNK_CHARS):
        yield text[i : i + STREAM_CHUNK_CHARS]
        # ~16ms between chunks → about 60 chunks/sec, plenty smooth
        await asyncio.sleep(0.016)


def _safe_parse_json(raw: str):
    """Best-effort JSON parse. Strips markdown fences if present."""
    s = raw.strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s.lower().startswith("json"):
            s = s[4:]
        s = s.strip()
    try:
        return json.loads(s)
    except Exception:
        first = s.find("{")
        last = s.rfind("}")
        if first >= 0 and last > first:
            try:
                return json.loads(s[first : last + 1])
            except Exception:
                return None
        return None
