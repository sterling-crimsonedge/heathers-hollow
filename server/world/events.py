"""Event bus — a unified stream of "things that happened" in the world.

In-process asyncio pub/sub. The conversation engine, mobile push system,
and any future consumers (analytics, persistence side-effects) subscribe.

Events are small dicts: {"type": str, ...payload}. Keep them serializable so
the mobile app can consume the same stream over a queue someday.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


EventHandler = Callable[[dict], Awaitable[None]]


@dataclass
class EventBus:
    """Simple async pub/sub. Each handler runs concurrently — no blocking."""

    _handlers: dict[str, list[EventHandler]] = field(default_factory=lambda: defaultdict(list))
    _wildcard: list[EventHandler] = field(default_factory=list)
    _history: list[dict] = field(default_factory=list)
    _history_max: int = 200

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    def subscribe_all(self, handler: EventHandler) -> None:
        self._wildcard.append(handler)

    async def emit(self, event_type: str, **payload: Any) -> None:
        event = {"type": event_type, **payload}
        self._history.append(event)
        if len(self._history) > self._history_max:
            self._history = self._history[-self._history_max:]

        handlers = self._handlers.get(event_type, []) + self._wildcard
        if not handlers:
            return
        await asyncio.gather(
            *(self._safe_call(h, event) for h in handlers),
            return_exceptions=True,
        )

    async def _safe_call(self, handler: EventHandler, event: dict) -> None:
        try:
            await handler(event)
        except Exception as exc:  # handlers must not crash the bus
            print(f"[event-bus] handler {handler!r} crashed on {event['type']}: {exc}")

    def recent(self, limit: int = 20) -> list[dict]:
        return self._history[-limit:]


# Module-level default bus. Tests can build their own.
default_bus = EventBus()


# --- well-known event types ---------------------------------------------------

EVT_PLAYER_ENTERED      = "player.entered_village"
EVT_PLAYER_APPROACHED   = "player.approached"      # {villager_id}
EVT_PLAYER_GAVE_GIFT    = "player.gave_gift"       # {villager_id, item}
EVT_PLAYER_SET_NAME     = "player.set_name"        # {name}

EVT_VILLAGER_MOOD       = "villager.mood_changed"  # {villager_id, old, new}
EVT_VILLAGER_SPOKE      = "villager.spoke"         # {villager_id, content}

EVT_WORLD_TIME          = "world.time_advanced"    # {time_of_day, hours}
EVT_WORLD_WEATHER       = "world.weather_changed"  # {weather}
