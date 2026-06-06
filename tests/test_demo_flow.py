"""Minimal tests for the Local Life Agent MVP."""

from src.agents.planner_agent import PlannerAgent
from src.core.intent_parser import parse_intent
from src.services.location_service import resolve_location
from src.tools.route_tool import estimate_route


QUERY = "今天下午想带老婆孩子出去玩几个小时，别太远，孩子5岁，老婆最近在减肥"


def test_intent_parser_extracts_mvp_constraints():
    intent = parse_intent(QUERY)

    assert intent.time_window == "今天下午"
    assert intent.duration_hours == [3.0, 4.0]
    assert intent.companions == ["老婆", "孩子"]
    assert intent.child_age == 5
    assert intent.scene == "family"
    assert "亲子" in intent.activity_preferences
    assert "减脂" in intent.diet_preferences
    assert intent.distance_preference == "nearby"


def test_demo_flow_returns_executable_plan():
    result = PlannerAgent().plan(QUERY)

    assert any(step.action in {"亲子活动", "活动"} and step.place for step in result.plan.steps)
    assert any(step.action == "晚餐" and step.place for step in result.plan.steps)
    assert len(result.plan.steps) >= 5
    assert result.plan.reasons

    reservation = next(action for action in result.actions if action.type == "reservation")
    message = next(action for action in result.actions if action.type == "send_message")
    assert reservation.status == "mock_success"
    assert message.status == "mock_success"
    assert message.message


def test_parser_supports_friends_and_weekend_evening():
    intent = parse_intent("周末晚上和朋友4个人在附近聚会，想吃清淡一点")

    assert intent.scene == "friends"
    assert intent.party_size == 4
    assert intent.time_window == "周末晚上"
    assert intent.distance_preference == "nearby"
    assert "清淡" in intent.diet_preferences


def test_default_location_and_route_are_demo_safe():
    intent = parse_intent("下午出去玩几个小时")
    location = resolve_location(intent)
    route = estimate_route(
        location.location_id,
        "unknown_destination",
        location,
        {},
    )

    assert location.address == "上海徐汇区（Demo 默认位置）"
    assert location.source == "demo_default"
    assert 5 <= route.duration_min <= 45
