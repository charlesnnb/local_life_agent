"""Plan Generator: builds the final itinerary from ranked candidates."""

import logging
from backend.agent.ranking import ScoreBreakdown

logger = logging.getLogger(__name__)


def build_plan(
    parsed_intent: dict,
    poi_candidates: list[dict],
    restaurant_candidates: list[dict],
    poi_rankings: list[ScoreBreakdown],
    restaurant_rankings: list[ScoreBreakdown],
    route_data: dict[str, dict] | None = None,
    weather_data: dict | None = None,
) -> dict:
    """Build the final plan from ranked candidates.

    Returns a dict with the complete plan structure.
    """
    # Top candidates (highest scored)
    top_poi = poi_rankings[0] if poi_rankings else None
    top_restaurant = restaurant_rankings[0] if restaurant_rankings else None

    # Find the actual POI/restaurant dicts
    top_poi_dict = next(
        (p for p in poi_candidates if p.get("id", p.get("poi_id")) == top_poi.candidate_id),
        poi_candidates[0] if poi_candidates else None,
    ) if top_poi else None

    top_rest_dict = next(
        (r for r in restaurant_candidates if r.get("id", r.get("restaurant_id")) == top_restaurant.candidate_id),
        restaurant_candidates[0] if restaurant_candidates else None,
    ) if top_restaurant else None

    # Build itinerary items
    itinerary = _build_itinerary(parsed_intent, top_poi_dict, top_rest_dict, route_data)

    # Collect all rankings
    all_poi_rankings = [r.to_dict() for r in (poi_rankings or [])]
    all_rest_rankings = [r.to_dict() for r in (restaurant_rankings or [])]

    return {
        "scene": parsed_intent.get("scene", "unknown"),
        "itinerary": itinerary,
        "top_poi": top_poi_dict,
        "top_restaurant": top_rest_dict,
        "top_poi_score": top_poi.to_dict() if top_poi else None,
        "top_restaurant_score": top_restaurant.to_dict() if top_restaurant else None,
        "all_poi_rankings": all_poi_rankings,
        "all_restaurant_rankings": all_rest_rankings,
        "weather": weather_data,
    }


def _build_itinerary(
    intent: dict,
    top_poi: dict | None,
    top_restaurant: dict | None,
    route_data: dict[str, dict] | None = None,
) -> list[dict]:
    """Build a simple itinerary sequence."""
    items = []

    start_time = intent.get("date_or_time") or "下午2:00"
    transport = intent.get("transport_preference") or "driving"

    # If no candidates, return empty
    if not top_poi and not top_restaurant:
        return items

    # Travel to venue
    if top_poi:
        poi_name = top_poi.get("name", "活动地点")
        poi_id = top_poi.get("id", top_poi.get("poi_id", ""))
        route = (route_data or {}).get(poi_id, {})
        travel_mins = (route.get("duration_sec", 1200) or 1200) // 60
        items.append({
            "time": start_time,
            "type": "travel",
            "title": f"前往{poi_name}",
            "description": f"预计 {travel_mins} 分钟",
            "location_id": poi_id,
        })

        items.append({
            "time": "活动时间",
            "type": "activity",
            "title": poi_name,
            "description": poi_get_desc(top_poi),
            "location_id": poi_id,
        })

    # Meal
    if top_restaurant:
        rest_name = top_restaurant.get("name", "餐厅")
        rest_id = top_restaurant.get("id", top_restaurant.get("restaurant_id", ""))
        items.append({
            "time": "晚餐时间",
            "type": "meal",
            "title": f"晚餐 @ {rest_name}",
            "description": restaurant_get_desc(top_restaurant),
            "location_id": rest_id,
        })

    items.append({
        "time": "返程",
        "type": "return",
        "title": f"返回（{transport}）",
        "description": "",
        "location_id": None,
    })

    return items


def poi_get_desc(poi: dict) -> str:
    parts = []
    addr = poi.get("address", "")
    if addr:
        parts.append(addr)
    rating = poi.get("rating")
    if rating and rating != "unknown":
        parts.append(f"评分 {rating}")
    price = poi.get("avg_price")
    if price and price != "unknown":
        parts.append(f"人均 ¥{price}")
    tags = poi.get("tags", [])
    if tags and tags != "unknown" and isinstance(tags, list):
        parts.append(" · ".join(tags[:3]))
    return " | ".join(parts) if parts else ""


def restaurant_get_desc(r: dict) -> str:
    parts = []
    type_ = r.get("type", "")
    if type_ and type_ != "unknown":
        parts.append(type_.replace(";", " · "))
    price = r.get("avg_price")
    if price and price != "unknown":
        parts.append(f"人均 ¥{price}")
    rating = r.get("rating")
    if rating and rating != "unknown":
        parts.append(f"评分 {rating}")
    return " | ".join(parts) if parts else ""
