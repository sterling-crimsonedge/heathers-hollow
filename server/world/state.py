"""World state — authoritative time, weather, and ambient context.

Lives on the server so the future mobile companion app can read the same
state the game client sees. Villagers consult this when deciding what to
talk about ("nice morning, isn't it?").

TODO: define the schema. Time-of-day, day-of-year, weather, season.
"""
