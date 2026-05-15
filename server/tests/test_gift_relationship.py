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


WARMUP_GIFT = {
    "item_id": "tuning_warmup",
    "display_name": "Tuning Warmup",
    "category": "warmup",
    "tags": ["warmup"],
    "quantity": 1,
    "gift_prompt": "A small token used to burn the first-of-kind gift bonus in tests.",
}


async def _burn_first_of_kind(
    engine: ConversationEngine,
    *,
    player_id: str,
    villager_id: str,
) -> None:
    """Give a generic warmup gift so steady-state assertions ignore HH-006 first-of-kind.

    The warmup item has no tags that match any villager's likes, dislikes, or
    loved_tags, so its base preference is `neutral`. The first-of-kind bonus
    then bumps it to `liked` (affection +2, trust +2). Tests can subtract that
    constant baseline when asserting subsequent gift deltas.
    """
    await engine.handle_gift(
        player_id=player_id,
        villager_id=villager_id,
        item=WARMUP_GIFT,
        context={"location": "town_square", "test": "warmup"},
    )


WARMUP_AFFECTION = 2
WARMUP_TRUST = 2
WARMUP_FAMILIARITY = 1


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
            # HH-006 first-of-kind: the first gift any player gives a villager
            # gets bumped one preference tier. Burn that bonus for every
            # test player so the steady-state assertions below exercise the
            # native preference path. The dedicated first-of-kind test below
            # covers the bonus itself.
            for warmup_player_id in (
                "heather_loved",
                "heather_neutral",
                "heather_catalog",
                "heather_unknown",
                "heather_disliked",
            ):
                await _burn_first_of_kind(
                    engine,
                    player_id=warmup_player_id,
                    villager_id="margot",
                )

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
            # The warmup gift earlier in this run was a neutral item bumped by
            # first-of-kind to liked (+2 affection, +2 trust). The wilted bouquet
            # is now a steady-state disliked gift at -1 affection on top of that,
            # so the relationship row lands at WARMUP_AFFECTION - 1.
            assert (
                disliked["relationship"]["affection"]
                == WARMUP_AFFECTION - 1
            )
            assert loved["relationship"]["affection"] > neutral["relationship"]["affection"]
            assert loved["relationship"]["trust"] > neutral["relationship"]["trust"]
            assert (
                loved["relationship"]["familiarity"]
                == neutral["relationship"]["familiarity"]
                == WARMUP_FAMILIARITY + 1
            )

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
            #
            # Each per-villager player_id gets a warmup gift first so HH-006
            # first-of-kind is burned before the asserted loved gift lands.
            # The warmup itself is a neutral item bumped to liked by
            # first-of-kind; the asserted loved gift below is then a true
            # steady-state loved interaction.
            for warmup_player_id, warmup_villager_id in (
                ("heather_fern_loved", "fern"),
                ("heather_hugo_loved", "hugo"),
                ("heather_clover_loved", "clover"),
                ("heather_hugo_neutral", "hugo"),
            ):
                await _burn_first_of_kind(
                    engine,
                    player_id=warmup_player_id,
                    villager_id=warmup_villager_id,
                )

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


async def run_first_of_kind_gift_bonus_check() -> None:
    """HH-006 first-of-kind bonus: the first gift any player gives a villager
    should land one preference tier warmer than its native taste match. A
    neutral first gift reads as liked; a disliked first gift reads as neutral;
    a loved first gift stays loved. The bonus fires exactly once per
    (player, villager) pair and is recorded on the relationship metadata.
    """
    with TemporaryDirectory() as tmp_dir:
        memory_store = MemoryStore(Path(tmp_dir) / "first_of_kind.sqlite3")
        event_log = EventLog()
        engine = ConversationEngine(
            memory_store=memory_store,
            personality_store=PersonalityStore(),
            world_state=WorldState.create_default(),
            event_log=event_log,
        )

        try:
            # 1. Neutral first gift should land as liked (tier bump).
            neutral_first = await engine.handle_gift(
                player_id="heather_first_neutral",
                villager_id="margot",
                item=NEUTRAL_GIFT,
                context={"location": "town_square", "test": "first_of_kind_neutral"},
            )
            assert neutral_first["mood"] == "warm", (
                f"First-of-kind neutral gift should bump to liked (mood=warm), "
                f"got mood={neutral_first['mood']!r}."
            )
            neutral_first_memory = next(
                memory for memory in memory_store.get_recent_memories("margot", limit=5)
                if memory.id == neutral_first["memory_id"]
            )
            assert neutral_first_memory.metadata["preference"] == "liked"
            assert neutral_first_memory.metadata["base_preference"] == "neutral"
            assert neutral_first_memory.metadata["first_of_kind_bonus"] is True
            # Liked tier delta on a fresh player: affection +2, trust +2.
            assert neutral_first["relationship"]["affection"] == 2
            assert neutral_first["relationship"]["trust"] == 2

            # 2. A second gift from the same player must *not* re-trigger the
            #    bonus. Give the same player a neutral pebble; it should now
            #    read as a true neutral interaction.
            neutral_second = await engine.handle_gift(
                player_id="heather_first_neutral",
                villager_id="margot",
                item={
                    "item_id": "another_pebble",
                    "display_name": "Another Pebble",
                    "category": "trinket",
                    "tags": ["stone", "pocket"],
                    "quantity": 1,
                },
                context={"location": "town_square", "test": "first_of_kind_used_up"},
            )
            assert neutral_second["mood"] == "shy", (
                f"Second gift to same player should not get first-of-kind bonus; "
                f"expected mood=shy, got mood={neutral_second['mood']!r}."
            )
            second_memory = next(
                memory for memory in memory_store.get_recent_memories("margot", limit=5)
                if memory.id == neutral_second["memory_id"]
            )
            assert second_memory.metadata["preference"] == "neutral"
            assert second_memory.metadata["base_preference"] == "neutral"
            assert second_memory.metadata["first_of_kind_bonus"] is False

            # 3. Disliked first gift should bump to neutral. Affection delta
            #    softens from -1 to +1 because the first gift is a "relationship
            #    event regardless of what it was" (per docs/AI_ARCHITECTURE.md).
            disliked_first = await engine.handle_gift(
                player_id="heather_first_disliked",
                villager_id="margot",
                item=DISLIKED_GIFT,
                context={"location": "town_square", "test": "first_of_kind_disliked"},
            )
            assert disliked_first["mood"] == "shy", (
                f"First-of-kind disliked gift should bump to neutral (mood=shy), "
                f"got mood={disliked_first['mood']!r}."
            )
            disliked_first_memory = next(
                memory for memory in memory_store.get_recent_memories("margot", limit=5)
                if memory.id == disliked_first["memory_id"]
            )
            assert disliked_first_memory.metadata["preference"] == "neutral"
            assert disliked_first_memory.metadata["base_preference"] == "disliked"
            assert disliked_first_memory.metadata["first_of_kind_bonus"] is True
            assert disliked_first["relationship"]["affection"] == 1, (
                "First-of-kind should never let the very first gift dock affection."
            )

            # 4. Loved first gift stays loved. There is no rung above loved.
            loved_first = await engine.handle_gift(
                player_id="heather_first_loved",
                villager_id="margot",
                item=LOVED_GIFT,
                context={"location": "town_square", "test": "first_of_kind_loved"},
            )
            assert loved_first["mood"] == "delighted"
            loved_first_memory = next(
                memory for memory in memory_store.get_recent_memories("margot", limit=5)
                if memory.id == loved_first["memory_id"]
            )
            assert loved_first_memory.metadata["preference"] == "loved"
            assert loved_first_memory.metadata["base_preference"] == "loved"
            assert loved_first_memory.metadata["first_of_kind_bonus"] is True

            # The first-of-kind flag is persisted on the relationship row so a
            # cold restart still respects the bonus state.
            persisted = memory_store.get_relationship("margot", "heather_first_neutral")
            assert (persisted.get("metadata") or {}).get("gift_first_done") is True
        finally:
            memory_store.close()


async def run_repeated_gift_dampening_check() -> None:
    """HH-006 repeated-gift dampening: spamming the same item_id to the same
    villager halves the affection delta from the threshold-th same-item gift
    onward. Trust, familiarity, mood, and the memory write are intentionally
    not affected — the moment still registers; only the optimal-play stat reward
    gets dulled.
    """
    with TemporaryDirectory() as tmp_dir:
        memory_store = MemoryStore(Path(tmp_dir) / "repeat_dampening.sqlite3")
        event_log = EventLog()
        engine = ConversationEngine(
            memory_store=memory_store,
            personality_store=PersonalityStore(),
            world_state=WorldState.create_default(),
            event_log=event_log,
        )

        try:
            # Burn first-of-kind on a generic warmup so the first Dusty Rose
            # below is *not* a first-of-kind interaction.
            await _burn_first_of_kind(
                engine,
                player_id="heather_spammer",
                villager_id="margot",
            )

            # Gift 1: Dusty Rose. Loved on Margot. Steady-state +5 affection.
            gift_1 = await engine.handle_gift(
                player_id="heather_spammer",
                villager_id="margot",
                item=LOVED_GIFT,
                context={"location": "town_square", "test": "dampening_gift_1"},
            )
            assert gift_1["mood"] == "delighted"
            gift_1_memory = next(
                memory for memory in memory_store.get_recent_memories("margot", limit=10)
                if memory.id == gift_1["memory_id"]
            )
            assert gift_1_memory.metadata["first_of_kind_bonus"] is False
            assert gift_1_memory.metadata["repeat_gift_dampened"] is False
            assert gift_1_memory.metadata["repeat_count_in_window"] == 0
            # Steady-state loved gift is +5 affection on top of the warmup (+2).
            affection_after_gift_1 = WARMUP_AFFECTION + 5
            assert gift_1["relationship"]["affection"] == affection_after_gift_1
            trust_after_gift_1 = WARMUP_TRUST + 2

            # Gift 2: same Dusty Rose. Repeat count in window = 1 (just the
            # first one), below the threshold of 2 prior. NOT dampened.
            gift_2 = await engine.handle_gift(
                player_id="heather_spammer",
                villager_id="margot",
                item=LOVED_GIFT,
                context={"location": "town_square", "test": "dampening_gift_2"},
            )
            assert gift_2["mood"] == "delighted"
            gift_2_memory = next(
                memory for memory in memory_store.get_recent_memories("margot", limit=10)
                if memory.id == gift_2["memory_id"]
            )
            assert gift_2_memory.metadata["repeat_gift_dampened"] is False
            assert gift_2_memory.metadata["repeat_count_in_window"] == 1
            affection_after_gift_2 = affection_after_gift_1 + 5
            assert gift_2["relationship"]["affection"] == affection_after_gift_2

            # Gift 3: same Dusty Rose. Repeat count in window = 2. Dampened!
            # +5 affection halves toward zero to +2 (int(5/2) = 2).
            gift_3 = await engine.handle_gift(
                player_id="heather_spammer",
                villager_id="margot",
                item=LOVED_GIFT,
                context={"location": "town_square", "test": "dampening_gift_3"},
            )
            assert gift_3["mood"] == "delighted", (
                "Repeated-gift dampening must not change the mood — the moment "
                "still registers; only the stat reward gets dulled."
            )
            gift_3_memory = next(
                memory for memory in memory_store.get_recent_memories("margot", limit=10)
                if memory.id == gift_3["memory_id"]
            )
            assert gift_3_memory.metadata["repeat_gift_dampened"] is True
            assert gift_3_memory.metadata["repeat_count_in_window"] == 2
            affection_after_gift_3 = affection_after_gift_2 + 2  # halved from +5 to +2
            assert gift_3["relationship"]["affection"] == affection_after_gift_3, (
                f"Third same-item gift should halve affection delta (5→2). "
                f"Expected total {affection_after_gift_3}, got {gift_3['relationship']['affection']}."
            )
            # Trust deltas should NOT be dampened. The doc is explicit: only
            # affection is halved.
            expected_trust_after_gift_3 = trust_after_gift_1 + 2 + 2  # gifts 2 and 3 each +2
            assert gift_3["relationship"]["trust"] == expected_trust_after_gift_3

            # Gift 4: a *different* loved item should reset to the non-dampened
            # path because dampening keys on item_id, not on overall gift count.
            # Chamomile Bundle is loved on Margot (her loved_tags include tea,
            # flower, garden, and handmade — all on the chamomile bundle) and
            # is not flagged by her dislikes.
            different_loved_gift = {
                "item_id": "chamomile_bundle",
                "display_name": "Chamomile Bundle",
                "category": "herb",
                "tags": ["flower", "tea", "garden", "handmade"],
                "quantity": 1,
            }
            gift_4 = await engine.handle_gift(
                player_id="heather_spammer",
                villager_id="margot",
                item=different_loved_gift,
                context={"location": "town_square", "test": "dampening_different_item"},
            )
            gift_4_memory = next(
                memory for memory in memory_store.get_recent_memories("margot", limit=10)
                if memory.id == gift_4["memory_id"]
            )
            assert gift_4_memory.metadata["repeat_gift_dampened"] is False, (
                "Switching to a different item_id must reset the dampening counter."
            )
            assert gift_4_memory.metadata["repeat_count_in_window"] == 0
            assert gift_4_memory.metadata["preference"] == "loved", (
                f"Chamomile Bundle should land loved on Margot, "
                f"got preference={gift_4_memory.metadata.get('preference')!r}."
            )
            affection_after_gift_4 = affection_after_gift_3 + 5  # loved, not dampened
            assert gift_4["relationship"]["affection"] == affection_after_gift_4, (
                f"Different loved item should land full +5 affection. Expected "
                f"total {affection_after_gift_4}, got {gift_4['relationship']['affection']}."
            )

            # The recent_gifts metadata on the relationship row should track
            # the four gifts above (3 Dusty Rose, 1 Chamomile Bundle) within
            # the trailing window, plus the warmup that opened the run.
            persisted = memory_store.get_relationship("margot", "heather_spammer")
            recent_gifts = (persisted.get("metadata") or {}).get("recent_gifts") or []
            recent_ids = [entry.get("item_id") for entry in recent_gifts]
            assert recent_ids.count("dusty_rose") == 3, (
                f"Expected 3 dusty_rose entries in recent_gifts, got {recent_ids!r}."
            )
            assert recent_ids.count("chamomile_bundle") == 1, (
                f"Expected 1 chamomile_bundle entry in recent_gifts, got {recent_ids!r}."
            )
            # Warmup item is also tracked on the same row.
            assert "tuning_warmup" in recent_ids
        finally:
            memory_store.close()


def main() -> None:
    asyncio.run(run_gift_relationship_check())
    asyncio.run(run_first_of_kind_gift_bonus_check())
    asyncio.run(run_repeated_gift_dampening_check())
    print("PASS: Gift relationship, memory, mood, and event updates are consistent.")


if __name__ == "__main__":
    main()
