"""API server — bridges the Godot client (and future mobile app) to the
AI and world systems.

Plan: WebSocket for real-time conversation streaming + a small REST surface
for state queries.

TODO: pick framework (FastAPI is the likely default — good WS support,
async-native, fast to scaffold).
"""
