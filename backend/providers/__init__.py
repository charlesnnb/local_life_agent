"""Provider abstraction layer for the Local Life Planning Agent.

All external data sources (LLM, POI, route, weather, booking) are accessed
through provider interfaces, allowing real/mock/fallback modes.
"""