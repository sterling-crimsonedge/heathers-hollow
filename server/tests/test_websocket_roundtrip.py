"""Live WebSocket smoke test for the Heather's Hollow AI server.

Run against an already-running server:

    python -m server.tests.test_websocket_roundtrip

Or start an isolated temporary server automatically:

    python -m server.tests.test_websocket_roundtrip --start-server

The `--start-server` path uses a temporary SQLite database and removes
`ANTHROPIC_API_KEY` from the subprocess environment so fallback mode stays
deterministic. It verifies the actual `/ws` WebSocket route, not just the
conversation engine in process.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

import websockets


DEFAULT_URL = "ws://127.0.0.1:8765/ws"


async def run_roundtrip(url: str) -> tuple[bool, str]:
    fact_text = "Margot, please remember that my favorite color is moonlit lavender."

    first_reply = await send_player_message(url, fact_text)
    second_reply = await send_player_message(url, "Do you remember what my favorite color is?")
    fact_remembered = "moonlit" in second_reply.lower() or "lavender" in second_reply.lower()
    gift_reply = await send_gift(url)
    gift_memory_reply = await send_player_message(url, "Do you remember the flower I gave you?")
    gift_remembered = "dusty" in gift_memory_reply.lower() or "rose" in gift_memory_reply.lower()

    transcript = "\n".join(
        [
            f"First reply: {first_reply}",
            f"Second reply: {second_reply}",
            f"Gift reply: {gift_reply}",
            f"Gift memory reply: {gift_memory_reply}",
        ]
    )
    return fact_remembered and gift_remembered, transcript


async def send_player_message(url: str, text: str) -> str:
    async with websockets.connect(url, open_timeout=5) as websocket:
        greeting = json.loads(await websocket.recv())
        if greeting.get("type") != "server_status":
            raise RuntimeError(f"Expected server_status greeting, received: {greeting}")

        await websocket.send(
            json.dumps(
                {
                    "type": "player_message",
                    "player_id": "heather",
                    "villager_id": "margot",
                    "text": text,
                    "context": {
                        "location": "town_square",
                        "test": "websocket_roundtrip",
                    },
                }
            )
        )

        response: dict[str, Any] = json.loads(await websocket.recv())
        if response.get("type") != "villager_reply":
            raise RuntimeError(f"Expected villager_reply, received: {response}")
        return str(response.get("text", ""))


async def send_gift(url: str) -> str:
    async with websockets.connect(url, open_timeout=5) as websocket:
        greeting = json.loads(await websocket.recv())
        if greeting.get("type") != "server_status":
            raise RuntimeError(f"Expected server_status greeting, received: {greeting}")

        await websocket.send(
            json.dumps(
                {
                    "type": "gift_item",
                    "player_id": "heather",
                    "villager_id": "margot",
                    "item": {
                        "item_id": "dusty_rose",
                        "display_name": "Stale Rose Name",
                        "category": "waste",
                        "tags": ["waste"],
                        "secret": "not public",
                    },
                    "context": {
                        "location": "town_square",
                        "test": "websocket_gift_roundtrip",
                    },
                }
            )
        )

        response: dict[str, Any] = json.loads(await websocket.recv())
        if response.get("type") != "villager_reply":
            raise RuntimeError(f"Expected villager_reply, received: {response}")
        return str(response.get("text", ""))


def wait_for_health(url: str, timeout_seconds: float = 10.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=1.0) as response:
                if response.status == 200:
                    return
        except URLError:
            time.sleep(0.2)
    raise RuntimeError(f"Server did not become healthy at {url}")


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def run_with_temp_server() -> tuple[bool, str]:
    port = find_free_port()
    url = f"ws://127.0.0.1:{port}/ws"
    health_url = f"http://127.0.0.1:{port}/health"

    with TemporaryDirectory() as tmp_dir:
        env = os.environ.copy()
        env["HH_MEMORY_DB"] = str(Path(tmp_dir) / "websocket_roundtrip.sqlite3")
        env.pop("ANTHROPIC_API_KEY", None)
        env["HOLLOW_LLM_PROVIDER"] = "fallback"

        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "server.api.server:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--log-level",
                "warning",
            ],
            cwd=Path(__file__).resolve().parents[2],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            wait_for_health(health_url)
            return asyncio.run(run_roundtrip(url))
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify live WebSocket conversation and gift memory.")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"WebSocket URL to test. Default: {DEFAULT_URL}")
    parser.add_argument(
        "--start-server",
        action="store_true",
        help="Start an isolated uvicorn server on a temporary port before testing.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.start_server:
        remembered, transcript = run_with_temp_server()
    else:
        remembered, transcript = asyncio.run(run_roundtrip(args.url))

    print(transcript)
    if remembered:
        print("PASS: Margot remembered conversation and gift facts across WebSocket sessions.")
        return
    raise SystemExit("FAIL: Margot did not remember conversation and gift facts across WebSocket sessions.")


if __name__ == "__main__":
    main()
