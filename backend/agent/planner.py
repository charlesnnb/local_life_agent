"""Itinerary construction: builds a time-ordered plan from scored candidates."""

import copy
from backend.agent.scorer import score_poi, score_restaurant, score_plan, _time_to_minutes


def build_itinerary(
    scene: str,
    constraints: dict,
    pois: list[dict],
    restaurants: list[dict],
    poi_travel: dict[str, dict],
    rest_travel: dict[str, dict],
    poi_scores: list[float],
    rest_scores: list[float],
    home_id: str,
) -> dict:
    """Build a complete itinerary from scored candidates.

    Returns dict with itinerary items, total time, and scores.
    """
    start_time = constraints["start_time"]
    transport = constraints.get("transport", "taxi")
    max_dist = constraints.get("max_distance_km", 8)

    # Pick best POI and restaurant
    best_poi_idx = _argmax(poi_scores)
    best_rest_idx = _argmax(rest_scores)

    if best_poi_idx < 0 or best_rest_idx < 0:
        return {"itinerary": [], "total_time_min": 0, "plan_score": 0}

    poi = pois[best_poi_idx]
    restaurant = restaurants[best_rest_idx]

    # Travel times
    home_to_poi = poi_travel.get(poi["poi_id"], {}).get("duration_min", 20)
    poi_to_rest = _get_poi_to_rest_travel(
        poi["poi_id"], restaurant["restaurant_id"], constraints
    )
    rest_to_home = rest_travel.get(restaurant["restaurant_id"], {}).get("duration_min", 20)

    # Activity duration
    poi_duration = poi.get("avg_duration_min", 90)
    meal_duration = 70  # approximate

    current = _time_to_minutes(start_time)
    items = []

    # 1. Travel from home to POI
    items.append({
        "time_start": _minutes_to_time(current),
        "time_end": _minutes_to_time(current + home_to_poi),
        "type": "travel",
        "title": f"打车前往{poi['name']}",
        "description": f"距离约 {home_to_poi * 0.3:.1f}km，预计 {home_to_poi} 分钟",
        "location_id": poi["poi_id"],
    })
    current += home_to_poi

    # 2. Activity at POI
    poi_end_time = _minutes_to_time(current + poi_duration)
    items.append({
        "time_start": _minutes_to_time(current),
        "time_end": poi_end_time,
        "type": "activity",
        "title": poi["name"],
        "description": f"游玩约 {poi_duration} 分钟，{_poi_desc(poi, scene)}",
        "location_id": poi["poi_id"],
    })
    current += poi_duration

    # 3. Travel from POI to restaurant
    items.append({
        "time_start": _minutes_to_time(current),
        "time_end": _minutes_to_time(current + poi_to_rest),
        "type": "travel",
        "title": f"前往{restaurant['name']}",
        "description": f"预计 {poi_to_rest} 分钟",
        "location_id": restaurant["restaurant_id"],
    })
    current += poi_to_rest

    # Meal time needs to be at least 16:30
    if current < _time_to_minutes("16:30"):
        current = _time_to_minutes("16:30")

    # 4. Meal
    items.append({
        "time_start": _minutes_to_time(current),
        "time_end": _minutes_to_time(current + meal_duration),
        "type": "meal",
        "title": f"晚餐@{restaurant['name']}",
        "description": _restaurant_desc(restaurant, constraints),
        "location_id": restaurant["restaurant_id"],
    })
    current += meal_duration

    # 5. Optional extra (family: cake/flower, friends: coffee/dessert)
    optional_extra = constraints.get("optional_extra", [])
    if optional_extra:
        extra_duration = 20
        extra_type = optional_extra[0]
        items.append({
            "time_start": _minutes_to_time(current),
            "time_end": _minutes_to_time(current + extra_duration),
            "type": "extra",
            "title": f"顺路取{_extra_name(extra_type)}",
            "description": f"取{_extra_name(extra_type)}，约 {extra_duration} 分钟",
            "location_id": None,
        })
        current += extra_duration

    # 6. Return home
    items.append({
        "time_start": _minutes_to_time(current),
        "time_end": _minutes_to_time(current + rest_to_home),
        "type": "return",
        "title": "打车回家",
        "description": f"预计 {rest_to_home} 分钟到家",
        "location_id": home_id,
    })
    current += rest_to_home

    total_time = current - _time_to_minutes(start_time)

    # Plan score
    plan_score = score_plan(
        total_time_min=total_time,
        route_smoothness=_calc_route_smoothness(home_to_poi, poi_to_rest, rest_to_home),
        people_match=0.9,
        execution_success=0.85,
        experience_richness=0.8,
    )

    return {
        "itinerary": items,
        "total_time_min": total_time,
        "plan_score": plan_score,
        "selected_poi": poi,
        "selected_restaurant": restaurant,
    }


def _get_poi_to_rest_travel(poi_id: str, rest_id: str, constraints: dict) -> int:
    """Get travel time from POI to restaurant from travel data."""
    # Will be populated by actual travel time lookups
    from backend.data_loader import get_travel_times
    for t in get_travel_times():
        if t["from"] == poi_id and t["to"] == rest_id:
            return t.get("taxi_time_min", 15)
    return 15  # default


def _minutes_to_time(m: int) -> str:
    h = m // 60
    mm = m % 60
    return f"{h:02d}:{mm:02d}"


def _argmax(scores: list[float]) -> int:
    if not scores:
        return -1
    return max(range(len(scores)), key=lambda i: scores[i])


def _poi_desc(poi: dict, scene: str) -> str:
    tags = ", ".join(poi.get("tags", [])[:3])
    indoor = "室内" if poi.get("indoor") else "户外"
    return f"{indoor}，{tags}，评分 {poi.get('rating', 0)}"


def _restaurant_desc(r: dict, constraints: dict) -> str:
    parts = []
    if r.get("has_low_fat_meal"):
        parts.append("有低脂餐")
    if r.get("has_kids_meal"):
        parts.append("有儿童餐")
    parts.append(f"人均 ¥{r.get('avg_price', 0)}")
    return "，".join(parts) if parts else ""


def _extra_name(extra_type: str) -> str:
    return {"cake": "低糖蛋糕", "flower": "鲜花", "coffee": "咖啡", "dessert": "甜品"}.get(
        extra_type, extra_type
    )


def _calc_route_smoothness(home_to_poi: int, poi_to_rest: int, rest_to_home: int) -> float:
    """Calculate how smooth the route is (shorter travel = smoother)."""
    total = home_to_poi + poi_to_rest + rest_to_home
    if total == 0:
        return 0.5
    # Ideal: each leg under 25 min
    smooth = 1.0
    for leg in [home_to_poi, poi_to_rest, rest_to_home]:
        if leg > 30:
            smooth -= 0.2
        elif leg > 20:
            smooth -= 0.1
    return max(0, smooth)
