"""AMap real provider — implements POI, route, and weather via 高德地图 APIs."""

import logging
import httpx
from typing import Optional

from backend.providers.base import POIProvider, RouteProvider, WeatherProvider

logger = logging.getLogger(__name__)

AMAP_BASE = "https://restapi.amap.com/v3"
REQUEST_TIMEOUT = 10.0

# AMap POI type codes for relevant categories
RESTAURANT_TYPES = "050000|050100|050200|050300|060000|060100"
ACTIVITY_TYPES = "110000|110100|110200|140000|140200|140300|140400|080000|080100"


class AmapPOIProvider(POIProvider):
    """Real POI search via 高德地图 POI search API."""

    def __init__(self, api_key: str):
        self._api_key = api_key

    async def search_pois(
        self,
        keyword: str | None = None,
        city: str | None = None,
        location: str | None = None,
        radius_m: int = 5000,
        poi_type: str | None = None,
    ) -> list[dict]:
        params = {
            "key": self._api_key,
            "keywords": keyword or "",
            "city": city or "",
            "offset": 20,
            "extensions": "all",
        }
        if poi_type:
            params["types"] = poi_type
        if location:
            params["location"] = location
            params["radius"] = str(radius_m)

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                resp = await client.get(f"{AMAP_BASE}/place/text", params=params)
                resp.raise_for_status()
                data = resp.json()

            if data.get("status") != "1":
                logger.warning(f"AMap POI search failed: {data.get('info', 'unknown')}")
                return []

            pois = data.get("pois", [])
            return [self._normalize_poi(p) for p in pois]

        except Exception as e:
            logger.error(f"AMap POI search error: {e}")
            raise

    async def geocode(self, address: str, city: str | None = None) -> dict | None:
        params = {
            "key": self._api_key,
            "address": address,
        }
        if city:
            params["city"] = city

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                resp = await client.get(f"{AMAP_BASE}/geocode/geo", params=params)
                resp.raise_for_status()
                data = resp.json()

            if data.get("status") != "1" or data.get("count") == "0":
                return None

            geocode = data["geocodes"][0]
            location = geocode.get("location", "")
            lon, lat = (location.split(",") + ["", ""])[:2]
            return {
                "formatted_address": geocode.get("formatted_address", ""),
                "longitude": float(lon) if lon else None,
                "latitude": float(lat) if lat else None,
                "adcode": geocode.get("adcode", None),
            }

        except Exception as e:
            logger.error(f"AMap geocoding error: {e}")
            raise

    @staticmethod
    def _normalize_poi(poi: dict) -> dict:
        """Normalize an AMap POI into our standard format.

        Fields not provided by AMap are explicitly set to 'unknown'.
        """
        location = poi.get("location", "")
        lon, lat = (location.split(",") + ["", ""])[:2]

        return {
            "id": poi.get("id", ""),
            "name": poi.get("name", ""),
            "type": poi.get("type", ""),
            "address": poi.get("address", ""),
            "longitude": float(lon) if lon else None,
            "latitude": float(lat) if lat else None,
            "distance_m": int(poi.get("distance", 0)) if poi.get("distance") else None,
            "tel": poi.get("tel", None),
            # Fields AMap does NOT provide — explicitly set to "unknown"
            "rating": "unknown",
            "avg_price": "unknown",
            "open_time": "unknown",
            "close_time": "unknown",
            "indoor": "unknown",
            "suitable_scenes": "unknown",
            "tags": "unknown",
            "age_range": "unknown",
            "has_low_fat_meal": "unknown",
            "has_kids_meal": "unknown",
            "booking_supported": "unknown",
            "source": "amap",
            "raw": poi,
        }


class AmapRouteProvider(RouteProvider):
    """Real route planning via 高德地图 driving direction API."""

    def __init__(self, api_key: str):
        self._api_key = api_key

    async def plan_route(
        self,
        origin: str,
        destination: str,
        origin_coords: str | None = None,
        dest_coords: str | None = None,
        transport: str = "driving",
    ) -> dict:
        """Plan a route. origin/destination can be coordinates (lon,lat) or place names.

        Coordinates are preferred for accuracy.
        """
        params = {
            "key": self._api_key,
            "origin": origin_coords or origin,
            "destination": dest_coords or destination,
            "extensions": "all",
        }

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                resp = await client.get(f"{AMAP_BASE}/direction/driving", params=params)
                resp.raise_for_status()
                data = resp.json()

            if data.get("status") != "1":
                logger.warning(f"AMap route planning failed: {data.get('info', 'unknown')}")
                return {
                    "distance_m": None,
                    "duration_sec": None,
                    "traffic_status": "unknown",
                    "source": "amap",
                    "error": data.get("info", "unknown"),
                }

            route = data.get("route", {})
            paths = route.get("paths", [])
            if not paths:
                return {
                    "distance_m": None,
                    "duration_sec": None,
                    "traffic_status": "unknown",
                    "source": "amap",
                    "error": "no route found",
                }

            path = paths[0]
            return {
                "distance_m": int(path.get("distance", 0)),
                "duration_sec": int(path.get("duration", 0)),
                "traffic_status": "unknown",
                "source": "amap",
                "raw": path,
            }

        except Exception as e:
            logger.error(f"AMap route planning error: {e}")
            raise


class AmapWeatherProvider(WeatherProvider):
    """Real weather query via 高德地图 weather API."""

    def __init__(self, api_key: str):
        self._api_key = api_key

    async def get_weather(self, city: str, adcode: str | None = None) -> dict:
        """Get current weather for a city or adcode."""
        params = {
            "key": self._api_key,
            "city": adcode or city,
            "extensions": "all",
        }

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                resp = await client.get(f"{AMAP_BASE}/weather/weatherInfo", params=params)
                resp.raise_for_status()
                data = resp.json()

            if data.get("status") != "1":
                logger.warning(f"AMap weather query failed: {data.get('info', 'unknown')}")
                return {
                    "weather": "unknown",
                    "temperature": "unknown",
                    "wind": "unknown",
                    "humidity": "unknown",
                    "source": "amap",
                    "error": data.get("info", "unknown"),
                }

            forecasts = data.get("forecasts", [])
            if not forecasts:
                return {
                    "weather": "unknown",
                    "temperature": "unknown",
                    "source": "amap",
                }

            forecast = forecasts[0]
            casts = forecast.get("casts", [])
            today = casts[0] if casts else {}

            return {
                "city": forecast.get("city", city),
                "date": today.get("date", ""),
                "day_weather": today.get("dayweather", "unknown"),
                "night_weather": today.get("nightweather", "unknown"),
                "day_temp": today.get("daytemp", "unknown"),
                "night_temp": today.get("nighttemp", "unknown"),
                "day_wind": today.get("daywind", "unknown"),
                "night_wind": today.get("nightwind", "unknown"),
                "day_power": today.get("daypower", "unknown"),
                "source": "amap",
                "raw": forecast,
            }

        except Exception as e:
            logger.error(f"AMap weather query error: {e}")
            raise
