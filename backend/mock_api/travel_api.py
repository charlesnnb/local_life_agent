"""Mock Travel API — estimate travel times between locations."""

from backend.data_loader import get_travel_times
import math


def estimate_travel_time(
    from_id: str,
    to_id: str,
    transport: str = "taxi",
    departure_time: str | None = None,
) -> dict:
    """Estimate travel time between two location IDs."""
    # Look up exact match
    for t in get_travel_times():
        if t["from"] == from_id and t["to"] == to_id:
            return _build_result(t, transport)

    # Try reverse
    for t in get_travel_times():
        if t["from"] == to_id and t["to"] == from_id:
            return _build_result(t, transport)

    # Fallback: rough estimate based on distance
    for t in get_travel_times():
        if t["from"] == from_id:
            # Use similar distance as proxy
            return _build_result(t, transport)

    return {
        "distance_km": 5.0,
        "duration_min": 20,
        "traffic_level": "medium",
        "estimated": True,
    }


def _build_result(travel_entry: dict, transport: str) -> dict:
    duration_key = {
        "taxi": "taxi_time_min",
        "walk": "walk_time_min",
        "subway": "subway_time_min",
    }.get(transport, "taxi_time_min")

    return {
        "distance_km": travel_entry.get("distance_km", 0),
        "duration_min": travel_entry.get(duration_key, 20),
        "traffic_level": travel_entry.get("traffic_level", "medium"),
        "estimated": False,
    }
