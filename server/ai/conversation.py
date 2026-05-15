"""Conversation engine for AI-powered villagers."""

from __future__ import annotations

import asyncio
import json
import os
import re
import uuid
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from server.ai.memory import MemoryRecord, MemoryStore
from server.ai.mood import MoodTracker
from server.ai.personality import Personality, PersonalityStore
from server.world.events import EventLog, VillageEvent
from server.world.inventory import normalize_gift_item
from server.world.state import WorldState


POSITIVE_WORDS = {"thanks", "thank", "kind", "love", "beautiful", "sweet", "friend", "happy", "nice"}
NEGATIVE_WORDS = {"hate", "annoying", "stupid", "ugly", "mean", "bad", "awful"}

# HH-062 legacy global "loved" rubric. When a villager's personality JSON does
# not supply `loved_tags`, this set is used as a fallback so pre-HH-062 configs
# keep their original gift behaviour. New configs should supply explicit
# `loved_tags` so each villager has a distinct rubric — see
# `_loved_tags_for()` and the personality JSONs under server/data/personalities/.
DEFAULT_LOVED_TAGS: frozenset[str] = frozenset(
    {"flower", "porcelain", "tea", "handmade", "garden vegetables"}
)
SUPPORTED_LLM_PROVIDERS = {"auto", "fallback", "ollama", "anthropic"}
DEFAULT_LLM_PROVIDER = "auto"
OLLAMA_DEFAULT_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_DEFAULT_MODEL = "llama3.2"
OLLAMA_DEFAULT_TIMEOUT_SECONDS = 20.0

# HH-006 talk-path tuning caps (see docs/AI_ARCHITECTURE.md "Mood And Relationship Tuning Rules").
# These caps prevent slot-machine warmth and protect trust as the slow, precious score.
TALK_AFFECTION_DAILY_CAP = 2
TALK_TRUST_DAILY_CAP = 1
TALK_NEGATIVE_DAILY_CAP = 1
# Personal-disclosure conversation turns hit mood harder than small talk.
TALK_MOOD_NUDGE_DEFAULT = 0.45
TALK_MOOD_NUDGE_PERSONAL = 0.6

# HH-006 gift-path tuning (see docs/AI_ARCHITECTURE.md "Mood And Relationship Tuning Rules").
# Gift preferences are ordered from coldest to warmest; the first gift a villager
# receives from a player gets bumped up one tier on this ladder so the moment
# feels like a relationship event regardless of taste match.
GIFT_PREFERENCE_LADDER: tuple[str, ...] = ("disliked", "neutral", "liked", "loved")
# Repeated-gift dampening: if the same item_id has been gifted this villager by
# this player within the trailing window, halve the affection delta on the
# triggering gift (and any further repeats) toward zero. Mood, memory writes,
# and trust deltas are intentionally unaffected so the moment still registers.
GIFT_REPEAT_WINDOW_DAYS = 3
GIFT_REPEAT_DAMPEN_THRESHOLD = 2


class ConversationEngine:
    """Builds prompts, calls the configured LLM provider, and persists memory."""

    def __init__(
        self,
        *,
        memory_store: MemoryStore,
        personality_store: PersonalityStore,
        world_state: WorldState,
        event_log: EventLog,
        ollama_transport: Callable[[str, dict[str, Any], float], dict[str, Any]] | None = None,
    ) -> None:
        self.memory_store = memory_store
        self.personality_store = personality_store
        self.world_state = world_state
        self.event_log = event_log
        self.mood_tracker = MoodTracker(memory_store)
        self._ollama_transport = ollama_transport or self._post_ollama_chat

    def llm_provider_status(self) -> dict[str, Any]:
        """Return a public, non-secret summary of provider selection."""
        configured = self._configured_llm_provider()
        provider_order = self._llm_provider_order(configured)
        return {
            "configured": configured,
            "active_order": provider_order or ["fallback"],
            "anthropic": {
                "configured": bool(os.getenv("ANTHROPIC_API_KEY")),
                "model": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
            },
            "ollama": {
                "base_url": self._ollama_base_url(),
                "model": self._ollama_model(),
                "timeout_seconds": self._ollama_timeout_seconds(),
            },
        }

    async def handle_player_message(
        self,
        *,
        player_id: str,
        villager_id: str,
        text: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        context = context or {}
        personality = self.personality_store.load(villager_id)
        self.memory_store.upsert_villager(villager_id, personality.display_name, str(personality.config_path))

        relationship = self.memory_store.get_relationship(
            villager_id,
            player_id,
            personality.starting_relationship(player_id),
        )
        player_memories = self.memory_store.get_relevant_memories(villager_id, player_id)
        social_memories, social_relationships = self._social_context_for_text(personality, text)
        memories = self._merge_memories(player_memories, social_memories, limit=10)
        world = self.world_state.snapshot()
        conversation_id = str(uuid.uuid4())

        self.memory_store.add_conversation_turn(
            conversation_id,
            villager_id,
            player_id,
            speaker=player_id,
            text=text,
            metadata={"context": context},
        )

        baseline_mood = self.mood_tracker.tick(villager_id, world, personality)
        mood = self._choose_mood(text, relationship, baseline_mood)
        if mood != baseline_mood:
            nudge_weight = (
                TALK_MOOD_NUDGE_PERSONAL if self._looks_personal(text) else TALK_MOOD_NUDGE_DEFAULT
            )
            self.mood_tracker.nudge(villager_id, self._server_mood_to_tracker_mood(mood), nudge_weight)
        memories_used = [memory.id for memory in memories]
        social_memory_ids = [
            memory.id for memory in memories
            if memory.kind == "villager_interaction"
        ]
        reply = await self._generate_reply(
            personality=personality,
            player_id=player_id,
            player_text=text,
            relationship=relationship,
            memories=memories,
            social_relationships=social_relationships,
            world=world,
            context=context,
            mood=mood,
        )

        self.memory_store.add_conversation_turn(
            conversation_id,
            villager_id,
            player_id,
            speaker=villager_id,
            text=reply,
            metadata={"mood": mood, "memories_used": memories_used},
        )

        memory_id = self.memory_store.add_memory(
            villager_id,
            kind="conversation",
            subject_id=player_id,
            text=self._summarize_exchange(player_id, personality.display_name, text, reply),
            salience=self._estimate_salience(text),
            emotion=mood,
            metadata={
                "conversation_id": conversation_id,
                "player_text": text,
                "villager_reply": reply,
                "memories_used": memories_used,
                "social_memory_ids": social_memory_ids,
                "world": world,
                "context": context,
            },
        )

        proposed_affection = self._affection_delta(text)
        proposed_trust = 1 if self._looks_personal(text) else 0
        capped_affection, capped_trust, talk_meta_update = self._apply_talk_caps(
            current_relationship=relationship,
            proposed_affection=proposed_affection,
            proposed_trust=proposed_trust,
            world_day=int(world.get("day", 1) or 1),
        )
        relationship = self.memory_store.update_relationship(
            villager_id,
            player_id,
            affection_delta=capped_affection,
            trust_delta=capped_trust,
            familiarity_delta=1,
            metadata={
                "last_mood": mood,
                "last_memory_id": memory_id,
                **talk_meta_update,
            },
        )

        event = VillageEvent(
            kind="conversation",
            actor_id=player_id,
            target_id=villager_id,
            location=str(context.get("location", "unknown")),
            summary=f"{player_id} talked with {personality.display_name}.",
            metadata={
                "memory_id": memory_id,
                "mood": mood,
                "memories_used": memories_used,
                "social_memory_ids": social_memory_ids,
            },
        )
        self.event_log.publish(event)
        self.memory_store.add_event(
            kind=event.kind,
            actor_id=event.actor_id,
            target_id=event.target_id,
            location=event.location,
            summary=event.summary,
            metadata=event.metadata,
        )

        return {
            "type": "villager_reply",
            "villager_id": villager_id,
            "display_name": personality.display_name,
            "text": reply,
            "mood": mood,
            "relationship": self._public_relationship(relationship),
            "memories_used": memories_used,
            "memory_id": memory_id,
            "world": world,
        }

    async def handle_gift(
        self,
        *,
        player_id: str,
        villager_id: str,
        item: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        context = context or {}
        item = normalize_gift_item(item)
        personality = self.personality_store.load(villager_id)
        self.memory_store.upsert_villager(villager_id, personality.display_name, str(personality.config_path))
        current_relationship = self.memory_store.get_relationship(
            villager_id,
            player_id,
            personality.starting_relationship(player_id),
        )
        current_metadata = dict(current_relationship.get("metadata") or {})
        item_name = str(item.get("display_name") or item.get("item_id") or "something")
        item_id = str(item.get("item_id") or "").strip().lower()
        item_tags = {str(tag).lower() for tag in item.get("tags", [])}
        item_category = str(item.get("category", "")).lower()
        base_preference = self._gift_preference(personality, item_category, item_tags)
        world_day = int(self.world_state.snapshot().get("day", 1) or 1)

        # HH-006 first-of-kind gift bonus: the first gift any player gives a
        # villager bumps the preference up one tier ("the first gift is a
        # relationship event regardless of what it was"). Disliked → neutral,
        # neutral → liked, liked → loved, loved stays loved.
        first_gift_done = bool(current_metadata.get("gift_first_done"))
        first_of_kind_bonus = not first_gift_done
        preference = (
            self._bump_gift_preference(base_preference) if first_of_kind_bonus else base_preference
        )

        mood = {
            "loved": "delighted",
            "liked": "warm",
            "disliked": "melancholy",
        }.get(preference, "shy")
        # HH-006: disliked gifts should hurt the villager's feelings, not redirect them
        # into anxious territory. A softer tracker nudge (0.35) lets melancholy register
        # without dominating the mood field on the next several ticks.
        gift_nudge_weight = {
            "loved": 2.5,
            "liked": 0.7,
            "disliked": 0.35,
            "neutral": 0.45,
        }.get(preference, 0.55)
        self.mood_tracker.nudge(villager_id, self._server_mood_to_tracker_mood(mood), gift_nudge_weight)
        # HH-006 mood pin: a loved gift should genuinely *land*. The mood-score
        # nudge above is heavy (2.5), but a single noisy baseline tick on a
        # short demo day can still wash it out. Pin `excited` for the next two
        # in-game hours so the villager visibly carries the loved-gift mood
        # through Heather's immediate follow-up actions. Liked/neutral/disliked
        # gifts are *not* pinned — the rubric stays "loved gifts feel biggest,
        # disliked gifts are a small lingering note" per docs/AI_ARCHITECTURE.md.
        if preference == "loved":
            self.mood_tracker.pin(
                villager_id,
                self._server_mood_to_tracker_mood(mood),
                world=self.world_state,
            )

        affection_delta = {"loved": 5, "liked": 2, "neutral": 1, "disliked": -1}[preference]
        trust_delta = 2 if preference in {"loved", "liked"} else 0

        # HH-006 repeated-gift dampening: count how many times this player has
        # already given this villager the same item_id within the trailing
        # GIFT_REPEAT_WINDOW_DAYS in-game days. On the threshold-th repeat
        # (default the 3rd same-item gift in 3 days) and every repeat after,
        # halve the affection delta toward zero so Dusty-Rose-spam is not
        # optimal play. Mood, memory writes, and trust deltas are intentionally
        # left alone — the moment still registers; it just doesn't pay the same.
        recent_gifts = self._coerce_recent_gifts(
            current_metadata.get("recent_gifts"), world_day=world_day
        )
        repeat_count_in_window = sum(
            1 for entry in recent_gifts if entry.get("item_id") == item_id
        ) if item_id else 0
        repeat_gift_dampened = (
            bool(item_id) and repeat_count_in_window >= GIFT_REPEAT_DAMPEN_THRESHOLD
        )
        if repeat_gift_dampened:
            # Halve toward zero: +5 → +2, +2 → +1, +1 → 0, -1 → 0. Trust is left
            # alone (the gift still earned closeness, just not a stat reward).
            affection_delta = int(affection_delta / 2)

        if item_id:
            recent_gifts.append({"item_id": item_id, "day": int(world_day)})
        memory_text = f"{player_id} gave {personality.display_name} {item_name}. {personality.display_name} felt {mood} about it."

        memory_id = self.memory_store.add_memory(
            villager_id,
            kind="gift",
            subject_id=player_id,
            text=memory_text,
            salience=80 if preference == "loved" else 60,
            emotion=mood,
            metadata={
                "item": item,
                "preference": preference,
                "context": context,
                "base_preference": base_preference,
                "first_of_kind_bonus": first_of_kind_bonus,
                "repeat_gift_dampened": repeat_gift_dampened,
                "repeat_count_in_window": repeat_count_in_window,
            },
        )
        relationship = self.memory_store.update_relationship(
            villager_id,
            player_id,
            affection_delta=affection_delta,
            trust_delta=trust_delta,
            familiarity_delta=1,
            metadata={
                "last_gift": item_name,
                "last_gift_preference": preference,
                "last_gift_base_preference": base_preference,
                "last_gift_first_of_kind": first_of_kind_bonus,
                "last_gift_repeat_dampened": repeat_gift_dampened,
                "last_memory_id": memory_id,
                "gift_first_done": True,
                "recent_gifts": recent_gifts,
            },
        )

        event = VillageEvent(
            kind="gift",
            actor_id=player_id,
            target_id=villager_id,
            location=str(context.get("location", "unknown")),
            summary=f"{player_id} gave {personality.display_name} {item_name}.",
            metadata={
                "memory_id": memory_id,
                "preference": preference,
                "mood": mood,
                "item_id": str(item.get("item_id") or ""),
                "item_name": item_name,
                "base_preference": base_preference,
                "first_of_kind_bonus": first_of_kind_bonus,
                "repeat_gift_dampened": repeat_gift_dampened,
            },
        )
        self.event_log.publish(event)
        self.memory_store.add_event(
            kind=event.kind,
            actor_id=event.actor_id,
            target_id=event.target_id,
            location=event.location,
            summary=event.summary,
            metadata=event.metadata,
        )

        if preference == "loved":
            reply = f"Oh, {item_name}... that's so thoughtful. I'll keep it somewhere safe, where the morning light can find it."
        elif preference == "liked":
            reply = f"Thank you. {item_name} feels like the sort of little thing that makes a day softer."
        elif preference == "disliked":
            reply = f"Oh. Thank you for thinking of me, truly. I may need a moment to find the right place for it."
        else:
            reply = f"Thank you. I'll remember that you brought me {item_name}."

        return {
            "type": "villager_reply",
            "villager_id": villager_id,
            "display_name": personality.display_name,
            "text": reply,
            "mood": mood,
            "relationship": self._public_relationship(relationship),
            "memories_used": [memory_id],
            "memory_id": memory_id,
            "world": self.world_state.snapshot(),
        }

    async def _generate_reply(
        self,
        *,
        personality: Personality,
        player_id: str,
        player_text: str,
        relationship: dict[str, Any],
        memories: list[MemoryRecord],
        social_relationships: list[dict[str, Any]],
        world: dict[str, Any],
        context: dict[str, Any],
        mood: str,
    ) -> str:
        for provider in self._llm_provider_order(self._configured_llm_provider()):
            try:
                if provider == "ollama":
                    return await self._call_ollama(
                        personality=personality,
                        player_id=player_id,
                        player_text=player_text,
                        relationship=relationship,
                        memories=memories,
                        social_relationships=social_relationships,
                        world=world,
                        context=context,
                        mood=mood,
                    )
                if provider == "anthropic":
                    return await self._call_claude(
                        personality=personality,
                        player_id=player_id,
                        player_text=player_text,
                        relationship=relationship,
                        memories=memories,
                        social_relationships=social_relationships,
                        world=world,
                        context=context,
                        mood=mood,
                    )
            except Exception:
                # Keep the slice playable even when credentials, network, or model settings fail.
                continue

        return self._fallback_reply(personality, player_text, memories, social_relationships, world, mood)

    def _configured_llm_provider(self) -> str:
        provider = os.getenv("HOLLOW_LLM_PROVIDER", DEFAULT_LLM_PROVIDER).strip().lower()
        if provider not in SUPPORTED_LLM_PROVIDERS:
            return "fallback"
        return provider

    def _llm_provider_order(self, provider: str) -> list[str]:
        if provider == "fallback":
            return []
        if provider == "ollama":
            return ["ollama"]
        if provider == "anthropic":
            return ["anthropic"]

        order: list[str] = []
        if os.getenv("ANTHROPIC_API_KEY"):
            order.append("anthropic")
        if os.getenv("OLLAMA_BASE_URL") or os.getenv("OLLAMA_MODEL"):
            order.append("ollama")
        return order

    async def _call_claude(
        self,
        *,
        personality: Personality,
        player_id: str,
        player_text: str,
        relationship: dict[str, Any],
        memories: list[MemoryRecord],
        social_relationships: list[dict[str, Any]],
        world: dict[str, Any],
        context: dict[str, Any],
        mood: str,
    ) -> str:
        try:
            from anthropic import AsyncAnthropic
        except ImportError as exc:
            raise RuntimeError("anthropic package is not installed") from exc

        client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
        response = await client.messages.create(
            model=model,
            max_tokens=220,
            temperature=0.8,
            system=self._build_system_prompt(
                personality,
                relationship,
                memories,
                social_relationships,
                world,
                context,
                mood,
            ),
            messages=[
                {
                    "role": "user",
                    "content": f"{player_id} says: {player_text}",
                }
            ],
        )

        parts: list[str] = []
        for block in response.content:
            text = getattr(block, "text", None)
            if text:
                parts.append(str(text))
        return " ".join(parts).strip() or self._fallback_reply(
            personality,
            player_text,
            memories,
            social_relationships,
            world,
            mood,
        )

    async def _call_ollama(
        self,
        *,
        personality: Personality,
        player_id: str,
        player_text: str,
        relationship: dict[str, Any],
        memories: list[MemoryRecord],
        social_relationships: list[dict[str, Any]],
        world: dict[str, Any],
        context: dict[str, Any],
        mood: str,
    ) -> str:
        payload = {
            "model": self._ollama_model(),
            "stream": False,
            "messages": [
                {
                    "role": "system",
                    "content": self._build_system_prompt(
                        personality,
                        relationship,
                        memories,
                        social_relationships,
                        world,
                        context,
                        mood,
                    ),
                },
                {
                    "role": "user",
                    "content": f"{player_id} says: {player_text}",
                },
            ],
            "options": {
                "temperature": 0.8,
                "num_predict": 220,
            },
        }
        url = f"{self._ollama_base_url().rstrip('/')}/api/chat"
        raw_response = await asyncio.to_thread(
            self._ollama_transport,
            url,
            payload,
            self._ollama_timeout_seconds(),
        )
        if not isinstance(raw_response, dict):
            raise RuntimeError("Ollama returned a non-object payload")

        message = raw_response.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Ollama returned an empty assistant message")
        return content.strip()

    def _ollama_base_url(self) -> str:
        return os.getenv("OLLAMA_BASE_URL", OLLAMA_DEFAULT_BASE_URL).strip() or OLLAMA_DEFAULT_BASE_URL

    def _ollama_model(self) -> str:
        return os.getenv("OLLAMA_MODEL", OLLAMA_DEFAULT_MODEL).strip() or OLLAMA_DEFAULT_MODEL

    def _ollama_timeout_seconds(self) -> float:
        raw_value = os.getenv("OLLAMA_TIMEOUT_SECONDS", str(OLLAMA_DEFAULT_TIMEOUT_SECONDS))
        try:
            return max(0.1, float(raw_value))
        except ValueError:
            return OLLAMA_DEFAULT_TIMEOUT_SECONDS

    @staticmethod
    def _post_ollama_chat(url: str, payload: dict[str, Any], timeout_seconds: float) -> dict[str, Any]:
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                response_body = response.read().decode("utf-8")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise RuntimeError("Ollama request failed") from exc

        try:
            parsed = json.loads(response_body)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Ollama returned invalid JSON") from exc

        if not isinstance(parsed, dict):
            raise RuntimeError("Ollama returned a non-object payload")
        return parsed

    def _build_system_prompt(
        self,
        personality: Personality,
        relationship: dict[str, Any],
        memories: list[MemoryRecord],
        social_relationships: list[dict[str, Any]],
        world: dict[str, Any],
        context: dict[str, Any],
        mood: str,
    ) -> str:
        memory_lines = "\n".join(
            f"- [{memory.kind}, salience {memory.salience}] {memory.text}" for memory in memories
        ) or "- No prior memories were retrieved."
        social_lines = "\n".join(
            self._social_relationship_prompt_line(relationship) for relationship in social_relationships
        ) or "- No relevant villager relationship context was retrieved."

        return f"""{personality.system_prompt}

Game dialogue rules:
- Reply as {personality.display_name} only.
- Keep the reply to one to three short sentences.
- Reference memories only when they are relevant and natural.
- Do not invent past events unless they are in memory or current context.
- Do not mention Claude, AI, prompts, databases, or server details.

Personality:
{personality.prompt_block()}

Current mood: {mood}
Relationship with player:
- affection: {relationship.get("affection", 0)}
- trust: {relationship.get("trust", 0)}
- familiarity: {relationship.get("familiarity", 0)}
- tension: {relationship.get("tension", 0)}

World context:
- day: {world.get("day")}
- time: {world.get("clock")} ({world.get("time_label")})
- season: {world.get("season")}
- weather: {world.get("weather")}
- location: {context.get("location", "unknown")}

Relevant memories:
{memory_lines}

Relevant villager relationships:
{social_lines}
"""

    def _fallback_reply(
        self,
        personality: Personality,
        player_text: str,
        memories: list[MemoryRecord],
        social_relationships: list[dict[str, Any]],
        world: dict[str, Any],
        mood: str,
    ) -> str:
        text = player_text.lower()
        social_memory = self._first_referenced_social_memory(player_text, memories)
        if social_memory is not None:
            other_name = str(
                social_memory.metadata.get("other_villager_name")
                or social_memory.subject_id
                or "them"
            )
            relationship = self._relationship_for_subject(social_relationships, social_memory.subject_id)
            warmth = self._social_warmth_phrase(relationship)
            return (
                f"I've been thinking about {other_name}. {social_memory.text} "
                f"{warmth}"
            )

        if memories and re.search(r"\b(remember|yesterday|last time|before|again)\b", text):
            remembered = memories[0].text
            return f"I do remember. {remembered} It stayed with me like a little warm brushstroke."

        if re.search(r"\b(hello|hi|hey)\b", text):
            return f"Hi there. The {world.get('time_label', 'day')} feels soft today, doesn't it?"

        if mood == "warm":
            return "That makes me feel close to you, in a quiet sort of way. I'll tuck it carefully into my memory."

        if mood == "worried":
            return "Oh... I hear you. Let me hold onto that gently, and we can talk through it together."

        if memories:
            return f"That reminds me of something I kept thinking about: {memories[0].text}"

        return "I'll remember that. Little things matter here more than people think."

    def _choose_mood(self, text: str, relationship: dict[str, Any], baseline_mood: str) -> str:
        lowered = set(re.findall(r"[a-z']+", text.lower()))
        if lowered & NEGATIVE_WORDS:
            return "worried"
        if lowered & POSITIVE_WORDS or int(relationship.get("affection", 0)) >= 20:
            return "warm"
        if "?" in text:
            return "curious"
        return baseline_mood

    def _server_mood_to_tracker_mood(self, mood: str) -> str:
        return {
            "warm": "happy",
            "delighted": "excited",
            "shy": "anxious",
            "worried": "anxious",
            "curious": "content",
        }.get(mood, mood if mood in {"content", "happy", "excited", "melancholy", "anxious", "irritated", "peaceful", "lonely"} else "content")

    def _estimate_salience(self, text: str) -> int:
        score = 45
        if self._looks_personal(text):
            score += 20
        if "?" in text:
            score += 5
        if len(text) > 120:
            score += 10
        return min(score, 90)

    def _affection_delta(self, text: str) -> int:
        lowered = set(re.findall(r"[a-z']+", text.lower()))
        delta = 0
        if lowered & POSITIVE_WORDS:
            delta += 1
        if lowered & NEGATIVE_WORDS:
            delta -= 1
        return delta

    def _apply_talk_caps(
        self,
        *,
        current_relationship: dict[str, Any],
        proposed_affection: int,
        proposed_trust: int,
        world_day: int,
    ) -> tuple[int, int, dict[str, Any]]:
        """Apply per-in-game-day caps to talk-path affection and trust deltas.

        Implements HH-006 tuning rules:
        - Affection gain from talk is capped at TALK_AFFECTION_DAILY_CAP per in-game day.
        - Trust gain from talk is capped at TALK_TRUST_DAILY_CAP per in-game day (the
          slowest score; personal-disclosure earns trust at most once per day).
        - Negative talk deltas are capped to a single -TALK_NEGATIVE_DAILY_CAP per
          in-game day and never drop affection below 0 from talk alone — the hollow
          notices, but it does not punish.

        Returns (capped_affection_delta, capped_trust_delta, talk_meta_update). The
        metadata update is intended to be merged into the relationship row by the
        caller so the next turn sees the updated counters.
        """
        metadata = current_relationship.get("metadata") or {}
        last_talk_day = metadata.get("last_talk_day")
        if isinstance(last_talk_day, int) and last_talk_day == world_day:
            talk_affection_today = int(metadata.get("talk_affection_today", 0) or 0)
            talk_trust_today = int(metadata.get("talk_trust_today", 0) or 0)
            talk_negative_today = int(metadata.get("talk_negative_today", 0) or 0)
        else:
            # New in-game day (or no prior talk recorded) — reset the daily counters.
            talk_affection_today = 0
            talk_trust_today = 0
            talk_negative_today = 0

        current_affection = int(current_relationship.get("affection", 0))

        # Affection: cap positive gains, soften negatives.
        affection_delta = int(proposed_affection)
        if affection_delta > 0:
            remaining_positive = max(0, TALK_AFFECTION_DAILY_CAP - talk_affection_today)
            affection_delta = min(affection_delta, remaining_positive)
        elif affection_delta < 0:
            remaining_negative = max(0, TALK_NEGATIVE_DAILY_CAP - talk_negative_today)
            magnitude = min(abs(affection_delta), remaining_negative)
            affection_delta = -magnitude
            if affection_delta < 0 and current_affection + affection_delta < 0:
                # Never drop affection below 0 from talk alone.
                if current_affection > 0:
                    affection_delta = -current_affection
                else:
                    affection_delta = 0

        # Trust: cap positive gains; negative trust from talk is never proposed today.
        trust_delta = max(0, int(proposed_trust))
        remaining_trust = max(0, TALK_TRUST_DAILY_CAP - talk_trust_today)
        trust_delta = min(trust_delta, remaining_trust)

        new_affection_today = talk_affection_today + max(0, affection_delta)
        new_trust_today = talk_trust_today + max(0, trust_delta)
        new_negative_today = talk_negative_today + (1 if affection_delta < 0 else 0)

        talk_meta_update = {
            "last_talk_day": int(world_day),
            "talk_affection_today": int(new_affection_today),
            "talk_trust_today": int(new_trust_today),
            "talk_negative_today": int(new_negative_today),
        }
        return int(affection_delta), int(trust_delta), talk_meta_update

    def _looks_personal(self, text: str) -> bool:
        lowered = text.lower()
        return any(marker in lowered for marker in ["i ", "my ", "me ", "remember", "feel", "love", "miss"])

    def _social_context_for_text(
        self,
        personality: Personality,
        player_text: str,
    ) -> tuple[list[MemoryRecord], list[dict[str, Any]]]:
        social_memories: list[MemoryRecord] = []
        social_relationships: list[dict[str, Any]] = []
        for other_id in self._referenced_villager_ids(personality, player_text):
            social_memories.extend(
                self.memory_store.query_memories(
                    villager_id=personality.id,
                    subject_id=other_id,
                    kind="villager_interaction",
                    limit=3,
                )
            )
            relationship = self.memory_store.peek_relationship(personality.id, other_id)
            if relationship is not None:
                social_relationships.append(relationship)

        return social_memories, social_relationships

    def _referenced_villager_ids(self, personality: Personality, player_text: str) -> list[str]:
        referenced: list[str] = []
        text = player_text.lower()
        for villager_id in self.personality_store.list_ids():
            if villager_id == personality.id:
                continue
            try:
                other = self.personality_store.load(villager_id)
            except FileNotFoundError:
                continue

            names = {villager_id.lower(), other.display_name.lower()}
            if any(re.search(rf"\b{re.escape(name)}\b", text) for name in names if name):
                referenced.append(villager_id)
        return referenced

    def _merge_memories(
        self,
        player_memories: list[MemoryRecord],
        social_memories: list[MemoryRecord],
        *,
        limit: int,
    ) -> list[MemoryRecord]:
        memories_by_id: dict[int, MemoryRecord] = {}
        for memory in [*social_memories, *player_memories]:
            memories_by_id[memory.id] = memory

        return sorted(
            memories_by_id.values(),
            key=lambda memory: (
                memory.kind == "villager_interaction",
                int(memory.salience),
                str(memory.created_at),
            ),
            reverse=True,
        )[:limit]

    def _first_referenced_social_memory(
        self,
        player_text: str,
        memories: list[MemoryRecord],
    ) -> MemoryRecord | None:
        text = player_text.lower()
        for memory in memories:
            if memory.kind != "villager_interaction":
                continue
            names = {
                str(memory.subject_id or "").lower(),
                str(memory.metadata.get("other_villager_id") or "").lower(),
                str(memory.metadata.get("other_villager_name") or "").lower(),
            }
            if any(name and re.search(rf"\b{re.escape(name)}\b", text) for name in names):
                return memory
        return None

    def _relationship_for_subject(
        self,
        social_relationships: list[dict[str, Any]],
        subject_id: str | None,
    ) -> dict[str, Any] | None:
        if not subject_id:
            return None
        return next(
            (
                relationship
                for relationship in social_relationships
                if relationship.get("subject_id") == subject_id
            ),
            None,
        )

    def _social_warmth_phrase(self, relationship: dict[str, Any] | None) -> str:
        if relationship is None:
            return "I'm still learning what that means for us."
        affection = int(relationship.get("affection", 0))
        trust = int(relationship.get("trust", 0))
        if affection >= 20 or trust >= 20:
            return "I trust them more than I say out loud."
        if affection > 0 or trust > 0:
            return "It made me feel a little closer to them."
        tension = int(relationship.get("tension", 0))
        if tension >= 10:
            return "There is still something careful between us."
        return "I'm still deciding how I feel about them."

    def _social_relationship_prompt_line(self, relationship: dict[str, Any]) -> str:
        subject_id = str(relationship.get("subject_id") or "unknown")
        try:
            subject_name = self.personality_store.load(subject_id).display_name
        except FileNotFoundError:
            subject_name = subject_id
        metadata = dict(relationship.get("metadata") or {})
        topic = metadata.get("last_interaction_topic")
        topic_suffix = f"; latest topic: {topic}" if topic else ""
        return (
            f"- With {subject_name}: affection {relationship.get('affection', 0)}, "
            f"trust {relationship.get('trust', 0)}, "
            f"familiarity {relationship.get('familiarity', 0)}, "
            f"tension {relationship.get('tension', 0)}{topic_suffix}"
        )

    def _summarize_exchange(self, player_id: str, villager_name: str, player_text: str, reply: str) -> str:
        player_short = player_text.strip().replace("\n", " ")[:180]
        reply_short = reply.strip().replace("\n", " ")[:180]
        return f"{player_id} told {villager_name}: \"{player_short}\" {villager_name} replied: \"{reply_short}\""

    def _gift_preference(self, personality: Personality, item_category: str, item_tags: set[str]) -> str:
        likes = {item.lower() for item in personality.likes}
        dislikes = {item.lower() for item in personality.dislikes}
        if self._matches_preference(dislikes, item_category, item_tags):
            return "disliked"
        # HH-062: a villager loves a gift when its tag set or category intersects
        # with the villager's personal "loved" rubric. The rubric is either the
        # explicit `loved_tags` list from the JSON config (preferred — distinct
        # per villager) or the legacy DEFAULT_LOVED_TAGS fallback (for any
        # pre-HH-062 config that hasn't been updated yet).
        loved_tags = self._loved_tags_for(personality)
        item_category_clean = (item_category or "").strip().lower()
        gift_candidates: set[str] = set(item_tags)
        if item_category_clean:
            gift_candidates.add(item_category_clean)
        if loved_tags & gift_candidates:
            return "loved"
        if self._matches_preference(likes, item_category, item_tags):
            return "liked"
        return "neutral"

    def _loved_tags_for(self, personality: Personality) -> set[str]:
        explicit = {tag.strip().lower() for tag in personality.loved_tags if tag.strip()}
        if explicit:
            return explicit
        return set(DEFAULT_LOVED_TAGS)

    @staticmethod
    def _bump_gift_preference(preference: str) -> str:
        """Return the next-warmer tier on the gift preference ladder.

        HH-006 first-of-kind bonus: the first gift any player gives a villager
        should land one tier warmer than its native preference. Loved stays
        loved (the ladder has no higher rung).
        """
        ladder = GIFT_PREFERENCE_LADDER
        if preference not in ladder:
            return preference
        index = ladder.index(preference)
        return ladder[min(index + 1, len(ladder) - 1)]

    def _coerce_recent_gifts(
        self,
        raw_value: Any,
        *,
        world_day: int,
    ) -> list[dict[str, Any]]:
        """Normalize and prune persisted recent_gifts metadata.

        Returns a list of `{item_id, day}` entries trimmed to those within the
        trailing `GIFT_REPEAT_WINDOW_DAYS` in-game days relative to the supplied
        `world_day`. Invalid or malformed rows are dropped silently so a hand
        edited relationship metadata blob can't crash the gift path.
        """
        if not isinstance(raw_value, list):
            return []
        window_floor = int(world_day) - GIFT_REPEAT_WINDOW_DAYS + 1
        cleaned: list[dict[str, Any]] = []
        for entry in raw_value:
            if not isinstance(entry, dict):
                continue
            entry_item_id = str(entry.get("item_id") or "").strip().lower()
            if not entry_item_id:
                continue
            try:
                entry_day = int(entry.get("day"))
            except (TypeError, ValueError):
                continue
            if entry_day < window_floor or entry_day > int(world_day):
                continue
            cleaned.append({"item_id": entry_item_id, "day": entry_day})
        return cleaned

    def _matches_preference(self, preferences: set[str], item_category: str, item_tags: set[str]) -> bool:
        candidates = {item_category, *item_tags}
        for candidate in candidates:
            candidate = candidate.strip().lower()
            if not candidate:
                continue
            candidate_stem = candidate.removesuffix("s")
            for preference in preferences:
                preference_words = preference.replace("-", " ").split()
                preference_stems = {word.removesuffix("s") for word in preference_words}
                if candidate == preference or candidate_stem == preference.removesuffix("s"):
                    return True
                if candidate in preference_words or candidate_stem in preference_stems:
                    return True
        return False

    def _public_relationship(self, relationship: dict[str, Any]) -> dict[str, int]:
        return {
            "affection": int(relationship.get("affection", 0)),
            "trust": int(relationship.get("trust", 0)),
            "familiarity": int(relationship.get("familiarity", 0)),
            "tension": int(relationship.get("tension", 0)),
        }
