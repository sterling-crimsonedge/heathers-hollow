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


def main() -> None:
    run_personality_config_check()
    print("PASS: Personality configs load and satisfy schema checks.")


if __name__ == "__main__":
    main()
