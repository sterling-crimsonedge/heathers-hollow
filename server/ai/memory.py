"""Persistent memory store for villagers.

SQLite, single file. Schema follows docs/AI_ARCHITECTURE.md.

Each villager owns a stream of memories. Conversations are logged turn by turn.
At end of conversation, a summary + extracted long-term memories are written
back so they show up in future prompts.

Retrieval for prompt assembly uses a cheap scoring function: salience +
recency decay + keyword overlap with the recent conversation + a small boost
if the memory mentions the player. No embeddings yet — see open questions in
docs/AI_ARCHITECTURE.md.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional


# --- schema -------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    villager_id       TEXT NOT NULL,
    kind              TEXT NOT NULL,
    content           TEXT NOT NULL,
    participants      TEXT,
    salience          REAL NOT NULL DEFAULT 0.5,
    emotional_valence REAL DEFAULT 0.0,
    created_at        TEXT NOT NULL,
    last_recalled     TEXT,
    recall_count      INTEGER DEFAULT 0,
    tags              TEXT
);
CREATE INDEX IF NOT EXISTS idx_memories_villager ON memories(villager_id);
CREATE INDEX IF NOT EXISTS idx_memories_kind ON memories(villager_id, kind);

CREATE TABLE IF NOT EXISTS relationships (
    villager_id  TEXT NOT NULL,
    target_id    TEXT NOT NULL,
    affection    INTEGER NOT NULL DEFAULT 0,
    trust        INTEGER NOT NULL DEFAULT 0,
    familiarity  INTEGER NOT NULL DEFAULT 0,
    mood         TEXT,
    updated_at   TEXT NOT NULL,
    PRIMARY KEY (villager_id, target_id)
);

CREATE TABLE IF NOT EXISTS conversations (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    villager_id  TEXT NOT NULL,
    player_id    TEXT NOT NULL,
    started_at   TEXT NOT NULL,
    ended_at     TEXT,
    summary      TEXT
);
CREATE INDEX IF NOT EXISTS idx_conv_villager ON conversations(villager_id);

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);

CREATE TABLE IF NOT EXISTS gifts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    villager_id   TEXT NOT NULL,
    player_id     TEXT NOT NULL,
    item          TEXT NOT NULL,
    reaction      TEXT,
    given_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_gifts_villager ON gifts(villager_id);

CREATE TABLE IF NOT EXISTS player_profile (
    player_id    TEXT PRIMARY KEY,
    display_name TEXT,
    notes        TEXT,
    updated_at   TEXT NOT NULL
);
"""


# --- dataclasses --------------------------------------------------------------

@dataclass
class Memory:
    id: int
    villager_id: str
    kind: str
    content: str
    participants: list[str]
    salience: float
    emotional_valence: float
    created_at: str
    last_recalled: Optional[str]
    recall_count: int
    tags: list[str]


@dataclass
class Relationship:
    villager_id: str
    target_id: str
    affection: int      # -100..100
    trust: int          # 0..100
    familiarity: int    # 0..100
    mood: Optional[str]
    updated_at: str


# --- store --------------------------------------------------------------------

class MemoryStore:
    """SQLite-backed memory and relationship store.

    Thread-unsafe in the sense that you should give each consumer its own
    instance, but SQLite itself handles concurrent access fine for our scale.
    """

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # --- memories -----------------------------------------------------------

    def add_memory(
        self,
        villager_id: str,
        kind: str,
        content: str,
        *,
        participants: Optional[list[str]] = None,
        salience: float = 0.5,
        emotional_valence: float = 0.0,
        tags: Optional[list[str]] = None,
    ) -> int:
        now = _utcnow_iso()
        with self._conn() as c:
            cur = c.execute(
                """INSERT INTO memories
                   (villager_id, kind, content, participants, salience,
                    emotional_valence, created_at, tags)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    villager_id,
                    kind,
                    content,
                    json.dumps(participants or []),
                    salience,
                    emotional_valence,
                    now,
                    json.dumps(tags or []),
                ),
            )
            return cur.lastrowid

    def recall(
        self,
        villager_id: str,
        *,
        query: str = "",
        mentions_player: bool = True,
        limit: int = 10,
    ) -> list[Memory]:
        """Retrieve the top-N most relevant memories for this villager.

        Scoring is cheap and deterministic:
            score = salience
                  + 0.4 * recency_factor (exp decay, half-life ~30 days)
                  + 0.3 * keyword_overlap_with_query
                  + 0.2 * (1 if player in participants else 0)
        """
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM memories WHERE villager_id = ?",
                (villager_id,),
            ).fetchall()

        if not rows:
            return []

        q_tokens = _tokenize(query)
        now = time.time()
        scored: list[tuple[float, sqlite3.Row]] = []
        for row in rows:
            created_ts = _parse_iso(row["created_at"])
            age_days = max(0.0, (now - created_ts) / 86400.0)
            recency = math.exp(-age_days / 30.0)

            m_tokens = _tokenize(row["content"])
            overlap = (
                len(q_tokens & m_tokens) / max(1, len(q_tokens))
                if q_tokens
                else 0.0
            )

            participants = json.loads(row["participants"] or "[]")
            player_boost = 1.0 if mentions_player and "player" in participants else 0.0

            score = (
                float(row["salience"])
                + 0.4 * recency
                + 0.3 * overlap
                + 0.2 * player_boost
            )
            scored.append((score, row))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        top = scored[:limit]

        # bump recall stats
        ids = [row["id"] for _, row in top]
        if ids:
            now_iso = _utcnow_iso()
            with self._conn() as c:
                c.executemany(
                    "UPDATE memories SET last_recalled = ?, recall_count = recall_count + 1 WHERE id = ?",
                    [(now_iso, mid) for mid in ids],
                )

        return [_row_to_memory(row) for _, row in top]

    # --- relationships ------------------------------------------------------

    def get_relationship(self, villager_id: str, target_id: str) -> Relationship:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM relationships WHERE villager_id = ? AND target_id = ?",
                (villager_id, target_id),
            ).fetchone()
        if row is None:
            return Relationship(
                villager_id=villager_id,
                target_id=target_id,
                affection=0,
                trust=0,
                familiarity=0,
                mood=None,
                updated_at=_utcnow_iso(),
            )
        return Relationship(
            villager_id=row["villager_id"],
            target_id=row["target_id"],
            affection=row["affection"],
            trust=row["trust"],
            familiarity=row["familiarity"],
            mood=row["mood"],
            updated_at=row["updated_at"],
        )

    def update_relationship(
        self,
        villager_id: str,
        target_id: str,
        *,
        affection_delta: int = 0,
        trust_delta: int = 0,
        familiarity_delta: int = 0,
        mood: Optional[str] = None,
    ) -> Relationship:
        current = self.get_relationship(villager_id, target_id)
        new_affection = _clamp(current.affection + affection_delta, -100, 100)
        new_trust = _clamp(current.trust + trust_delta, 0, 100)
        new_familiarity = _clamp(current.familiarity + familiarity_delta, 0, 100)
        new_mood = mood if mood is not None else current.mood
        now = _utcnow_iso()
        with self._conn() as c:
            c.execute(
                """INSERT INTO relationships
                   (villager_id, target_id, affection, trust, familiarity, mood, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(villager_id, target_id) DO UPDATE SET
                       affection = excluded.affection,
                       trust = excluded.trust,
                       familiarity = excluded.familiarity,
                       mood = excluded.mood,
                       updated_at = excluded.updated_at""",
                (villager_id, target_id, new_affection, new_trust, new_familiarity, new_mood, now),
            )
        return Relationship(
            villager_id=villager_id,
            target_id=target_id,
            affection=new_affection,
            trust=new_trust,
            familiarity=new_familiarity,
            mood=new_mood,
            updated_at=now,
        )

    # --- conversations ------------------------------------------------------

    def start_conversation(self, villager_id: str, player_id: str) -> int:
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO conversations (villager_id, player_id, started_at) VALUES (?, ?, ?)",
                (villager_id, player_id, _utcnow_iso()),
            )
            return cur.lastrowid

    def end_conversation(self, conversation_id: int, summary: Optional[str] = None) -> None:
        with self._conn() as c:
            c.execute(
                "UPDATE conversations SET ended_at = ?, summary = ? WHERE id = ?",
                (_utcnow_iso(), summary, conversation_id),
            )

    def add_message(self, conversation_id: int, role: str, content: str) -> int:
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (conversation_id, role, content, _utcnow_iso()),
            )
            return cur.lastrowid

    def get_messages(self, conversation_id: int) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT role, content, created_at FROM messages WHERE conversation_id = ? ORDER BY id",
                (conversation_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def recent_conversation_summaries(
        self, villager_id: str, *, player_id: str = "player", limit: int = 3
    ) -> list[str]:
        with self._conn() as c:
            rows = c.execute(
                """SELECT summary FROM conversations
                   WHERE villager_id = ? AND player_id = ? AND summary IS NOT NULL
                   ORDER BY id DESC LIMIT ?""",
                (villager_id, player_id, limit),
            ).fetchall()
        return [r["summary"] for r in rows]

    # --- gifts --------------------------------------------------------------

    def log_gift(
        self,
        villager_id: str,
        player_id: str,
        item: str,
        reaction: Optional[str] = None,
    ) -> int:
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO gifts (villager_id, player_id, item, reaction, given_at) VALUES (?, ?, ?, ?, ?)",
                (villager_id, player_id, item, reaction, _utcnow_iso()),
            )
            return cur.lastrowid

    def gift_history(self, villager_id: str, player_id: str = "player") -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT item, reaction, given_at FROM gifts WHERE villager_id = ? AND player_id = ? ORDER BY id DESC",
                (villager_id, player_id),
            ).fetchall()
        return [dict(r) for r in rows]

    # --- player -------------------------------------------------------------

    def get_player_name(self, player_id: str = "player") -> Optional[str]:
        with self._conn() as c:
            row = c.execute(
                "SELECT display_name FROM player_profile WHERE player_id = ?",
                (player_id,),
            ).fetchone()
        return row["display_name"] if row else None

    def set_player_name(self, display_name: str, player_id: str = "player") -> None:
        now = _utcnow_iso()
        with self._conn() as c:
            c.execute(
                """INSERT INTO player_profile (player_id, display_name, updated_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(player_id) DO UPDATE SET
                       display_name = excluded.display_name,
                       updated_at = excluded.updated_at""",
                (player_id, display_name, now),
            )


# --- helpers ------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-zA-Z']+")
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "in", "on", "at", "to", "of",
    "for", "with", "is", "are", "was", "were", "be", "been", "being", "i",
    "you", "he", "she", "it", "we", "they", "my", "your", "his", "her", "its",
    "our", "their", "this", "that", "these", "those", "do", "does", "did",
    "have", "has", "had", "will", "would", "can", "could", "should", "just",
    "so", "not", "no", "yes", "as", "from",
}


def _tokenize(text: str) -> set[str]:
    return {w.lower() for w in _TOKEN_RE.findall(text or "") if w.lower() not in _STOPWORDS and len(w) > 2}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(s: str) -> float:
    return datetime.fromisoformat(s).timestamp()


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def _row_to_memory(row: sqlite3.Row) -> Memory:
    return Memory(
        id=row["id"],
        villager_id=row["villager_id"],
        kind=row["kind"],
        content=row["content"],
        participants=json.loads(row["participants"] or "[]"),
        salience=float(row["salience"]),
        emotional_valence=float(row["emotional_valence"] or 0.0),
        created_at=row["created_at"],
        last_recalled=row["last_recalled"],
        recall_count=int(row["recall_count"] or 0),
        tags=json.loads(row["tags"] or "[]"),
    )
