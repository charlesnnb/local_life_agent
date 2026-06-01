"""Mock POI API — search and filter POIs from JSON data."""

from backend.data_loader import get_pois


def search_pois(
    location_district: str | None = None,
    radius_km: float = 8.0,
    scene: str | None = None,
    tags: list[str] | None = None,
    age: int | None = None,
    time_window: tuple[str, str] | None = None,
    indoor_only: bool = False,
) -> list[dict]:
    """Search POIs with filters. Returns list of matching POI dicts."""
    results = []
    for poi in get_pois():
        # District filter
        if location_district and poi.get("district") != location_district:
            continue

        # Scene filter
        if scene and scene not in poi.get("suitable_scenes", []):
            continue

        # Tags filter (at least one tag matching)
        if tags:
            poi_tags = set(poi.get("tags", []))
            if not poi_tags.intersection(tags):
                continue

        # Age filter
        if age is not None:
            age_min, age_max = poi.get("age_range", [0, 99])
            if age < age_min or age > age_max:
                continue

        # Indoor filter
        if indoor_only and not poi.get("indoor", False):
            continue

        # Time window filter
        if time_window:
            open_t = poi.get("open_time", "00:00")
            close_t = poi.get("close_time", "23:59")
            if time_window[0] < open_t or time_window[1] > close_t:
                continue

        results.append(poi)

    return results
