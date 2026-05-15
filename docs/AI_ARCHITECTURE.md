# AI Architecture — Heather's Hollow

> **Status:** TODO — placeholder. Fill in as the system takes shape.

## Goal

Villagers that feel like *people* — they remember, they grow, they surprise. Not chatbots wearing animal costumes.

## Components to design

### Personality
- Static traits (the seed of who they are)
- Dynamic traits (what changes through play)
- Voice / speech patterns
- Relationships with other villagers

### Memory
- Short-term: current conversation context
- Long-term: persistent facts, episodes, opinions about the player
- Forgetting / summarization strategy (we can't keep everything verbatim forever)
- Shared world memory vs. per-villager memory

### Conversation engine
- Prompt structure for Claude
- Injecting relevant memories without blowing context
- Tone and length controls
- How villagers reference each other and recent events

### Evolution
- When and how personality drifts
- Trigger events for growth (gifts, milestones, time)
- Stability vs. surprise — they should feel *consistent*, not random

## Open questions

- What's the unit of memory? (utterance, episode, fact?)
- How do we keep token costs sane at scale?
- How do villagers "see" the world — do they have spatial awareness, or just a feed of events?
- Caching strategy for personality prompts (prompt caching is likely critical here)
