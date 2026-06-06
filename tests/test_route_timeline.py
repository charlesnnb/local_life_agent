"""Priority 2 coverage for route and timeline structures."""

from src.agents.planner_agent import PlannerAgent
from src.core.intent_parser import parse_intent
from src.schemas.models import LocationInput
from src.services.location_service import resolve_location
from src.tools.route_tool import estimate_route


QUERY = "今天下午想带老婆孩子出去玩几个小时，别太远，孩子5岁，老婆最近在减肥"


def test_plan_response_contains_executable_route():
    result = PlannerAgent().plan(QUERY)

    assert result.route.origin.name == "默认位置：上海徐汇"
    assert result.route.origin.lat == 31.1886
    assert result.route.origin.lng == 121.4365

    stop_types = {stop.type for stop in result.route.stops}
    assert {"activity", "restaurant"} <= stop_types
    assert all(stop.lat and stop.lng for stop in result.route.stops)
    assert all(
        5 <= stop.estimated_travel_minutes <= 45
        for stop in result.route.stops
    )
    assert 5 <= result.route.return_to_origin_minutes <= 45
    assert 15 <= result.route.total_travel_minutes <= 135
    assert result.route.total_travel_minutes == (
        sum(stop.estimated_travel_minutes for stop in result.route.stops)
        + result.route.return_to_origin_minutes
    )


def test_plan_response_contains_typed_timeline():
    result = PlannerAgent().plan(QUERY)

    timeline_types = {item.type for item in result.timeline.items}
    assert {"departure", "activity", "restaurant"} <= timeline_types
    assert result.timeline.items[0].time == "14:00"
    assert result.timeline.total_duration_minutes > 0


def test_route_fallback_never_returns_extreme_minutes():
    intent = parse_intent("今天下午出去玩")
    location = resolve_location(
        intent,
        LocationInput(address="北京市海淀区某街道的完整家庭地址"),
    )
    route = estimate_route(
        location.location_id,
        "far_mock_destination",
        location,
        {"lat": 39.9042, "lng": 116.4074},
    )

    assert location.source == "demo_default"
    assert location.city == "上海"
    assert 5 <= route.duration_min <= 45
    assert route.duration_min != 1778


def test_serialized_response_contains_no_extreme_route_value():
    payload = PlannerAgent().plan(QUERY).model_dump_json()

    assert '"route"' in payload
    assert '"timeline"' in payload
    assert "1778" not in payload
