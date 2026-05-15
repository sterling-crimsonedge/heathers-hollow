"""Smoke test for loadable personality configs.

Run from the repo root:

    python -m server.tests.test_personality_configs
"""

from __future__ import annotations

from server.ai.mood import MOODS
from server.ai.personality import PersonalityStore


TIME_LABELS = {"morning", "afternoon", "evening", "night"}
RELATIONSHIP_KEYS = {
    "starting_affection": (-100, 100),
    "starting_trust": (0, 100),
    "starting_familiarity": (0, 100),
    "starting_tension": (0, 100),
}


def run_personality_config_check() -> None:
    store = PersonalityStore()
    villager_ids = store.list_ids()
    assert villager_ids, "Expected at least one personality config."

    for villager_id in villager_ids:
        personality = store.load(villager_id)
        assert personality.id == villager_id
        assert personality.config_path.stem == villager_id
        assert personality.display_name.strip()
        assert personality.species.strip()
        assert personality.archetype.strip()
        assert personality.core_traits, f"{villager_id} needs core traits."
        assert personality.values, f"{villager_id} needs values."
        assert personality.likes, f"{villager_id} needs likes."
        assert personality.dislikes, f"{villager_id} needs dislikes."
        assert personality.private_goals, f"{villager_id} needs private goals."
        assert personality.speaking_style.tone.strip()
        assert personality.speaking_style.quirks, f"{villager_id} needs speaking quirks."
        assert len(personality.system_prompt.split()) >= 30
        assert "ai model" in personality.system_prompt.lower()
        assert "database" in personality.system_prompt.lower()
        assert "api" in personality.system_prompt.lower()

        mood_keys = set(personality.mood_baseline_by_time)
        assert mood_keys == TIME_LABELS, f"{villager_id} mood baselines must cover {sorted(TIME_LABELS)}."
        unknown_moods = set(personality.mood_baseline_by_time.values()) - set(MOODS)
        assert not unknown_moods, f"{villager_id} uses unsupported moods: {sorted(unknown_moods)}."

        assert personality.relationships, f"{villager_id} needs relationship seeds."
        for subject_id, relationship in personality.relationships.items():
            assert str(subject_id).strip()
            assert isinstance(relationship, dict)
            for key, bounds in RELATIONSHIP_KEYS.items():
                if key not in relationship:
                    continue
                value = relationship[key]
                assert isinstance(value, int), f"{villager_id}.{subject_id}.{key} must be an int."
                low, high = bounds
                assert low <= value <= high, f"{villager_id}.{subject_id}.{key} must be within {bounds}."

        # home_location is optional but, when supplied, must be a non-empty
        # string so clients can place the villager spatially. The current MVP
        # cast (Margot/Fern/Hugo/Clover) all supply it; older configs may not.
        assert isinstance(personality.home_location, str)
        if personality.home_location:
            assert personality.home_location.strip(), (
                f"{villager_id} home_location, when set, must be a non-empty string."
            )

        # Optional HH-060 enrichment fields: when supplied they must be well-typed
        # so the prompt_block lines stay readable. Absence is allowed for all four.
        assert isinstance(personality.quirks, list)
        for entry in personality.quirks:
            assert isinstance(entry, str) and entry.strip(), (
                f"{villager_id} quirks entries must be non-empty strings."
            )
        assert isinstance(personality.backstory_anchors, list)
        for entry in personality.backstory_anchors:
            assert isinstance(entry, str) and entry.strip(), (
                f"{villager_id} backstory_anchors entries must be non-empty strings."
            )
        assert isinstance(personality.default_mood, str)
        if personality.default_mood:
            assert personality.default_mood in MOODS, (
                f"{villager_id} default_mood {personality.default_mood!r} must be a known mood."
            )

        # HH-062 optional per-villager loved-gift rubric. Entries must be
        # non-empty lowercase strings so the gift-preference set intersection
        # works without surprise casing bugs. Empty is allowed for backward
        # compatibility — the engine falls back to DEFAULT_LOVED_TAGS.
        assert isinstance(personality.loved_tags, list)
        for entry in personality.loved_tags:
            assert isinstance(entry, str) and entry.strip(), (
                f"{villager_id} loved_tags entries must be non-empty strings."
            )
            assert entry == entry.lower(), (
                f"{villager_id} loved_tags entry {entry!r} must be lowercase."
            )

        prompt = personality.prompt_block()
        if personality.quirks:
            assert "Character quirks:" in prompt, (
                f"{villager_id} prompt_block must surface quirks when supplied."
            )
        else:
            assert "Character quirks:" not in prompt, (
                f"{villager_id} prompt_block must not invent a quirks line when none supplied."
            )
        if personality.backstory_anchors:
            assert "Backstory anchors:" in prompt
        else:
            assert "Backstory anchors:" not in prompt
        if personality.default_mood:
            assert "Default mood:" in prompt
        else:
            assert "Default mood:" not in prompt

    fern = store.load("fern")
    hugo = store.load("hugo")

    assert fern.display_name == "Fern"
    assert hugo.display_name == "Hugo"
    assert "herbalist" in fern.prompt_block().lower()
    assert "baker" in hugo.prompt_block().lower()
    assert fern.prompt_block() != hugo.prompt_block()
    assert "fern" in store.list_ids()
    assert "hugo" in store.list_ids()

    # The canonical MVP cast must each carry a distinct home_location so the
    # web/Godot prototypes can place all four villagers spatially without
    # hardcoded names. Defaults match docs/VILLAGER_CAST.md's spatial reads.
    expected_home_locations = {
        "margot": "town_square",
        "fern": "garden",
        "hugo": "shop",
        "clover": "brook",
    }
    for villager_id, expected in expected_home_locations.items():
        if villager_id not in store.list_ids():
            continue
        actual = store.load(villager_id).home_location
        assert actual == expected, (
            f"{villager_id} home_location is {actual!r}; expected {expected!r}."
        )

    # HH-062: the canonical MVP cast each ships an explicit loved_tags rubric
    # so the gift engine can score "loved" per villager rather than against a
    # single global set. Each rubric should include at least one tag that
    # *only* fits its villager so the demo shows four distinct reactions
    # (see server/world/inventory.py for the matching items).
    expected_loved_tag_signatures = {
        "margot": {"porcelain", "flower"},      # Dusty Rose / porcelain button territory
        "fern": {"lavender", "herb"},            # lavender sachet, chamomile bundle
        "hugo": {"bread", "sea"},                 # honey oat crust, sea glass
        "clover": {"marigold", "shiny"},          # marigold sprig, sea glass shard
    }
    for villager_id, required in expected_loved_tag_signatures.items():
        if villager_id not in store.list_ids():
            continue
        loved_tags = set(store.load(villager_id).loved_tags)
        missing = required - loved_tags
        assert not missing, (
            f"{villager_id} loved_tags missing required signature tags {sorted(missing)}; "
            f"current loved_tags = {sorted(loved_tags)}."
        )


def main() -> None:
    run_personality_config_check()
    print("PASS: Personality configs load and satisfy schema checks.")


if __name__ == "__main__":
    main()
