"""Restaurant search using AMap identity plus mock commerce enrichment."""

from src.config.settings import current_demo_scenario, load_json
from src.providers.amap_provider import AmapProvider
from src.providers.local_commerce_provider import enrich_restaurant
from src.schemas.models import ResolvedLocation, UserIntent


def search_restaurants(
    intent: UserIntent,
    location: ResolvedLocation,
    queries: list[str] | None = None,
    amap_provider: AmapProvider | None = None,
) -> list[dict]:
    """Return real AMap restaurants or local mock records on any failure."""
    if amap_provider and amap_provider.is_available:
        real_candidates = _search_amap(
            intent,
            location,
            queries or intent.diet_preferences or ["附近餐厅"],
            amap_provider,
        )
        if real_candidates:
            return real_candidates
    return _search_mock(intent, location, queries)


def _search_amap(
    intent: UserIntent,
    location: ResolvedLocation,
    queries: list[str],
    provider: AmapProvider,
) -> list[dict]:
    candidates: list[dict] = []
    seen: set[str] = set()
    for query in queries[:5]:
        for place in provider.search_restaurants(
            query,
            city=location.city,
            location=(location.lat, location.lng),
        ):
            if not place.get("id") or place["id"] in seen:
                continue
            seen.add(place["id"])
            candidates.append(enrich_restaurant(place, intent, query))
            if len(candidates) >= 8:
                return candidates
    return candidates


def _search_mock(
    intent: UserIntent,
    location: ResolvedLocation,
    queries: list[str] | None = None,
) -> list[dict]:
    candidates = []
    wait_times = _average_wait_times()
    allow_scene_fallback = current_demo_scenario() in {
        "restaurant_full",
        "traffic_delay",
    }
    requested_cuisine = _requested_cuisine(queries or [])
    for restaurant in load_json("restaurants.json").get("restaurants", []):
        if (
            intent.scene not in restaurant.get("suitable_scenes", [])
            and not allow_scene_fallback
        ):
            continue
        if (
            requested_cuisine
            and requested_cuisine not in _restaurant_text(restaurant)
        ):
            continue

        candidate = dict(restaurant)
        candidate["id"] = restaurant["restaurant_id"]
        candidate["address"] = f"{location.city}{restaurant.get('district', '')}"
        candidate["wait_time_min"] = wait_times.get(
            restaurant["restaurant_id"],
            15,
        )
        candidate["source"] = "mock"
        candidate["reservation_available"] = candidate.get(
            "reservation_supported",
            False,
        )
        candidate["diet_friendly"] = candidate.get(
            "has_low_fat_meal",
            False,
        )
        candidate["child_friendly"] = candidate.get(
            "has_kids_meal",
            False,
        )
        candidates.append(candidate)
    return candidates


def _requested_cuisine(queries: list[str]) -> str | None:
    query_text = " ".join(queries).lower()
    aliases = {
        "火锅": "hotpot",
        "日料": "japanese",
        "轻食": "light_food",
        "素食": "vegetarian",
    }
    for label, tag in aliases.items():
        if label in query_text or tag in query_text:
            return tag
    return None


def _restaurant_text(restaurant: dict) -> str:
    return " ".join(
        [
            str(restaurant.get("name", "")).lower(),
            " ".join(
                str(tag).lower() for tag in restaurant.get("tags", [])
            ),
        ]
    )


def _average_wait_times() -> dict[str, int]:
    grouped: dict[str, list[int]] = {}
    for slot in load_json("availability.json").get("availability", []):
        grouped.setdefault(slot["restaurant_id"], []).append(
            int(slot.get("queue_time_min", 0))
        )
    return {
        restaurant_id: round(sum(values) / len(values))
        for restaurant_id, values in grouped.items()
        if values
    }
