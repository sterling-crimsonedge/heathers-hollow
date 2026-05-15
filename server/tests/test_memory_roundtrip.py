"""Smoke test for the villager memory loop.

Run from the repo root:

    python -m server.tests.test_memory_roundtrip

This test uses the local fallback conversation path, so it does not require
ANTHROPIC_API_KEY. The live Claude path should be tested separately once
credentials are configured.
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


async def run_roundtrip() -> bool:
    with TemporaryDirectory() as tmp_dir:
        memory_store = MemoryStore(Path(tmp_dir) / "roundtrip.sqlite3")
        engine = ConversationEngine(
            memory_store=memory_store,
            personality_store=PersonalityStore(),
            world_state=WorldState.create_default(),
            event_log=EventLog(),
        )

        await engine.handle_player_message(
            player_id="heather",
            villager_id="margot",
            text="Margot, my favorite color today is marigold yellow.",
            context={"location": "town_square"},
        )
        response = await engine.handle_player_message(
            player_id="heather",
            villager_id="margot",
            text="Do you remember what my favorite color is?",
            context={"location": "town_square"},
        )

        reply = response["text"].lower()
        return "marigold" in reply or "yellow" in reply


def main() -> None:
    remembered = asyncio.run(run_roundtrip())
    if remembered:
        print("PASS: Margot remembered the prior conversation.")
        return
    raise SystemExit("FAIL: Margot did not reference the remembered color.")


if __name__ == "__main__":
    main()
