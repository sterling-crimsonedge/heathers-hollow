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


async def run_clover_trust_unlock_check() -> None:
    """Clover's `trust_cap_unlocks_on_day=5` releases the trust override after day 5.

    Per `docs/AI_ARCHITECTURE.md`: "Clover moves familiarity faster and trust
    slower. Cap their trust at half the others' caps for the first 5 in-game
    days, then unlock." We model that as `trust_per_talk_cap=0` for the lock
    window plus `trust_cap_unlocks_on_day=5` so the override expires.

    Test scenario: drive a personal-disclosure turn at Clover on day 1 (trust
    stays at 0 because the override is active and `first_seen_day` is being
    stamped). Then jump the world to day 6 (i.e. 5 in-game days after first
    meeting) and drive another personal-disclosure turn — trust should now
    land at the global default (1) because the unlock has fired.
    """
    with TemporaryDirectory() as tmp_dir:
        memory_store = MemoryStore(Path(tmp_dir) / "tuning_clover_unlock.sqlite3")
        engine = _make_engine(memory_store)

        try:
            player = "heather_clover_unlock"

            # Turn 1: day 1. Override still active → trust stays at 0 even on
            # a personal-disclosure turn. The relationship row gets
            # first_seen_day=1 stamped so the unlock has a reference point.
            response_day1 = await engine.handle_player_message(
                player_id=player,
                villager_id="clover",
                text=POSITIVE_PERSONAL_TEXT,
                context={"location": "brook", "test": "clover_unlock_day1"},
            )
            assert response_day1["relationship"]["trust"] == 0, response_day1["relationship"]

            stored_day1 = memory_store.get_relationship("clover", player)
            stored_meta_day1 = stored_day1.get("metadata") or {}
            assert stored_meta_day1.get("first_seen_day") == 1, (
                f"first_seen_day should be stamped on first interaction; "
                f"got {stored_meta_day1!r}."
            )

            # Jump the world clock to day 6 by sliding start_minute_of_day
            # forward by 5 in-game days (5 × 1440 minutes). The unlock
            # condition is `world_day >= first_seen_day + 5`, so day 1 + 5 = 6
            # is the first eligible day.
            engine.world_state.start_minute_of_day += 5 * 1440
            world_now = engine.world_state.snapshot()
            assert world_now["day"] >= 6, (
                f"Expected world to advance to day 6+; got {world_now!r}."
            )

            response_unlocked = await engine.handle_player_message(
                player_id=player,
                villager_id="clover",
                text=POSITIVE_PERSONAL_TEXT,
                context={"location": "brook", "test": "clover_unlock_day6"},
            )
            assert response_unlocked["relationship"]["trust"] == 1, (
                f"After day-5 unlock, Clover's trust cap should revert to the "
                f"global default (1); got {response_unlocked['relationship']!r}."
            )

            # The first_seen_day field must not have been overwritten by the
            # day-6 update — it's a frozen first-meeting marker.
            stored_unlocked = memory_store.get_relationship("clover", player)
            stored_meta_unlocked = stored_unlocked.get("metadata") or {}
            assert stored_meta_unlocked.get("first_seen_day") == 1, (
                f"first_seen_day must not be overwritten by later turns; "
                f"got {stored_meta_unlocked!r}."
            )
        finally:
            memory_store.close()


async def run_clover_trust_unlock_locked_window_check() -> None:
    """Before the unlock fires, Clover's trust cap stays at the override (0).

    Drives a personal-disclosure turn at Clover on day 5 (still inside the
    5-day lock window since first_seen_day=1 → unlock at day 6). Trust must
    still cap at 0 — the unlock is strictly `>=` so day 5 is the *last* day
    the override holds.
    """
    with TemporaryDirectory() as tmp_dir:
        memory_store = MemoryStore(Path(tmp_dir) / "tuning_clover_locked.sqlite3")
        engine = _make_engine(memory_store)

        try:
            player = "heather_clover_locked"

            await engine.handle_player_message(
                player_id=player,
                villager_id="clover",
                text=POSITIVE_PERSONAL_TEXT,
                context={"location": "brook", "test": "clover_locked_day1"},
            )

            # Slide to day 5 — still within the lock window (need day 6+).
            engine.world_state.start_minute_of_day += 4 * 1440
            world_now = engine.world_state.snapshot()
            assert world_now["day"] == 5, (
                f"Expected world to land on day 5; got {world_now!r}."
            )

            response_day5 = await engine.handle_player_message(
                player_id=player,
                villager_id="clover",
                text=POSITIVE_PERSONAL_TEXT,
                context={"location": "brook", "test": "clover_locked_day5"},
            )
            assert response_day5["relationship"]["trust"] == 0, (
                f"On day 5 (before the day-6 unlock), Clover's trust must "
                f"still cap at the override (0); got "
                f"{response_day5['relationship']!r}."
            )
        finally:
            memory_store.close()


async def run_hugo_shared_weather_bonus_check() -> None:
    """Hugo's shared-weather bonus lands when the player notices the weather.

    Per `docs/AI_ARCHITECTURE.md`: "Hugo is slow-trust, slow-fall. His
    affection should move +1 less than the baseline for the first three
    visits, then move +1 more than the baseline after a 'shared weather'
    line." We model the second half as `shared_weather_affection_bonus=1` —
    a player text that mentions the current weather (rainy day) or time
    label (evening greeting) adds +1 affection on top of the capped talk
    delta, bypassing the per-day affection cap so the moment actually
    lands.

    Four readings:
      - Rainy world + "I love this rain" → +1 affection bonus stacks on
        the +1 cap (total +2). The bonus fires once.
      - Repeating the same rainy mention on the *same* in-game day must
        not fire again (anti-spam).
      - Day rollover allows another bonus fire.
      - Clear world + "I love this rain" → no bonus.
    """
    # Case A: bonus fires once on rainy day, stacks past the affection cap.
    with TemporaryDirectory() as tmp_dir:
        memory_store = MemoryStore(Path(tmp_dir) / "tuning_hugo_weather_rainy.sqlite3")
        engine = _make_engine(memory_store)
        engine.world_state.weather = "rainy"

        try:
            player = "heather_hugo_rainy"

            # Burn the first-of-kind bonus separately so the bonus delta isn't
            # masked by a Margot-style "first gift is a tier warmer" effect.
            response = await engine.handle_player_message(
                player_id=player,
                villager_id="hugo",
                text="thanks Hugo, I love this rain on the bakery roof",
                context={"location": "shop", "test": "hugo_weather_rainy_a"},
            )
            # Hugo's affection cap is 1 (from his tuning) plus the +1 bonus.
            # The text contains positive words ("thanks", "love") so the base
            # delta is +1. Total expected affection = 1 (capped) + 1 (bonus) = 2.
            assert response["relationship"]["affection"] == 2, (
                f"Rainy-day shared-weather bonus should stack past the cap; "
                f"got {response['relationship']!r}."
            )

            stored = memory_store.get_relationship("hugo", player)
            stored_meta = stored.get("metadata") or {}
            assert stored_meta.get("last_shared_weather_day") == 1, stored_meta
            marker = stored_meta.get("last_shared_weather_marker")
            assert isinstance(marker, str) and marker.startswith("weather:rain"), (
                f"Expected weather:rain marker; got {marker!r}."
            )
            assert stored_meta.get("first_seen_day") == 1, stored_meta

            # Case A2: another rainy mention on the same in-game day must NOT
            # fire the bonus again. The base talk path is also already capped,
            # so a second positive turn lands no further affection at all.
            response_repeat = await engine.handle_player_message(
                player_id=player,
                villager_id="hugo",
                text="thanks Hugo, I love this rain even more today",
                context={"location": "shop", "test": "hugo_weather_rainy_repeat"},
            )
            assert response_repeat["relationship"]["affection"] == 2, (
                f"Shared-weather bonus must not refire on the same in-game day; "
                f"got {response_repeat['relationship']!r}."
            )
        finally:
            memory_store.close()

    # Case B: day rollover allows the bonus to fire again on a new in-game day.
    with TemporaryDirectory() as tmp_dir:
        memory_store = MemoryStore(Path(tmp_dir) / "tuning_hugo_weather_dayroll.sqlite3")
        engine = _make_engine(memory_store)
        engine.world_state.weather = "rainy"

        try:
            player = "heather_hugo_dayroll"
            await engine.handle_player_message(
                player_id=player,
                villager_id="hugo",
                text="thanks Hugo, the rain is so cozy this morning",
                context={"location": "shop", "test": "hugo_weather_dayroll_day1"},
            )
            stored_after_day1 = memory_store.get_relationship("hugo", player)
            assert stored_after_day1["affection"] == 2, stored_after_day1

            # Slide world clock to day 2 so the bonus is eligible to fire again.
            engine.world_state.start_minute_of_day += 1 * 1440
            world_now = engine.world_state.snapshot()
            assert world_now["day"] == 2, world_now

            response_day2 = await engine.handle_player_message(
                player_id=player,
                villager_id="hugo",
                text="thanks Hugo, more rain again - lovely",
                context={"location": "shop", "test": "hugo_weather_dayroll_day2"},
            )
            # Day-2 talk caps reset (+1 cap + +1 bonus = +2 on day 2 on top of
            # the day-1 total of 2) → cumulative affection = 4.
            assert response_day2["relationship"]["affection"] == 4, (
                f"Shared-weather bonus should re-fire on a new in-game day; "
                f"got {response_day2['relationship']!r}."
            )
            stored_day2 = memory_store.get_relationship("hugo", player)
            assert (stored_day2.get("metadata") or {}).get(
                "last_shared_weather_day"
            ) == 2, stored_day2
        finally:
            memory_store.close()

    # Case C: clear world + rain mention → no bonus.
    with TemporaryDirectory() as tmp_dir:
        memory_store = MemoryStore(Path(tmp_dir) / "tuning_hugo_weather_clear.sqlite3")
        engine = _make_engine(memory_store)
        engine.world_state.weather = "clear"

        try:
            player = "heather_hugo_clear"
            response = await engine.handle_player_message(
                player_id=player,
                villager_id="hugo",
                text="thanks Hugo, I love this rain on the bakery roof",
                context={"location": "shop", "test": "hugo_weather_clear"},
            )
            # No bonus → just the +1 capped affection from the positive talk.
            assert response["relationship"]["affection"] == 1, (
                f"Shared-weather bonus must not fire when the world is clear; "
                f"got {response['relationship']!r}."
            )
            stored = memory_store.get_relationship("hugo", player)
            stored_meta = stored.get("metadata") or {}
            assert "last_shared_weather_day" not in stored_meta, stored_meta
        finally:
            memory_store.close()


async def run_hugo_shared_evening_bonus_check() -> None:
    """Hugo's bonus also fires on an "evening greeting" when time_label matches.

    The shared-weather hook intentionally covers time-of-day language too —
    "good evening, Hugo" on the evening time_label is the same cozy moment
    as a rainy-day greeting. The match requires the literal time label word
    in the text *and* the world's current time_label to be that value.
    """
    with TemporaryDirectory() as tmp_dir:
        memory_store = MemoryStore(Path(tmp_dir) / "tuning_hugo_evening.sqlite3")
        engine = _make_engine(memory_store)
        # Slide the world clock to 17:00 (start_minute_of_day=8*60=480 by
        # default; 17:00 = 1020 minutes from the start of day). This puts
        # time_label at "evening".
        engine.world_state.start_minute_of_day = 17 * 60
        world_now = engine.world_state.snapshot()
        assert world_now["time_label"] == "evening", world_now

        try:
            response = await engine.handle_player_message(
                player_id="heather_hugo_evening",
                villager_id="hugo",
                text="thanks Hugo, good evening to you",
                context={"location": "shop", "test": "hugo_evening_bonus"},
            )
            # +1 capped + +1 bonus = +2 affection.
            assert response["relationship"]["affection"] == 2, (
                f"Evening shared-weather bonus should stack past the cap; "
                f"got {response['relationship']!r}."
            )
            stored = memory_store.get_relationship("hugo", "heather_hugo_evening")
            stored_meta = stored.get("metadata") or {}
            marker = stored_meta.get("last_shared_weather_marker")
            assert marker == "time:evening", (
                f"Expected time:evening marker; got {marker!r}."
            )
        finally:
            memory_store.close()


async def run_fern_no_shared_weather_bonus_check() -> None:
    """Fern has no `shared_weather_affection_bonus`, so the hook is a no-op.

    This is the regression guardrail: the bonus is opt-in. A villager without
    the tuning key must see no bonus and no `last_shared_weather_day` write
    on the relationship row even when the player mentions matching weather.
    """
    with TemporaryDirectory() as tmp_dir:
        memory_store = MemoryStore(Path(tmp_dir) / "tuning_fern_no_bonus.sqlite3")
        engine = _make_engine(memory_store)
        engine.world_state.weather = "rainy"

        try:
            response = await engine.handle_player_message(
                player_id="heather_fern_no_bonus",
                villager_id="fern",
                text="thanks Fern, I love this rain on the garden",
                context={"location": "garden", "test": "fern_no_bonus"},
            )
            # Fern's affection cap is the default (2), and the talk text has
            # positive words → +1 affection. No bonus stacks on top.
            assert response["relationship"]["affection"] == 1, (
                f"Fern (no shared_weather_affection_bonus) should not gain "
                f"a bonus; got {response['relationship']!r}."
            )
            stored = memory_store.get_relationship("fern", "heather_fern_no_bonus")
            stored_meta = stored.get("metadata") or {}
            assert "last_shared_weather_day" not in stored_meta, stored_meta
            assert "last_shared_weather_marker" not in stored_meta, stored_meta
        finally:
            memory_store.close()


async def run_all_checks() -> None:
    await run_margot_slow_warming_check()
    await run_hugo_gruff_talk_check()
    await run_clover_testing_trust_check()
    await run_fern_default_caps_check()
    await run_loved_gift_pin_duration_check()
    await run_first_gift_bonus_disable_check()
    await run_clover_trust_unlock_check()
    await run_clover_trust_unlock_locked_window_check()
    await run_hugo_shared_weather_bonus_check()
    await run_hugo_shared_evening_bonus_check()
    await run_fern_no_shared_weather_bonus_check()


def main() -> None:
    asyncio.run(run_all_checks())
    print("PASS: Per-villager tuning JSON overrides talk caps, pin duration, and first-of-kind bonus.")


if __name__ == "__main__":
    main()
