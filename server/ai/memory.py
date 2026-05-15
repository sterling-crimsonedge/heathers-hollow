"""SQLite-backed persistent memory for villagers."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "heathers_hollow.sqlite3"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


@dataclass(frozen=True)
class MemoryRecord:
    id: int
    villager_id: str
    kind: str
    subject_id: str | None
    text: str
    salience: int
    emotion: str | None
    created_at: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class EventRecord:
    id: int
    kind: str
    summary: str
    actor_id: str | None
    target_id: str | None
    location: str | None
    created_at: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ConversationTurnRecord:
    id: int
    conversation_id: str
    villager_id: str
    player_id: str
    speaker: str
    text: str
    created_at: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class NotificationCursorRecord:
    client_id: str
    last_event_id: int
    updated_at: str


class MemoryStore:
    """Small SQLite repository for relationship and memory state."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        configured_path = db_path or os.getenv("HH_MEMORY_DB") or DEFAULT_DB_PATH
        self.db_path = Path(configured_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(self.db_path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self.initialize()

    def initialize(self) -> None:
        with self._lock, self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS villagers (
                    id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    config_path TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    villager_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    subject_id TEXT,
                    text TEXT NOT NULL,
                    salience INTEGER NOT NULL DEFAULT 50,
                    emotion TEXT,
                    created_at TEXT NOT NULL,
                    last_accessed_at TEXT,
                    access_count INTEGER NOT NULL DEFAULT 0,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE INDEX IF NOT EXISTS idx_memories_villager_created
                    ON memories(villager_id, created_at DESC);

                CREATE INDEX IF NOT EXISTS idx_memories_villager_subject_salience
                    ON memories(villager_id, subject_id, salience DESC);

                CREATE TABLE IF NOT EXISTS relationships (
                    villager_id TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    affection INTEGER NOT NULL DEFAULT 0,
                    trust INTEGER NOT NULL DEFAULT 0,
                    familiarity INTEGER NOT NULL DEFAULT 0,
                    tension INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY (villager_id, subject_id)
                );

                CREATE TABLE IF NOT EXISTS conversation_turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    villager_id TEXT NOT NULL,
                    player_id TEXT NOT NULL,
                    speaker TEXT NOT NULL,
                    text TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL,
                    actor_id TEXT,
                    target_id TEXT,
                    location TEXT,
                    summary TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE INDEX IF NOT EXISTS idx_events_kind_created
                    ON events(kind, created_at DESC);

                CREATE INDEX IF NOT EXISTS idx_events_actor_target_created
                    ON events(actor_id, target_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS notification_cursors (
                    client_id TEXT PRIMARY KEY,
                    last_event_id INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );
                """
            )

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def upsert_villager(self, villager_id: str, display_name: str, config_path: str) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO villagers (id, display_name, config_path, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    display_name = excluded.display_name,
                    config_path = excluded.config_path
                """,
                (villager_id, display_name, config_path, utc_now()),
            )

    def get_relationship(
        self,
        villager_id: str,
        subject_id: str,
        starting_values: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        with self._lock, self._connection:
            row = self._connection.execute(
                """
                SELECT villager_id, subject_id, affection, trust, familiarity, tension, updated_at, metadata_json
                FROM relationships
                WHERE villager_id = ? AND subject_id = ?
                """,
                (villager_id, subject_id),
            ).fetchone()

            if row is None:
                values = starting_values or {}
                now = utc_now()
                self._connection.execute(
                    """
                    INSERT INTO relationships
                        (villager_id, subject_id, affection, trust, familiarity, tension, updated_at, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        villager_id,
                        subject_id,
                        int(values.get("affection", 0)),
                        int(values.get("trust", 0)),
                        int(values.get("familiarity", 0)),
                        int(values.get("tension", 0)),
                        now,
                        "{}",
                    ),
                )
                row = self._connection.execute(
                    """
                    SELECT villager_id, subject_id, affection, trust, familiarity, tension, updated_at, metadata_json
                    FROM relationships
                    WHERE villager_id = ? AND subject_id = ?
                    """,
                    (villager_id, subject_id),
                ).fetchone()

            return self._relationship_from_row(row)

    def peek_relationship(self, villager_id: str, subject_id: str) -> dict[str, Any] | None:
        """Return a relationship row without creating one when it is missing."""
        with self._lock:
            row = self._connection.execute(
                """
                SELECT villager_id, subject_id, affection, trust, familiarity, tension, updated_at, metadata_json
                FROM relationships
                WHERE villager_id = ? AND subject_id = ?
                """,
                (villager_id, subject_id),
            ).fetchone()

        if row is None:
            return None
        return self._relationship_from_row(row)

    def query_relationships(
        self,
        *,
        villager_id: str | None = None,
        subject_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        conditions: list[str] = []
        params: list[Any] = []

        if villager_id:
            conditions.append("villager_id = ?")
            params.append(villager_id)
        if subject_id:
            conditions.append("subject_id = ?")
            params.append(subject_id)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(max(1, int(limit)))

        with self._lock:
            rows = self._connection.execute(
                f"""
                SELECT villager_id, subject_id, affection, trust, familiarity, tension, updated_at, metadata_json
                FROM relationships
                {where_clause}
                ORDER BY datetime(updated_at) DESC, villager_id ASC, subject_id ASC
                LIMIT ?
                """,
                params,
            ).fetchall()

        return [self._relationship_from_row(row) for row in rows]

    def update_relationship(
        self,
        villager_id: str,
        subject_id: str,
        *,
        affection_delta: int = 0,
        trust_delta: int = 0,
        familiarity_delta: int = 0,
        tension_delta: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        current = self.get_relationship(villager_id, subject_id)
        merged_metadata = dict(current.get("metadata", {}))
        if metadata:
            merged_metadata.update(metadata)

        updated = {
            "affection": clamp(int(current["affection"]) + affection_delta, -100, 100),
            "trust": clamp(int(current["trust"]) + trust_delta, 0, 100),
            "familiarity": clamp(int(current["familiarity"]) + familiarity_delta, 0, 100),
            "tension": clamp(int(current["tension"]) + tension_delta, 0, 100),
        }

        with self._lock, self._connection:
            self._connection.execute(
                """
                UPDATE relationships
                SET affection = ?, trust = ?, familiarity = ?, tension = ?, updated_at = ?, metadata_json = ?
                WHERE villager_id = ? AND subject_id = ?
                """,
                (
                    updated["affection"],
                    updated["trust"],
                    updated["familiarity"],
                    updated["tension"],
                    utc_now(),
                    json.dumps(merged_metadata, sort_keys=True),
                    villager_id,
                    subject_id,
                ),
            )

        return self.get_relationship(villager_id, subject_id)

    def add_memory(
        self,
        villager_id: str,
        *,
        kind: str,
        text: str,
        subject_id: str | None = None,
        salience: int = 50,
        emotion: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """
                INSERT INTO memories
                    (villager_id, kind, subject_id, text, salience, emotion, created_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    villager_id,
                    kind,
                    subject_id,
                    text,
                    clamp(salience, 0, 100),
                    emotion,
                    utc_now(),
                    json.dumps(metadata or {}, sort_keys=True),
                ),
            )
            return int(cursor.lastrowid)

    def add_conversation_turn(
        self,
        conversation_id: str,
        villager_id: str,
        player_id: str,
        *,
        speaker: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """
                INSERT INTO conversation_turns
                    (conversation_id, villager_id, player_id, speaker, text, created_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    villager_id,
                    player_id,
                    speaker,
                    text,
                    utc_now(),
                    json.dumps(metadata or {}, sort_keys=True),
                ),
            )
            return int(cursor.lastrowid)

    def get_conversation_turns(self, conversation_id: str) -> list[ConversationTurnRecord]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT *
                FROM conversation_turns
                WHERE conversation_id = ?
                ORDER BY id ASC
                """,
                (conversation_id,),
            ).fetchall()
        return [self._conversation_turn_from_row(row) for row in rows]

    def get_recent_memories(self, villager_id: str, limit: int = 6) -> list[MemoryRecord]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT *
                FROM memories
                WHERE villager_id = ?
                ORDER BY datetime(created_at) DESC, id DESC
                LIMIT ?
                """,
                (villager_id, limit),
            ).fetchall()
        return [self._memory_from_row(row) for row in rows]

    def get_memory(self, memory_id: int) -> MemoryRecord | None:
        """Return one memory without updating retrieval counters."""
        with self._lock:
            row = self._connection.execute(
                """
                SELECT *
                FROM memories
                WHERE id = ?
                """,
                (int(memory_id),),
            ).fetchone()

        if row is None:
            return None
        return self._memory_from_row(row)

    def query_memories(
        self,
        *,
        villager_id: str | None = None,
        subject_id: str | None = None,
        kind: str | None = None,
        limit: int = 10,
    ) -> list[MemoryRecord]:
        conditions: list[str] = []
        params: list[Any] = []

        if villager_id:
            conditions.append("villager_id = ?")
            params.append(villager_id)
        if subject_id:
            conditions.append("subject_id = ?")
            params.append(subject_id)
        if kind:
            conditions.append("kind = ?")
            params.append(kind)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(max(1, int(limit)))

        with self._lock:
            rows = self._connection.execute(
                f"""
                SELECT *
                FROM memories
                {where_clause}
                ORDER BY datetime(created_at) DESC, id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [self._memory_from_row(row) for row in rows]

    def get_salient_memories(self, villager_id: str, subject_id: str, limit: int = 5) -> list[MemoryRecord]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT *
                FROM memories
                WHERE villager_id = ? AND (subject_id = ? OR subject_id IS NULL)
                ORDER BY salience DESC, datetime(created_at) DESC, id DESC
                LIMIT ?
                """,
                (villager_id, subject_id, limit),
            ).fetchall()
        return [self._memory_from_row(row) for row in rows]

    def get_relevant_memories(self, villager_id: str, subject_id: str, limit: int = 8) -> list[MemoryRecord]:
        recent = self.get_recent_memories(villager_id, limit=limit)
        salient = self.get_salient_memories(villager_id, subject_id, limit=limit)
        merged: dict[int, MemoryRecord] = {memory.id: memory for memory in recent}
        for memory in salient:
            merged[memory.id] = memory

        selected = sorted(
            merged.values(),
            key=lambda memory: (memory.salience, memory.created_at),
            reverse=True,
        )[:limit]

        if selected:
            self.mark_accessed([memory.id for memory in selected])
        return selected

    def mark_accessed(self, memory_ids: list[int]) -> None:
        if not memory_ids:
            return
        placeholders = ",".join("?" for _ in memory_ids)
        with self._lock, self._connection:
            self._connection.execute(
                f"""
                UPDATE memories
                SET last_accessed_at = ?, access_count = access_count + 1
                WHERE id IN ({placeholders})
                """,
                [utc_now(), *memory_ids],
            )

    def add_event(
        self,
        *,
        kind: str,
        summary: str,
        actor_id: str | None = None,
        target_id: str | None = None,
        location: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """
                INSERT INTO events (kind, actor_id, target_id, location, summary, created_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    kind,
                    actor_id,
                    target_id,
                    location,
                    summary,
                    utc_now(),
                    json.dumps(metadata or {}, sort_keys=True),
                ),
            )
            return int(cursor.lastrowid)

    def get_recent_events(self, limit: int = 10) -> list[EventRecord]:
        return self.query_events(limit=limit)

    def get_event(self, event_id: int) -> EventRecord | None:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT *
                FROM events
                WHERE id = ?
                """,
                (int(event_id),),
            ).fetchone()
        if row is None:
            return None
        return self._event_from_row(row)

    def query_events(
        self,
        *,
        kind: str | None = None,
        actor_id: str | None = None,
        target_id: str | None = None,
        after_id: int | None = None,
        limit: int = 10,
        ascending: bool = False,
    ) -> list[EventRecord]:
        conditions: list[str] = []
        params: list[Any] = []

        if kind:
            conditions.append("kind = ?")
            params.append(kind)
        if actor_id:
            conditions.append("actor_id = ?")
            params.append(actor_id)
        if target_id:
            conditions.append("target_id = ?")
            params.append(target_id)
        if after_id is not None:
            conditions.append("id > ?")
            params.append(max(0, int(after_id)))

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(max(1, int(limit)))
        order_clause = "id ASC" if ascending else "datetime(created_at) DESC, id DESC"

        with self._lock:
            rows = self._connection.execute(
                f"""
                SELECT *
                FROM events
                {where_clause}
                ORDER BY {order_clause}
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [self._event_from_row(row) for row in rows]

    def count_events(
        self,
        *,
        kind: str | None = None,
        actor_id: str | None = None,
        target_id: str | None = None,
        after_id: int | None = None,
    ) -> int:
        conditions: list[str] = []
        params: list[Any] = []

        if kind:
            conditions.append("kind = ?")
            params.append(kind)
        if actor_id:
            conditions.append("actor_id = ?")
            params.append(actor_id)
        if target_id:
            conditions.append("target_id = ?")
            params.append(target_id)
        if after_id is not None:
            conditions.append("id > ?")
            params.append(max(0, int(after_id)))

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        with self._lock:
            row = self._connection.execute(
                f"""
                SELECT COUNT(*) AS event_count
                FROM events
                {where_clause}
                """,
                params,
            ).fetchone()
        return int(row["event_count"] if row is not None else 0)

    def get_notification_cursor(self, client_id: str) -> NotificationCursorRecord | None:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT client_id, last_event_id, updated_at
                FROM notification_cursors
                WHERE client_id = ?
                """,
                (client_id,),
            ).fetchone()
        if row is None:
            return None
        return self._notification_cursor_from_row(row)

    def set_notification_cursor(self, client_id: str, last_event_id: int) -> NotificationCursorRecord:
        safe_event_id = max(0, int(last_event_id))
        now = utc_now()

        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO notification_cursors (client_id, last_event_id, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(client_id) DO UPDATE SET
                    last_event_id = CASE
                        WHEN excluded.last_event_id > notification_cursors.last_event_id
                        THEN excluded.last_event_id
                        ELSE notification_cursors.last_event_id
                    END,
                    updated_at = excluded.updated_at
                """,
                (client_id, safe_event_id, now),
            )
            row = self._connection.execute(
                """
                SELECT client_id, last_event_id, updated_at
                FROM notification_cursors
                WHERE client_id = ?
                """,
                (client_id,),
            ).fetchone()

        if row is None:
            raise RuntimeError(f"Failed to persist notification cursor for {client_id!r}.")
        return self._notification_cursor_from_row(row)

    def _memory_from_row(self, row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(
            id=int(row["id"]),
            villager_id=str(row["villager_id"]),
            kind=str(row["kind"]),
            subject_id=row["subject_id"],
            text=str(row["text"]),
            salience=int(row["salience"]),
            emotion=row["emotion"],
            created_at=str(row["created_at"]),
            metadata=json.loads(row["metadata_json"] or "{}"),
        )

    def _relationship_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "villager_id": row["villager_id"],
            "subject_id": row["subject_id"],
            "affection": int(row["affection"]),
            "trust": int(row["trust"]),
            "familiarity": int(row["familiarity"]),
            "tension": int(row["tension"]),
            "updated_at": row["updated_at"],
            "metadata": json.loads(row["metadata_json"] or "{}"),
        }

    def _event_from_row(self, row: sqlite3.Row) -> EventRecord:
        return EventRecord(
            id=int(row["id"]),
            kind=str(row["kind"]),
            actor_id=row["actor_id"],
            target_id=row["target_id"],
            location=row["location"],
            summary=str(row["summary"]),
            created_at=str(row["created_at"]),
            metadata=json.loads(row["metadata_json"] or "{}"),
        )

    def _notification_cursor_from_row(self, row: sqlite3.Row) -> NotificationCursorRecord:
        return NotificationCursorRecord(
            client_id=str(row["client_id"]),
            last_event_id=max(0, int(row["last_event_id"])),
            updated_at=str(row["updated_at"]),
        )

    def _conversation_turn_from_row(self, row: sqlite3.Row) -> ConversationTurnRecord:
        return ConversationTurnRecord(
            id=int(row["id"]),
            conversation_id=str(row["conversation_id"]),
            villager_id=str(row["villager_id"]),
            player_id=str(row["player_id"]),
            speaker=str(row["speaker"]),
            text=str(row["text"]),
            created_at=str(row["created_at"]),
            metadata=json.loads(row["metadata_json"] or "{}"),
        )
