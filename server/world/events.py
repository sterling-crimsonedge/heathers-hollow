"""Village event stream for remembered world activity."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class VillageEvent:
    kind: str
    summary: str
    actor_id: str | None = None
    target_id: str | None = None
    location: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class EventLog:
    """In-memory event bus for prototype systems."""

    def __init__(self) -> None:
        self._events: list[VillageEvent] = []

    def publish(self, event: VillageEvent) -> VillageEvent:
        self._events.append(event)
        return event

    def recent(self, limit: int = 10) -> list[VillageEvent]:
        return self._events[-limit:]
