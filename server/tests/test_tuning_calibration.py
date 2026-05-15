"""Smoke test for HH-006 per-villager `tuning` JSON overrides.

Run from the repo root:

    python -m server.tests.test_tuning_calibration

Each of the four canonical MVP villagers (Margot/Fern/Hugo/Clover) can ship an
optional `tuning` block that overrides the global HH-006 talk-cap constants and
the loved-gift mood-pin duration. The fields are intentionally narrow:

  - `affection_per_talk_cap`        (int)   — overrides TALK_AFFECTION_DAILY_CAP
  - `trust_per_talk_cap`            (int)   — overrides TALK_TRUST_DAILY_CAP
  - `negative_talk_per_day_cap`     (int)   — overrides TALK_NEGATIVE_DAILY_CAP
  - `loved_gift_mood_lock_hours`    (float) — overrides MoodTracker.pin window
  - `first_gift_bonus_tier`         (int)   — 0 disables the first-of-kind bump

`tuning` is not exposed in `public_villager_summary` (verified in
`test_api_contract.py` and `test_personality_configs.py`), so it stays
server-private — it's a mechanical knob, not a stat sheet for clients.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from server.ai.conversation import (
    ConversationEngine,
    TALK_AFFECTION_DAILY_CAP,
    TALK_NEGATIVE_DAILY_CAP,
    TALK_TRUST_DAILY_CAP,
)
from server.ai.memory import MemoryStore
from server.ai.personality import PersonalityStore
from server.world.events import EventLog
from server.world.state import WorldState


POSITIVE_PERSONAL_TEXT = "I love porcelain teacups and my favorite flower is lavender."


MARGOT_LOVED_GIFT = {
    "item_id": "dusty_rose",
    "display_name": "Dusty Rose",
    "category": "flower",
    "tags": ["flower", "garden", "soft_color", "handmade"],
    "quantity": 1,
}


HUGO_LOVED_GIFT = {
    "item_id": "honey_oat_crust",
    "display_name": "Honey Oat Crust",
    "category": "baked",
    "tags": ["bread", "baked", "warm", "handmade"],
    "quantity": 1,
}


CLOVER_LOVED_GIFT = {
    "item_id": "marigold_sprig",
    "display_name": "Marigold Sprig",
    "category": "flower",
    "tags": ["flower", "marigold", "orange", "garden"],
    "quantity": 1,
}


# Used to burn the HH-006 first-of-kind tier bump before steady-state assertions
# so each test sees the native per-villager tuning behaviour rather than the
# generic warmth of "Heather brought *something*".
WARMUP_GIFT = {
    "item_id": "tuning_warmup",
    "display_name": "Tuning Warmup",
    "category": "warmup",
    "tags": ["warmup"],
    "quantity": 1,
}


async def _drive_turns(
    engine: ConversationEngine,
    *,
    player_id: str,
    villager_id: str,
    text: str,
    count: int,
    location: str,
) -> dict[str, Any]:
    response: dict[str, Any] = {}
    for _ in range(count):
        response = await engine.handle_player_message(
            player_id=player_id,
            villager_id=villager_id,
            text=text,
            context={"location": location, "test": "tuning_calibration"},
        )
    return response


async def _burn_first_of_kind(
    engine: ConversationEngine,
    *,
    player_id: str,
    villager_id: str,
    location: str,
) -> None:
    await engine.handle_gift(
        player_id=player_id,
        villager_id=villager_id,
        item=WARMUP_GIFT,
        context={"location": location, "test": "tuning_warmup"},
    )


def _read_self_pin(memory_store: MemoryStore, villager_id: str) -> dict[str, Any]:
    self_relationship = memory_store.get_relationship(villager_id, "self")
    return (self_relationship.get("metadata") or {}).get("mood_state") or {}


def _make_engine(memory_store: MemoryStore) -> ConversationEngine:
    return ConversationEngine(
        memory_store=memory_store,
        personality_store=PersonalityStore(),
        world_state=WorldState.create_default(),
        event_log=EventLog(),
    )


async def run_margot_slow_warming_check() -> None:
    """Margot's tuning sets affection_per_talk_cap=1 and trust_per_talk_cap=0.

    Ten positive-personal turns at Margot must land at her tightened caps
    (affection=1, trust=0) rather than the global defaults (2, 1) the doc
    treats as too easy for "fragile and slow-warming Margot".
    """
    with TemporaryDirectory() as tmp_dir:
        memory_store = MemoryStore(Path(tmp_dir) / "tuning_margot_talk.sqlite3")
        engine = _make_engine(memory_store)

        try:
            positive_player = "heather_tuning_margot_positive"
            response = await _drive_turns(
                engine,
                player_id=positive_player,
                villager_id="margot",
                text=POSITIVE_PERSONAL_TEXT,
                count=10,
                location="town_square",
            )
            relationship = response["relationship"]
            assert relationship["affection"] == 1, (
                f"Margot affection_per_talk_cap=1 should cap fresh-player affection "
                f"at 1 after 10 positive turns, got {relationship['affection']!r}."
            )
            assert relationship["trust"] == 0, (
                f"Margot trust_per_talk_cap=0 should keep fresh-player trust at 0 "
                f"after 10 personal-disclosure turns, got {relationship['trust']!r}."
            )
            # Familiarity is uncapped — talk still always grows the social ledger.
            assert relationship["familiarity"] >= 10, relationship

            stored = memory_store.get_relationship("margot", positive_player)
            stored_meta = stored.get("metadata", {})
            assert stored_meta.get("talk_affection_today") == 1, stored_meta
            assert stored_meta.get("talk_trust_today") == 0, stored_meta
        finally:
            memory_store.close()


async def run_hugo_gruff_talk_check() -> None:
    """Hugo's tuning sets affection_per_talk_cap=1 but keeps trust at default.

    Per `docs/AI_ARCHITECTURE.md`: "Hugo is slow-trust, slow-fall. His affection
    should move +1 less than the baseline for the first three visits." We model
    that here by halving his per-day affection cap. Trust still respects the
    global cap (1) so a single personal-disclosure turn lands trust=1.
    """
    with TemporaryDirectory() as tmp_dir:
        memory_store = MemoryStore(Path(tmp_dir) / "tuning_hugo_talk.sqlite3")
        engine = _make_engine(memory_store)

        try:
            positive_player = "heather_tuning_hugo_positive"
            response = await _drive_turns(
                engine,
                player_id=positive_player,
                villager_id="hugo",
                text=POSITIVE_PERSONAL_TEXT,
                count=10,
                location="shop",
            )
            relationship = response["relationship"]
            assert relationship["affection"] == 1, (
                f"Hugo affection_per_talk_cap=1 should cap fresh-player affection "
                f"at 1 after 10 positive turns, got {relationship['affection']!r}."
            )
            # Hugo doesn't override trust_per_talk_cap, so the global default
            # (1) applies: a single personal-disclosure turn lands trust=1.
            assert relationship["trust"] == TALK_TRUST_DAILY_CAP, (
                f"Hugo should keep the global trust cap ({TALK_TRUST_DAILY_CAP}); "
                f"got {relationship['trust']!r}."
            )
        finally:
            memory_store.close()


async def run_clover_testing_trust_check() -> None:
    """Clover's tuning sets trust_per_talk_cap=0 — they're testing Heather.

    Per the doc: "Clover moves familiarity faster and trust slower. Cap their
    trust at half the others' caps for the first 5 in-game days, then unlock."
    We model the simpler version: trust does not move from talk at all for
    Clover (they want to see Heather *keep promises*, which is a future
    "kept-commitment" event hook, not a free reward for asking nice questions).
    Affection still respects the global default.
    """
    with TemporaryDirectory() as tmp_dir:
        memory_store = MemoryStore(Path(tmp_dir) / "tuning_clover_talk.sqlite3")
        engine = _make_engine(memory_store)

        try:
            positive_player = "heather_tuning_clover_positive"
            response = await _drive_turns(
                engine,
                player_id=positive_player,
                villager_id="clover",
                text=POSITIVE_PERSONAL_TEXT,
                count=10,
                location="brook",
            )
            relationship = response["relationship"]
            # Clover keeps the default affection cap (2).
            assert relationship["affection"] == TALK_AFFECTION_DAILY_CAP, (
                f"Clover should keep the global affection cap "
                f"({TALK_AFFECTION_DAILY_CAP}); got {relationship['affection']!r}."
            )
            # Trust cap of 0 means even 10 personal-disclosure turns land trust=0.
            assert relationship["trust"] == 0, (
                f"Clover trust_per_talk_cap=0 should keep fresh-player trust at 0 "
                f"after 10 personal-disclosure turns, got {relationship['trust']!r}."
            )
        finally:
            memory_store.close()


async def run_fern_default_caps_check() -> None:
    """Fern ships no tuning block — she must keep the global defaults.

    This is the regression guardrail: the per-villager `tuning` plumbing is
    additive, and any villager without a `tuning` block should behave exactly
    like the pre-HH-006-tuning baseline.
    """
    with TemporaryDirectory() as tmp_dir:
        memory_store = MemoryStore(Path(tmp_dir) / "tuning_fern_default.sqlite3")
        engine = _make_engine(memory_store)

        try:
            positive_player = "heather_tuning_fern_default"
            response = await _drive_turns(
                engine,
                player_id=positive_player,
                villager_id="fern",
                text=POSITIVE_PERSONAL_TEXT,
                count=10,
                location="garden",
            )
            relationship = response["relationship"]
            assert relationship["affection"] == TALK_AFFECTION_DAILY_CAP, (
                f"Fern (no tuning) should hit the default affection cap "
                f"({TALK_AFFECTION_DAILY_CAP}); got {relationship['affection']!r}."
            )
            assert relationship["trust"] == TALK_TRUST_DAILY_CAP, (
                f"Fern (no tuning) should hit the default trust cap "
                f"({TALK_TRUST_DAILY_CAP}); got {relationship['trust']!r}."
            )
            # And negative_cap stays at default 1 too.
            assert TALK_NEGATIVE_DAILY_CAP == 1
        finally:
            memory_store.close()


async def run_loved_gift_pin_duration_check() -> None:
    """`loved_gift_mood_lock_hours` should change the loved-gift pin window.

    Three readings:
      - Margot's tuning sets the lock to 3 hours → pin window ≈ 180 minutes.
      - Hugo's tuning also sets the lock to 3 hours → pin window ≈ 180 minutes.
      - Clover's tuning sets the lock to 1.5 hours → pin window ≈ 90 minutes.
      - Fern (no override) falls back to the default ≈ 120 minutes.

    The exact pin_until_minute depends on the world clock at the moment the
    gift fires, so we assert the *delta* (pinned_until_minute - now) which is
    the actual duration in monotonic in-game minutes.
    """
    expectations = (
        ("margot", MARGOT_LOVED_GIFT, "town_square", 180),
        ("hugo", HUGO_LOVED_GIFT, "shop", 180),
        ("clover", CLOVER_LOVED_GIFT, "brook", 90),
    )

    for villager_id, gift_payload, location, expected_minutes in expectations:
        with TemporaryDirectory() as tmp_dir:
            memory_store = MemoryStore(
                Path(tmp_dir) / f"tuning_pin_{villager_id}.sqlite3"
            )
            engine = _make_engine(memory_store)

            try:
                # Burn the first-of-kind bonus so the asserted gift below is
                # exercised as a steady-state loved gift, not a freebie warmth.
                await _burn_first_of_kind(
                    engine,
                    player_id=f"heather_pin_{villager_id}",
                    villager_id=villager_id,
                    location=location,
                )

                world_snapshot_before = engine.world_state.snapshot()
                expected_minutes_at_pin = (
                    (int(world_snapshot_before.get("day", 1) or 1) - 1) * 1440
                    + int(world_snapshot_before.get("minute_of_day", 0) or 0)
                )

                payload = await engine.handle_gift(
                    player_id=f"heather_pin_{villager_id}",
                    villager_id=villager_id,
                    item=gift_payload,
                    context={"location": location, "test": "loved_pin"},
                )
                assert payload["mood"] == "delighted", (
                    f"{villager_id} loved-gift should mood=delighted; "
                    f"got {payload['mood']!r}."
                )

                pin = _read_self_pin(memory_store, villager_id)
                pinned_until = pin.get("pinned_until_minute")
                assert isinstance(pinned_until, int), (
                    f"{villager_id} loved-gift should set pinned_until_minute; "
                    f"got {pinned_until!r}."
                )
                delta = pinned_until - expected_minutes_at_pin
                # Allow a small slack (a few in-game minutes) in case the world
                # clock ticks once between snapshot and pin.
                assert abs(delta - expected_minutes) <= 5, (
                    f"{villager_id} pin window should be ≈{expected_minutes} "
                    f"minutes; got {delta} (pinned_until={pinned_until!r}, "
                    f"baseline={expected_minutes_at_pin!r})."
                )
            finally:
                memory_store.close()


async def run_first_gift_bonus_disable_check() -> None:
    """`first_gift_bonus_tier=0` opts a villager out of the HH-006 first bump.

    This is exercised against an in-memory PersonalityStore using Margot's
    config with an overridden tuning block. The asserted behaviour: a *neutral*
    first gift to a tuning-opt-out villager should land as neutral (mood=shy),
    not as liked (mood=warm) — the gesture-of-bringing-anything bonus is off.
    """
    import copy

    from server.ai.personality import Personality, PersonalityStore as RealStore

    real_store = RealStore()
    margot = real_store.load("margot")

    # Build a frozen Margot-with-no-first-gift-bonus personality without
    # touching the on-disk JSON. We use dataclasses.replace via attribute
    # copy because Personality is frozen.
    overridden_tuning = dict(margot.tuning)
    overridden_tuning["first_gift_bonus_tier"] = 0
    overridden_margot = Personality(
        id=margot.id,
        display_name=margot.display_name,
        species=margot.species,
        archetype=margot.archetype,
        core_traits=list(margot.core_traits),
        values=list(margot.values),
        speaking_style=margot.speaking_style,
        likes=list(margot.likes),
        dislikes=list(margot.dislikes),
        relationships=copy.deepcopy(margot.relationships),
        private_goals=list(margot.private_goals),
        mood_baseline_by_time=dict(margot.mood_baseline_by_time),
        system_prompt=margot.system_prompt,
        config_path=margot.config_path,
        quirks=list(margot.quirks),
        backstory_anchors=list(margot.backstory_anchors),
        default_mood=margot.default_mood,
        home_location=margot.home_location,
        loved_tags=list(margot.loved_tags),
        tuning=overridden_tuning,
    )

    class _PatchedStore(RealStore):
        def load(self, villager_id: str) -> Personality:  # type: ignore[override]
            if villager_id == "margot":
                return overridden_margot
            return super().load(villager_id)

    neutral_gift = {
        "item_id": "smooth_pebble",
        "display_name": "Smooth Pebble",
        "category": "trinket",
        "tags": ["stone", "smooth", "pocket"],
        "quantity": 1,
    }

    with TemporaryDirectory() as tmp_dir:
        memory_store = MemoryStore(Path(tmp_dir) / "tuning_first_gift_disabled.sqlite3")
        engine = ConversationEngine(
            memory_store=memory_store,
            personality_store=_PatchedStore(),
            world_state=WorldState.create_default(),
            event_log=EventLog(),
        )
        try:
            response = await engine.handle_gift(
                player_id="heather_no_bonus",
                villager_id="margot",
                item=neutral_gift,
                context={"location": "town_square", "test": "first_gift_disabled"},
            )
            # Without the first-of-kind tier bump, a neutral gift stays neutral
            # → mood "shy" rather than the liked "warm".
            assert response["mood"] == "shy", (
                f"first_gift_bonus_tier=0 should suppress the HH-006 bump; "
                f"expected mood=shy, got {response['mood']!r}."
            )
            memory_id = response["memory_id"]
            memory = next(
                memory for memory in memory_store.get_recent_memories("margot", limit=5)
                if memory.id == memory_id
            )
            assert memory.metadata["preference"] == "neutral"
            assert memory.metadata["base_preference"] == "neutral"
            # The bump flag should be False — the villager opted out.
            assert memory.metadata["first_of_kind_bonus"] is False
            # We still mark gift_first_done so the opt-out is durable for the
            # lifetime of the (player, villager) pair.
            persisted = memory_store.get_relationship("margot", "heather_no_bonus")
            assert (persisted.get("metadata") or {}).get("gift_first_done") is True
        finally:
            memory_store.close()


async def run_all_checks() -> None:
    await run_margot_slow_warming_check()
    await run_hugo_gruff_talk_check()
    await run_clover_testing_trust_check()
    await run_fern_default_caps_check()
    await run_loved_gift_pin_duration_check()
    await run_first_gift_bonus_disable_check()


def main() -> None:
    asyncio.run(run_all_checks())
    print("PASS: Per-villager tuning JSON overrides talk caps, pin duration, and first-of-kind bonus.")


if __name__ == "__main__":
    main()
