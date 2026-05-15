"""Persistent memory system for villagers.

Each villager remembers what the player said, what they gave them, who else
was around, and how they felt about it. Memories persist across sessions
and influence future conversations.

TODO: pick a storage layer (SQLite to start?), define memory schema,
design the retrieval-into-prompt strategy.
"""
