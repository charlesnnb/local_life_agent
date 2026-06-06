"""Mock weather lookup."""

from src.config.settings import load_json
from src.schemas.models import ResolvedLocation


def get_weather(location: ResolvedLocation) -> dict:
    """Return city-specific mock weather, falling back to the default record."""
    records = load_json("weather.json").get("weather", [])
    for record in records:
        if record.get("city") == location.city:
            return dict(record)
    return dict(records[0]) if records else {
        "city": location.city,
        "condition": "晴",
        "temperature_c": 25,
        "outdoor_friendly": True,
        "source": "mock",
    }
