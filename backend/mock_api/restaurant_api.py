"""Mock Restaurant API — search and filter restaurants from JSON data."""

from backend.data_loader import get_restaurants


def search_restaurants(
    location_district: str | None = None,
    radius_km: float = 8.0,
    scene: str | None = None,
    tags: list[str] | None = None,
    party_size: int = 2,
    meal_time: str | None = None,
    has_low_fat: bool = False,
    has_kids_meal: bool = False,
    reservation_required: bool = False,
) -> list[dict]:
    """Search restaurants with filters."""
    results = []
    for r in get_restaurants():
        if location_district and r.get("district") != location_district:
            continue

        if scene and scene not in r.get("suitable_scenes", []):
            continue

        if tags:
            r_tags = set(r.get("tags", []))
            if not r_tags.intersection(tags):
                continue

        if has_low_fat and not r.get("has_low_fat_meal"):
            continue

        if has_kids_meal and not r.get("has_kids_meal"):
            continue

        if reservation_required and not r.get("reservation_supported"):
            continue

        # Time filter
        if meal_time:
            open_t = r.get("open_time", "00:00")
            close_t = r.get("close_time", "23:59")
            if meal_time < open_t or meal_time > close_t:
                continue

        results.append(r)

    return results
