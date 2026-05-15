"""Smoke test for gift memory, relationship, mood, and event updates.

Run from the repo root:

    python -m server.tests.test_gift_relationship
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from server.ai.conversation import ConversationEngine
from server.ai.memory import MemoryStore
from server.ai.personality import PersonalityStore
from server.world.events import EventLog
from server.world.state import WorldState


LOVED_GIFT = {
    "item_id": "dusty_rose",
    "display_name": "Dusty Rose",
    "category": "flower",
    "tags": ["flower", "garden", "soft_color", "handmade"],
    "quantity": 1,
    "gift_prompt": "A soft dusty rose picked from Heather's garden.",
}

NEUTRAL_GIFT = {
    "item_id": "smooth_pebble",
    "display_name": "Smooth Pebble",
    "category": "trinket",
    "tags": ["stone", "smooth", "pocket"],
    "quantity": 1,
    "gift_prompt": "A small smooth pebble from the path near the garden.",
}

DISLIKED_GIFT = {
    "item_id": "wilted_bouquet",
    "display_name": "Wilted Bouquet",
    "category": "trash",
    "tags": ["waste"],
    "quantity": 1,
    "gift_prompt": "A bouquet of flowers that has seen better days.",
}

# HH-062 per-villager loved-gift smoke fixtures. Each item is shaped so the
# *signature* tag for one villager (lavender, bread, marigold, smooth) is
# present, exercising the per-villager loved_tags scoring path.
FERN_LOVED_GIFT = {
    "item_id": "lavender_sachet",
    "display_name": "Lavender Sachet",
    "category": "herb",
    "tags": ["herb", "lavender", "handmade", "soft_color"],
    "quantity": 1,
    "gift_prompt": "A small linen sachet of dried lavender, hand-stitched closed.",
}

HUGO_LOVED_GIFT = {
    "item_id": "honey_oat_crust",
    "display_name": "Honey Oat Crust",
    "category": "baked",
    "tags": ["bread", "baked", "warm", "handmade"],
    "quantity": 1,
    "gift_prompt": "A small heel of warm honey oat bread saved from this morning's bake.",
}

CLOVER_LOVED_GIFT = {
    "item_id": "marigold_sprig",
    "display_name": "Marigold Sprig",
    "category": "flower",
    "tags": ["flower", "marigold", "orange", "garden"],
    "quantity": 1,
    "gift_prompt": "A bright orange marigold sprig with one slightly bent petal.",
}

# A gift Hugo would *not* love: Dusty Rose has no bread/tea/rain/sea/wood/
# well-made/warm signature, so it should score neutral against the gruff baker.
HUGO_NEUTRAL_GIFT = LOVED_GIFT


async def run_gift_relationship_check() -> None:
    with TemporaryDirectory() as tmp_dir:
        memory_store = MemoryStore(Path(tmp_dir) / "gift_relationship.sqlite3")
        event_log = EventLog()
        engine = ConversationEngine(
            memory_store=memory_store,
            personality_store=PersonalityStore(),
            world_state=WorldState.create_default(),
            event_log=event_log,
        )

        try:
            loved = await engine.handle_gift(
                player_id="heather_loved",
                villager_id="margot",
                item=LOVED_GIFT,
                context={"location": "town_square", "test": "gift_relationship_loved"},
            )
            neutral = await engine.handle_gift(
                player_id="heather_neutral",
                villager_id="margot",
                item=NEUTRAL_GIFT,
                context={"location": "town_square", "test": "gift_relationship_neutral"},
            )
            catalog_only = await engine.handle_gift(
                player_id="heather_catalog",
                villager_id="margot",
                item={
                    "item_id": "dusty_rose",
                    "display_name": "Stale Rose Name",
                    "category": "waste",
                    "tags": ["waste"],
                    "quantity": 99,
                    "secret": "not public",
                },
                context={"location": "town_square", "test": "gift_relationship_catalog"},
            )
            unknown = await engine.handle_gift(
                player_id="heather_unknown",
                villager_id="margot",
                item={
                    "item_id": "blue_thread",
                    "display_name": "Blue Thread",
                    "category": "keepsake",
                    "tags": ["handmade"],
                    "quantity": "2",
                    "secret": "not public",
                },
                context={"location": "town_square", "test": "gift_relationship_unknown"},
            )
            disliked = await engine.handle_gift(
                player_id="heather_disliked",
                villager_id="margot",
                item=DISLIKED_GIFT,
                context={"location": "town_square", "test": "gift_relationship_disliked"},
            )

            assert loved["mood"] == "delighted"
            assert neutral["mood"] == "shy"
            assert catalog_only["mood"] == "delighted"
            assert unknown["type"] == "villager_reply"
            # HH-006 softening: disliked gifts feel melancholy, not anxious-shy, and
            # cost only -1 affection (not -2) — the hollow stays cozy under mistakes.
            assert disliked["mood"] == "melancholy"
            disliked_memory = next(
                memory for memory in memory_store.get_recent_memories("margot", limit=10)
                if memory.id == disliked["memory_id"]
            )
            assert disliked_memory.metadata["preference"] == "disliked"
            # This test uses a unique player_id with no seeded starting affection (0).
            # HH-006 softens the disliked delta from -2 to -1, so affection should be -1
            # after one disliked gift, not -2 as it was before HH-006.
            assert disliked["relationship"]["affection"] == -1
            assert loved["relationship"]["affection"] > neutral["relationship"]["affection"]
            assert loved["relationship"]["trust"] > neutral["relationship"]["trust"]
            assert loved["relationship"]["familiarity"] == neutral["relationship"]["familiarity"] == 1

            loved_memory = next(
                memory for memory in memory_store.get_recent_memories("margot", limit=5)
                if memory.id == loved["memory_id"]
            )
            neutral_memory = next(
                memory for memory in memory_store.get_recent_memories("margot", limit=5)
                if memory.id == neutral["memory_id"]
            )

            assert loved_memory.kind == "gift"
            assert loved_memory.metadata["preference"] == "loved"
            assert loved_memory.metadata["item"]["display_name"] == "Dusty Rose"
            assert neutral_memory.kind == "gift"
            assert neutral_memory.metadata["preference"] == "neutral"
            assert neutral_memory.metadata["item"]["display_name"] == "Smooth Pebble"
            catalog_memory = next(
                memory for memory in memory_store.get_recent_memories("margot", limit=10)
                if memory.id == catalog_only["memory_id"]
            )
            assert catalog_memory.metadata["preference"] == "loved"
            assert catalog_memory.metadata["item"]["display_name"] == "Dusty Rose"
            assert catalog_memory.metadata["item"]["category"] == "flower"
            assert catalog_memory.metadata["item"]["quantity"] == 1
            assert "flower" in catalog_memory.metadata["item"]["tags"]
            assert "secret" not in catalog_memory.metadata["item"]

            unknown_memory = next(
                memory for memory in memory_store.get_recent_memories("margot", limit=10)
                if memory.id == unknown["memory_id"]
            )
            assert unknown_memory.metadata["item"]["item_id"] == "blue_thread"
            assert unknown_memory.metadata["item"]["display_name"] == "Blue Thread"
            assert unknown_memory.metadata["item"]["quantity"] == 2
            assert "secret" not in unknown_memory.metadata["item"]

            live_events = event_log.recent(limit=5)
            assert any(
                event.kind == "gift"
                and event.metadata.get("memory_id") == loved["memory_id"]
                and event.metadata.get("preference") == "loved"
                for event in live_events
            )
            assert any(
                event.kind == "gift"
                and event.metadata.get("memory_id") == neutral["memory_id"]
                and event.metadata.get("preference") == "neutral"
                for event in live_events
            )
            assert any(
                event.kind == "gift"
                and event.metadata.get("memory_id") == catalog_only["memory_id"]
                and event.metadata.get("item_name") == "Dusty Rose"
                and event.metadata.get("preference") == "loved"
                for event in live_events
            )

            persisted_events = memory_store.get_recent_events(limit=10)
            assert any(
                event.kind == "gift"
                and event.actor_id == "heather_loved"
                and event.target_id == "margot"
                and event.metadata.get("memory_id") == loved["memory_id"]
                and event.metadata.get("preference") == "loved"
                for event in persisted_events
            )
            assert any(
                event.kind == "gift"
                and event.actor_id == "heather_neutral"
                and event.target_id == "margot"
                and event.metadata.get("memory_id") == neutral["memory_id"]
                and event.metadata.get("preference") == "neutral"
                for event in persisted_events
            )
            assert any(
                event.kind == "gift"
                and event.actor_id == "heather_catalog"
                and event.target_id == "margot"
                and event.metadata.get("memory_id") == catalog_only["memory_id"]
                and event.metadata.get("item_id") == "dusty_rose"
                and event.metadata.get("item_name") == "Dusty Rose"
                and event.metadata.get("preference") == "loved"
                for event in persisted_events
            )

            # HH-062 per-villager loved-gift coverage. Each canonical MVP
            # villager should score "loved" on the cast-specific item whose
            # tags hit their personal `loved_tags` rubric, *and* Hugo should
            # still score Dusty Rose as neutral (it has none of his signature
            # bread/tea/rain/sea/wood/well-made/warm tags). That distinction is
            # the whole point of the change: gifts now read as personality,
            # not as a single global rubric.
            fern_loved = await engine.handle_gift(
                player_id="heather_fern_loved",
                villager_id="fern",
                item=FERN_LOVED_GIFT,
                context={"location": "garden", "test": "fern_loved"},
            )
            hugo_loved = await engine.handle_gift(
                player_id="heather_hugo_loved",
                villager_id="hugo",
                item=HUGO_LOVED_GIFT,
                context={"location": "shop", "test": "hugo_loved"},
            )
            clover_loved = await engine.handle_gift(
                player_id="heather_clover_loved",
                villager_id="clover",
                item=CLOVER_LOVED_GIFT,
                context={"location": "brook", "test": "clover_loved"},
            )
            hugo_neutral = await engine.handle_gift(
                player_id="heather_hugo_neutral",
                villager_id="hugo",
                item=HUGO_NEUTRAL_GIFT,
                context={"location": "shop", "test": "hugo_neutral"},
            )

            assert fern_loved["mood"] == "delighted", (
                f"Fern should love a lavender sachet, got mood={fern_loved['mood']!r}."
            )
            assert hugo_loved["mood"] == "delighted", (
                f"Hugo should love a honey oat crust, got mood={hugo_loved['mood']!r}."
            )
            assert clover_loved["mood"] == "delighted", (
                f"Clover should love a marigold sprig, got mood={clover_loved['mood']!r}."
            )
            # Hugo doesn't share Margot's flower rubric — a Dusty Rose should
            # *not* be loved by the gruff baker. It also shouldn't be disliked
            # (none of his dislikes match), so the engine should land on
            # neutral with the conservative "shy" mood label.
            assert hugo_neutral["mood"] == "shy", (
                f"Hugo should be neutral on Dusty Rose (no bread/tea/rain/sea match), "
                f"got mood={hugo_neutral['mood']!r}."
            )

            for loved_payload in (fern_loved, hugo_loved, clover_loved):
                memory_id = loved_payload["memory_id"]
                villager_id = loved_payload["villager_id"]
                memory = next(
                    memory for memory in memory_store.get_recent_memories(villager_id, limit=10)
                    if memory.id == memory_id
                )
                assert memory.kind == "gift"
                assert memory.metadata["preference"] == "loved", (
                    f"{villager_id} loved-gift memory should record preference=loved, "
                    f"got {memory.metadata.get('preference')!r}."
                )
                # Loved gifts should land at least +5 affection on a 0-baseline
                # player so the demo's reward signal stays legible. Trust
                # bumps too, but the magnitude is engine-tunable.
                assert loved_payload["relationship"]["affection"] >= 5, (
                    f"{villager_id} loved-gift affection delta should be >= 5, "
                    f"got {loved_payload['relationship']['affection']}."
                )
                assert loved_payload["relationship"]["trust"] >= 2, (
                    f"{villager_id} loved-gift trust delta should be >= 2, "
                    f"got {loved_payload['relationship']['trust']}."
                )

                # HH-006 mood pin: a loved gift should set `pinned_mood` and
                # `pinned_until_minute` on the villager's self mood_state so
                # the delighted/excited reading actually holds for the next
                # couple of in-game hours instead of being washed out by the
                # next baseline tick.
                self_relationship = memory_store.get_relationship(villager_id, "self")
                pin_mood_state = (self_relationship.get("metadata") or {}).get("mood_state") or {}
                assert pin_mood_state.get("pinned_mood") == "excited", (
                    f"{villager_id} loved-gift should pin mood=excited, "
                    f"got pinned_mood={pin_mood_state.get('pinned_mood')!r}."
                )
                pinned_until_minute = pin_mood_state.get("pinned_until_minute")
                assert isinstance(pinned_until_minute, int) and pinned_until_minute > 0, (
                    f"{villager_id} loved-gift should set a positive pinned_until_minute, "
                    f"got {pinned_until_minute!r}."
                )
                # The publicly reported current mood should reflect the pin so
                # a follow-up `/villagers/{id}` or `/client/villagers/.../context`
                # call surfaces the loved-gift reading.
                assert pin_mood_state.get("current") == "excited", (
                    f"{villager_id} loved-gift should surface current=excited "
                    f"on the self mood_state, got {pin_mood_state.get('current')!r}."
                )

            # Neutral and disliked gifts should *not* pin the mood — the cozy
            # rubric is "loved gifts feel biggest, missteps are a small note",
            # not "every gift pins for two in-game hours".
            neutral_self = memory_store.get_relationship("margot", "self")
            neutral_pin = (neutral_self.get("metadata") or {}).get("mood_state") or {}
            # After the Margot test sequence above, the most recent gift on
            # margot is the disliked Wilted Bouquet. The pin set by the prior
            # Dusty Rose may or may not still be live; what matters is that
            # the disliked path didn't introduce a *new* delighted/melancholy
            # pin of its own.
            assert neutral_pin.get("pinned_mood") in {None, "", "excited"}, (
                "Disliked gift path must not pin a melancholy mood — the hollow "
                "should not stew over a misstep."
            )
        finally:
            memory_store.close()


def main() -> None:
    asyncio.run(run_gift_relationship_check())
    print("PASS: Gift relationship, memory, mood, and event updates are consistent.")


if __name__ == "__main__":
    main()
