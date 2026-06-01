"""Restaurant tools with unified return format."""

from backend.mock_api.restaurant_api import search_restaurants as _search_restaurants
from backend.data_loader import get_availability


def search_restaurant(
    location: str | None = None,
    radius_km: float = 8.0,
    scene: str | None = None,
    tags: list[str] | None = None,
    party_size: int = 2,
    meal_time: str | None = None,
    has_low_fat: bool = False,
    has_kids_meal: bool = False,
) -> dict:
    """Search restaurants. Returns unified result dict."""
    try:
        results = _search_restaurants(
            location_district=location,
            radius_km=radius_km,
            scene=scene,
            tags=tags,
            party_size=party_size,
            meal_time=meal_time,
            has_low_fat=has_low_fat,
            has_kids_meal=has_kids_meal,
        )
        if not results:
            # Fallback: broaden
            results = _search_restaurants(
                location_district=location,
                radius_km=min(radius_km * 1.4, 20),
                scene=scene,
                party_size=party_size,
                meal_time=meal_time,
            )
        return {
            "success": True,
            "data": results,
            "error_code": None,
            "message": f"找到 {len(results)} 个餐厅" if results else "未找到匹配的餐厅",
        }
    except Exception as e:
        return {"success": False, "data": [], "error_code": "RESTAURANT_SEARCH_ERROR", "message": str(e)}


def check_restaurant_availability(
    restaurant_id: str, time: str, party_size: int
) -> dict:
    """Check table availability for a restaurant at given time."""
    try:
        for a in get_availability():
            if a["restaurant_id"] == restaurant_id and a["time"] == time:
                can_seat = a.get("remaining_tables", 0) > 0
                return {
                    "success": True,
                    "data": {
                        "available": a.get("available", False) and can_seat,
                        "remaining_tables": a.get("remaining_tables", 0),
                        "queue_time_min": a.get("queue_time_min", 0),
                        "suggested_slots": [],
                    },
                    "error_code": None,
                    "message": "有空位" if can_seat else "当前时段无空位",
                }

        # No exact time match, find nearby slots
        suggestions = _find_nearby_slots(restaurant_id, time)
        return {
            "success": True,
            "data": {
                "available": False,
                "remaining_tables": 0,
                "queue_time_min": 0,
                "suggested_slots": suggestions,
            },
            "error_code": None,
            "message": "该时间无记录，已返回推荐时段" if suggestions else "未找到可用时段",
        }
    except Exception as e:
        return {"success": False, "data": {}, "error_code": "AVAILABILITY_ERROR", "message": str(e)}


def check_queue_time(target_id: str, time: str) -> dict:
    """Check queue time for a restaurant at given time."""
    try:
        for a in get_availability():
            if a["restaurant_id"] == target_id and a["time"] == time:
                qt = a.get("queue_time_min", 0)
                acceptable = qt <= 30
                return {
                    "success": True,
                    "data": {"queue_time_min": qt, "acceptable": acceptable},
                    "error_code": None,
                    "message": "排队时间可接受" if acceptable else f"排队时间 {qt} 分钟，超过30分钟阈值",
                }
        return {
            "success": True,
            "data": {"queue_time_min": 5, "acceptable": True},
            "error_code": None,
            "message": "无排队记录，估计可接受",
        }
    except Exception as e:
        return {"success": False, "data": {}, "error_code": "QUEUE_ERROR", "message": str(e)}


def _find_nearby_slots(restaurant_id: str, target_time: str) -> list[str]:
    """Find nearby available time slots for a restaurant."""
    slots = []
    for a in get_availability():
        if a["restaurant_id"] == restaurant_id and a.get("available"):
            slots.append(a["time"])
    slots.sort()
    # Return up to 3 slots near target_time
    result = [s for s in slots if s >= target_time][:3]
    if not result:
        result = slots[-3:]
    return result
