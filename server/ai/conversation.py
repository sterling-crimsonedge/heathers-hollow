"""Conversation engine.

Takes a player utterance + villager personality + relevant memories +
current world state, and produces a Claude-generated reply. Also writes
new memories back to the store.

TODO: build the prompt assembly pipeline. Use prompt caching for the
static personality block — that's the biggest token cost lever.
"""
