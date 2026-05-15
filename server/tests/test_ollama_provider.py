"""Smoke tests for the optional Ollama conversation provider.

Run from the repo root:

    python -m server.tests.test_ollama_provider

The tests fake the Ollama transport and do not require Ollama to be installed.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from server.ai.conversation import ConversationEngine
from server.ai.memory import MemoryStore
from server.ai.personality import PersonalityStore
from server.world.events import EventLog
from server.world.state import WorldState


ENV_KEYS = {
    "ANTHROPIC_API_KEY",
    "HOLLOW_LLM_PROVIDER",
    "OLLAMA_BASE_URL",
    "OLLAMA_MODEL",
    "OLLAMA_TIMEOUT_SECONDS",
}


@contextmanager
def patched_provider_env(values: dict[str, str]) -> Iterator[None]:
    previous = {key: os.environ.get(key) for key in ENV_KEYS}
    try:
        for key in ENV_KEYS:
            os.environ.pop(key, None)
        os.environ.update(values)
        yield
    finally:
        for key in ENV_KEYS:
            if previous[key] is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous[key] or ""


def build_engine(
    db_path: Path,
    ollama_transport: Any,
) -> tuple[ConversationEngine, MemoryStore]:
    memory_store = MemoryStore(db_path)
    engine = ConversationEngine(
        memory_store=memory_store,
        personality_store=PersonalityStore(),
        world_state=WorldState.create_default(),
        event_log=EventLog(),
        ollama_transport=ollama_transport,
    )
    return engine, memory_store


async def test_ollama_provider_uses_chat_payload() -> None:
    captured: dict[str, Any] = {}

    def fake_ollama(url: str, payload: dict[str, Any], timeout_seconds: float) -> dict[str, Any]:
        captured["url"] = url
        captured["payload"] = payload
        captured["timeout_seconds"] = timeout_seconds
        return {
            "message": {
                "role": "assistant",
                "content": "I remember the porcelain teacup, tucked where the morning light finds it.",
            }
        }

    with TemporaryDirectory() as tmp_dir:
        with patched_provider_env(
            {
                "HOLLOW_LLM_PROVIDER": "ollama",
                "OLLAMA_BASE_URL": "http://ollama.test",
                "OLLAMA_MODEL": "cozy-test-model",
                "OLLAMA_TIMEOUT_SECONDS": "4.5",
            }
        ):
            engine, memory_store = build_engine(Path(tmp_dir) / "ollama.sqlite3", fake_ollama)
            try:
                response = await engine.handle_player_message(
                    player_id="heather",
                    villager_id="margot",
                    text="Please remember the porcelain teacup by the window.",
                    context={"location": "town_square", "test": "ollama_provider"},
                )
            finally:
                memory_store.close()

    assert response["type"] == "villager_reply"
    assert "porcelain teacup" in response["text"]
    assert captured["url"] == "http://ollama.test/api/chat"
    assert captured["timeout_seconds"] == 4.5
    payload = captured["payload"]
    assert payload["model"] == "cozy-test-model"
    assert payload["stream"] is False
    assert payload["options"]["temperature"] == 0.8
    assert payload["options"]["num_predict"] == 220
    assert [message["role"] for message in payload["messages"]] == ["system", "user"]
    assert "Reply as Margot only" in payload["messages"][0]["content"]
    assert "heather says: Please remember the porcelain teacup by the window." == payload["messages"][1]["content"]


async def test_ollama_provider_falls_back_on_invalid_response() -> None:
    calls: list[dict[str, Any]] = []

    def fake_ollama(url: str, payload: dict[str, Any], timeout_seconds: float) -> dict[str, Any]:
        calls.append({"url": url, "payload": payload, "timeout_seconds": timeout_seconds})
        return {"message": {"role": "assistant", "content": "   "}}

    with TemporaryDirectory() as tmp_dir:
        with patched_provider_env({"HOLLOW_LLM_PROVIDER": "ollama"}):
            engine, memory_store = build_engine(Path(tmp_dir) / "ollama_fallback.sqlite3", fake_ollama)
            try:
                response = await engine.handle_player_message(
                    player_id="heather",
                    villager_id="margot",
                    text="Hello Margot.",
                    context={"location": "town_square", "test": "ollama_invalid_fallback"},
                )
            finally:
                memory_store.close()

    assert len(calls) == 1
    assert response["type"] == "villager_reply"
    assert "feels soft today" in response["text"]


async def test_fallback_provider_does_not_call_ollama() -> None:
    calls: list[str] = []

    def fake_ollama(url: str, payload: dict[str, Any], timeout_seconds: float) -> dict[str, Any]:
        calls.append(url)
        return {"message": {"role": "assistant", "content": "This should not be used."}}

    with TemporaryDirectory() as tmp_dir:
        with patched_provider_env(
            {
                "HOLLOW_LLM_PROVIDER": "fallback",
                "OLLAMA_BASE_URL": "http://ollama.test",
                "OLLAMA_MODEL": "cozy-test-model",
            }
        ):
            engine, memory_store = build_engine(Path(tmp_dir) / "forced_fallback.sqlite3", fake_ollama)
            try:
                response = await engine.handle_player_message(
                    player_id="heather",
                    villager_id="margot",
                    text="Hello Margot.",
                    context={"location": "town_square", "test": "forced_fallback"},
                )
            finally:
                memory_store.close()

    assert calls == []
    assert "feels soft today" in response["text"]


def main() -> None:
    asyncio.run(test_ollama_provider_uses_chat_payload())
    asyncio.run(test_ollama_provider_falls_back_on_invalid_response())
    asyncio.run(test_fallback_provider_does_not_call_ollama())
    print("PASS: Ollama provider selection, payload, and fallback behavior are valid.")


if __name__ == "__main__":
    main()
