"""POI search tools with unified return format."""

from backend.mock_api.poi_api import search_pois as _search_pois


def search_poi(
    location: str | None = None,
    radius_km: float = 8.0,
    scene: str | None = None,
    tags: list[str] | None = None,
    age: int | None = None,
    time_window: tuple | None = None,
    indoor_only: bool = False,
) -> dict:
    """Search activity POIs. Returns unified result dict."""
    try:
        results = _search_pois(
            location_district=location,
            radius_km=radius_km,
            scene=scene,
            tags=tags,
            age=age,
            time_window=time_window,
            indoor_only=indoor_only,
        )
        if not results:
            # Fallback: broaden search
            fallback_tags = [t for t in (tags or []) if t not in ("outdoor",)]
            if radius_km < 15:
                results = _search_pois(
                    location_district=location,
                    radius_km=min(radius_km * 1.5, 20),
                    scene=scene,
                    tags=fallback_tags,
                    indoor_only=indoor_only,
                )
        return {
            "success": True,
            "data": results,
            "error_code": None,
            "message": f"找到 {len(results)} 个POI" if results else "未找到匹配的POI",
        }
    except Exception as e:
        return {"success": False, "data": [], "error_code": "POI_SEARCH_ERROR", "message": str(e)}
