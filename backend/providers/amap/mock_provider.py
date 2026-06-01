"""Mock AMap providers — use old JSON data for test/development fallback."""

import logging
from backend.data_loader import get_pois, get_restaurants, get_travel_times
from backend.providers.base import POIProvider, RouteProvider, WeatherProvider

logger = logging.getLogger(__name__)


class MockPOIProvider(POIProvider):
    """Mock POI provider using old JSON data files."""

    async def search_pois(
        self,
        keyword: str | None = None,
        city: str | None = None,
        location: str | None = None,
        radius_m: int = 5000,
        poi_type: str | None = None,
    ) -> list[dict]:
        results = []
        for poi in get_pois():
            results.append({
                "id": poi.get("poi_id", ""),
                "name": poi.get("name", ""),
                "type": poi.get("type", "unknown"),
                "address": poi.get("district", ""),
                "longitude": None,
                "latitude": None,
                "distance_m": None,
                "tel": None,
                "rating": poi.get("rating", "unknown"),
                "avg_price": poi.get("avg_price", "unknown"),
                "open_time": poi.get("open_time", "unknown"),
                "close_time": poi.get("close_time", "unknown"),
                "indoor": poi.get("indoor", "unknown"),
                "suitable_scenes": poi.get("suitable_scenes", "unknown"),
                "tags": poi.get("tags", "unknown"),
                "age_range": poi.get("age_range", "unknown"),
                "has_low_fat_meal": poi.get("has_low_fat_meal", "unknown"),
                "has_kids_meal": poi.get("has_kids_meal", "unknown"),
                "booking_supported": "unknown",
                "source": "mock_json",
            })
        return results

    async def geocode(self, address: str, city: str | None = None) -> dict | None:
        return {
            "formatted_address": address,
            "longitude": None,
            "latitude": None,
            "adcode": None,
        }


class MockRouteProvider(RouteProvider):
    """Mock route provider using old travel_times.json."""

    async def plan_route(
        self,
        origin: str,
        destination: str,
        origin_coords: str | None = None,
        dest_coords: str | None = None,
        transport: str = "driving",
    ) -> dict:
        for t in get_travel_times():
            if t["from"] == origin and t["to"] == destination:
                dist_km = t.get("distance_km", 5)
                return {
                    "distance_m": int(dist_km * 1000),
                    "duration_sec": t.get("taxi_time_min", 20) * 60,
                    "traffic_status": t.get("traffic_level", "unknown"),
                    "source": "mock_json",
                }

        # Fallback
        return {
            "distance_m": 5000,
            "duration_sec": 1200,  # 20 min
            "traffic_status": "unknown",
            "source": "mock_fallback",
        }


class MockWeatherProvider(WeatherProvider):
    """Mock weather provider — always returns fixed data."""

    async def get_weather(self, city: str, adcode: str | None = None) -> dict:
        return {
            "city": city,
            "date": "",
            "day_weather": "sunny",
            "night_weather": "clear",
            "day_temp": "unknown",
            "night_temp": "unknown",
            "day_wind": "unknown",
            "night_wind": "unknown",
            "day_power": "unknown",
            "source": "mock",
        }
