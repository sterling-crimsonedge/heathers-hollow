"""Deterministic background villager interactions."""

from __future__ import annotations

import hashlib
from typing import Any

from server.ai.memory import MemoryStore
from server.ai.personality import Personality, PersonalityStore
from server.world.events import EventLog, VillageEvent
from server.world.state import WorldState


DEFAULT_AWAY_LOCATIONS = ["garden_path", "town_square", "shop_steps", "tea_garden"]


class AwayInteractionEngine:
    """Creates simple memories for villager activity while the player is away."""

    def __init__(
        self,
        *,
        memory_store: MemoryStore,
        personality_store: PersonalityStore,
        world_state: WorldState,
        event_log: EventLog,
    ) -> None:
        self.memory_store = memory_store
        self.personality_store = personality_store
        self.world_state = world_state
        self.event_log = event_log

    def run_tick(
        self,
        *,
        actor_id: str | None = None,
        target_id: str | None = None,
        location: str | None = None,
    ) -> dict[str, Any]:
        actor_id, target_id = self._select_pair(actor_id, target_id)
        actor = self.personality_store.load(actor_id)
        target = self.personality_store.load(target_id)
        world = self.world_state.snapshot()
        location = location or self._select_location(actor_id, target_id, world)
        topic = self._select_topic(actor, target)
        mood = self._select_mood(topic, world)

        self._upsert_villager(actor)
        self._upsert_villager(target)

        actor_memory_id = self._write_memory(actor, target, topic, mood, location, world)
        target_memory_id = self._write_memory(target, actor, topic, mood, location, world)

        actor_relationship = self._nudge_relationship(
            actor.id,
            target.id,
            topic=topic,
            memory_id=actor_memory_id,
        )
        target_relationship = self._nudge_relationship(
            target.id,
            actor.id,
            topic=topic,
            memory_id=target_memory_id,
        )

        summary = (
            f"{actor.display_name} and {target.display_name} spent a quiet moment "
            f"talking about {topic}."
        )
        event = VillageEvent(
            kind="villager_interaction",
            actor_id=actor.id,
            target_id=target.id,
            location=location,
            summary=summary,
            metadata={
                "actor_memory_id": actor_memory_id,
                "target_memory_id": target_memory_id,
                "topic": topic,
                "mood": mood,
                "relationship_delta": {"affection": 1, "trust": 1, "familiarity": 1},
            },
        )
        self.event_log.publish(event)
        event_id = self.memory_store.add_event(
            kind=event.kind,
            actor_id=event.actor_id,
            target_id=event.target_id,
            location=event.location,
            summary=event.summary,
            metadata=event.metadata,
        )

        return {
            "type": "away_interaction",
            "event": {
                "id": event_id,
                "kind": event.kind,
                "actor_id": event.actor_id,
                "target_id": event.target_id,
                "location": event.location,
                "summary": event.summary,
                "metadata": event.metadata,
            },
            "actor": {"id": actor.id, "display_name": actor.display_name},
            "target": {"id": target.id, "display_name": target.display_name},
            "topic": topic,
            "mood": mood,
            "relationship": {
                actor.id: self._public_relationship(actor_relationship),
                target.id: self._public_relationship(target_relationship),
            },
            "world": world,
        }

    def run_ticks(
        self,
        *,
        count: int = 1,
        actor_id: str | None = None,
        target_id: str | None = None,
        location: str | None = None,
    ) -> dict[str, Any]:
        requested_count = int(count)
        bounded_count = max(1, min(requested_count, 12))
        ticks = [
            self.run_tick(actor_id=actor_id, target_id=target_id, location=location)
            for _ in range(bounded_count)
        ]
        return {
            "type": "away_interaction_batch",
            "requested_count": requested_count,
            "count": len(ticks),
            "ticks": ticks,
        }

    def _select_pair(self, actor_id: str | None, target_id: str | None) -> tuple[str, str]:
        villager_ids = self.personality_store.list_ids()
        if len(villager_ids) < 2 and (not actor_id or not target_id):
            raise ValueError("At least two villager configs are required for an away interaction.")

        actor_id = actor_id or villager_ids[0]
        target_id = target_id or next(villager_id for villager_id in villager_ids if villager_id != actor_id)
        if actor_id == target_id:
            raise ValueError("Away interaction requires two different villagers.")
        return actor_id, target_id

    def _select_location(self, actor_id: str, target_id: str, world: dict[str, Any]) -> str:
        digest = hashlib.sha1(
            f"{actor_id}:{target_id}:{world.get('day')}:{world.get('time_label')}".encode("utf-8")
        ).digest()
        return DEFAULT_AWAY_LOCATIONS[digest[0] % len(DEFAULT_AWAY_LOCATIONS)]

    def _select_topic(self, actor: Personality, target: Personality) -> str:
        actor_likes = {like.lower() for like in actor.likes}
        target_likes = {like.lower() for like in target.likes}
        shared_likes = sorted(actor_likes & target_likes)
        if shared_likes:
            return shared_likes[0]

        actor_values = {value.lower() for value in actor.values}
        target_values = {value.lower() for value in target.values}
        shared_values = sorted(actor_values & target_values)
        if shared_values:
            return shared_values[0]

        return "quiet company"

    def _select_mood(self, topic: str, world: dict[str, Any]) -> str:
        if topic in {"tea", "flowers", "lavender", "warm kitchens"}:
            return "peaceful"
        if str(world.get("time_label")) == "night":
            return "melancholy"
        return "content"

    def _upsert_villager(self, personality: Personality) -> None:
        self.memory_store.upsert_villager(
            personality.id,
            personality.display_name,
            str(personality.config_path),
        )

    def _write_memory(
        self,
        actor: Personality,
        target: Personality,
        topic: str,
        mood: str,
        location: str,
        world: dict[str, Any],
    ) -> int:
        text = (
            f"{actor.display_name} spent time with {target.display_name} near "
            f"{location.replace('_', ' ')}. They talked about {topic}, and it felt {mood}."
        )
        return self.memory_store.add_memory(
            actor.id,
            kind="villager_interaction",
            subject_id=target.id,
            text=text,
            salience=55,
            emotion=mood,
            metadata={
                "other_villager_id": target.id,
                "other_villager_name": target.display_name,
                "topic": topic,
                "location": location,
                "world": {
                    "day": world.get("day"),
                    "time_label": world.get("time_label"),
                    "season": world.get("season"),
                    "weather": world.get("weather"),
                },
            },
        )

    def _nudge_relationship(
        self,
        villager_id: str,
        subject_id: str,
        *,
        topic: str,
        memory_id: int,
    ) -> dict[str, Any]:
        self.memory_store.get_relationship(villager_id, subject_id)
        return self.memory_store.update_relationship(
            villager_id,
            subject_id,
            affection_delta=1,
            trust_delta=1,
            familiarity_delta=1,
            metadata={
                "last_interaction_topic": topic,
                "last_interaction_memory_id": memory_id,
            },
        )

    def _public_relationship(self, relationship: dict[str, Any]) -> dict[str, int]:
        return {
            "affection": int(relationship.get("affection", 0)),
            "trust": int(relationship.get("trust", 0)),
            "familiarity": int(relationship.get("familiarity", 0)),
            "tension": int(relationship.get("tension", 0)),
        }
