"""Mock AMap providers — use JSON data for test/development fallback."""

import logging
from backend.data_loader import get_pois, get_restaurants, get_travel_times
from backend.providers.base import POIProvider, RouteProvider, WeatherProvider

logger = logging.getLogger(__name__)

# City center coordinates for geocode fallback (matching location_resolver)
_CITY_CENTERS = {
    "上海": (121.4737, 31.2304), "北京": (116.4074, 39.9042),
    "广州": (113.2644, 23.1291), "深圳": (114.0579, 22.5431),
    "杭州": (120.1551, 30.2741), "成都": (104.0668, 30.5728),
    "南京": (118.7969, 32.0603), "武汉": (114.3055, 30.5928),
    "西安": (108.9398, 34.3416), "重庆": (106.9123, 29.4316),
    "湖州": (120.0868, 30.8943), "沧州": (116.8388, 38.3044),
    "泌阳": (113.3271, 32.7245), "安吉": (119.6803, 30.6386),
    "天津": (117.3616, 39.3434), "苏州": (120.5853, 31.2990),
    "长沙": (112.9388, 28.2282), "郑州": (113.6253, 34.7466),
    "济南": (117.1201, 36.6512), "青岛": (120.3826, 36.0671),
    "大连": (121.6147, 38.9140), "厦门": (118.0894, 24.4798),
    "福州": (119.2965, 26.0745), "合肥": (117.2272, 31.8206),
    "昆明": (102.7183, 25.0389), "贵阳": (106.6302, 26.6470),
    "南宁": (108.3665, 22.8170), "海口": (110.1999, 20.0440),
    "沈阳": (123.4315, 41.8057), "石家庄": (114.5149, 38.0428),
    "太原": (112.5489, 37.8706), "兰州": (103.8343, 36.0611),
    "南昌": (115.8582, 28.6820), "温州": (120.6994, 27.9939),
    "宁波": (121.5440, 29.8683), "无锡": (120.3124, 31.4912),
    "佛山": (113.1214, 23.0218), "东莞": (113.7518, 23.0205),
    "珠海": (113.5767, 22.2707),
}


class MockPOIProvider(POIProvider):
    """Mock POI provider using JSON data files with real coordinates."""

    async def search_pois(
        self,
        keyword: str | None = None,
        city: str | None = None,
        location: str | None = None,
        radius_m: int = 5000,
        poi_type: str | None = None,
    ) -> list[dict]:
        # Use restaurant data when searching for restaurant types
        is_restaurant_search = poi_type and "050" in str(poi_type)
        source_data = get_restaurants() if is_restaurant_search else get_pois()

        # If city is specified and not Shanghai, return empty — the data/*.json
        # files only contain Shanghai mock data. The orchestrator's mock_poi_fallback
        # will provide city-specific candidates without misleading intermediate results.
        if city:
            city_clean = city.rstrip("市")
            if city_clean not in ("上海", ""):
                return []

        results = []
        for item in source_data:
            # Use "lat"/"lng" from pois.json, or compute fallback from city
            lat = item.get("lat")
            lng = item.get("lng")
            if lat is None or lng is None:
                coords = _CITY_CENTERS.get(city.rstrip("市") if city else "", (None, None))
                lng, lat = coords if coords[0] is not None else (None, None)

            results.append({
                "id": item.get("poi_id") or item.get("restaurant_id", ""),
                "name": item.get("name", ""),
                "type": item.get("type", "unknown"),
                "address": item.get("district") or item.get("address", ""),
                "longitude": lng,
                "latitude": lat,
                "distance_m": item.get("distance_m"),
                "tel": None,
                "rating": item.get("rating", "unknown"),
                "avg_price": item.get("avg_price") or item.get("price", "unknown"),
                "open_time": item.get("open_time", "unknown"),
                "close_time": item.get("close_time", "unknown"),
                "indoor": item.get("indoor", "unknown"),
                "suitable_scenes": item.get("suitable_scenes", "unknown"),
                "tags": item.get("tags", "unknown"),
                "age_range": item.get("age_range", "unknown"),
                "has_low_fat_meal": item.get("has_low_fat_meal", "unknown"),
                "has_kids_meal": item.get("has_kids_meal", "unknown"),
                "booking_supported": "unknown",
                "source": "mock_json",
            })
        return results

    async def geocode(self, address: str, city: str | None = None) -> dict | None:
        # Try to find coordinates for the address from city centers
        search = address.rstrip("市区县镇乡")
        for name, (lng, lat) in _CITY_CENTERS.items():
            if name in search or search in name:
                return {
                    "formatted_address": address,
                    "longitude": lng,
                    "latitude": lat,
                    "adcode": None,
                }
        # Fallback: return coordinates for the first matching city
        if city:
            city_clean = city.rstrip("市")
            coords = _CITY_CENTERS.get(city_clean)
            if coords:
                return {
                    "formatted_address": address,
                    "longitude": coords[0],
                    "latitude": coords[1],
                    "adcode": None,
                }
        return {
            "formatted_address": address,
            "longitude": None,
            "latitude": None,
            "adcode": None,
        }


class MockRouteProvider(RouteProvider):
    """Mock route provider using travel_times.json with haversine fallback."""

    async def plan_route(
        self,
        origin: str,
        destination: str,
        origin_coords: str | None = None,
        dest_coords: str | None = None,
        transport: str = "driving",
    ) -> dict:
        # Try travel_times.json first
        for t in get_travel_times():
            if t["from"] == origin and t["to"] == destination:
                dist_km = t.get("distance_km", 5)
                return {
                    "distance_m": int(dist_km * 1000),
                    "duration_sec": t.get("taxi_time_min", 20) * 60,
                    "traffic_status": t.get("traffic_level", "unknown"),
                    "source": "mock_json",
                }

        # Compute haversine distance from coordinates if available
        if origin_coords and dest_coords:
            try:
                olng, olat = map(float, origin_coords.split(","))
                dlng, dlat = map(float, dest_coords.split(","))
                import math
                R = 6371000
                dlat_r = math.radians(dlat - olat)
                dlng_r = math.radians(dlng - olng)
                a = (math.sin(dlat_r / 2) ** 2 +
                     math.cos(math.radians(olat)) * math.cos(math.radians(dlat)) *
                     math.sin(dlng_r / 2) ** 2)
                dist_m = R * 2 * math.asin(math.sqrt(a))
                duration_sec = max(300, int(dist_m / 10))  # ~10 m/s average
                return {
                    "distance_m": int(dist_m),
                    "duration_sec": duration_sec,
                    "traffic_status": "unknown",
                    "source": "mock_haversine",
                }
            except (ValueError, TypeError):
                pass

        return {
            "distance_m": 5000,
            "duration_sec": 1200,
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
