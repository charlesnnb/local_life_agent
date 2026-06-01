"""Travel tools with unified return format."""

from backend.mock_api.travel_api import estimate_travel_time as _estimate


def estimate_travel_time(
    from_id: str,
    to_id: str,
    transport: str = "taxi",
    departure_time: str | None = None,
) -> dict:
    """Estimate travel time between locations. Returns unified result dict."""
    try:
        result = _estimate(
            from_id=from_id, to_id=to_id, transport=transport, departure_time=departure_time
        )
        return {
            "success": True,
            "data": result,
            "error_code": None,
            "message": f"距离 {result['distance_km']}km，预计 {result['duration_min']} 分钟",
        }
    except Exception as e:
        return {"success": False, "data": {}, "error_code": "TRAVEL_ERROR", "message": str(e)}
