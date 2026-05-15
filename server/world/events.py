"""Event system.

A unified stream of "things that happened" — player gave Margot a pumpkin,
it started raining, the shop opened. Villagers subscribe to events
relevant to them and may form memories from them.

TODO: pick a transport (in-process pub/sub for now; consider a queue if
the mobile app needs to consume the same stream later).
"""
