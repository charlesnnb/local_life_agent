"""Unified detection and proposal coverage for Demo exceptions."""

import copy

import pytest

from src.agents.planner_agent import PlannerAgent
from src.providers.amap_provider import AmapProvider
from src.providers.deepseek_provider import DeepSeekProvider
from src.schemas.models import ToolExecutionResult
from src.tools.reservation_tool import reserve_restaurant


QUERY = (
    "今天下午想带老婆孩子出去玩几个小时，别太远，"
    "孩子5岁，老婆最近在减肥"
)


def _planner() -> PlannerAgent:
    return PlannerAgent(
        deepseek_provider=DeepSeekProvider(enabled=False),
        amap_provider=AmapProvider(enabled=False),
    )


def _plan_and_tool_results():
    plan = _planner().run(QUERY)
    assert plan.task_plan is not None
    activity_task = next(
        task for task in plan.task_plan.tasks if task.task_type == "poi_search"
    )
    restaurant_task = next(
        task
        for task in plan.task_plan.tasks
        if task.task_type == "restaurant_search"
    )
    activity_stop = next(
        stop for stop in plan.route.stops if stop.type == "activity"
    )
    restaurant_stop = next(
        stop for stop in plan.route.stops if stop.type == "restaurant"
    )
    activity = {
        "id": "activity_original",
        "poi_id": "activity_original",
        "name": activity_stop.name,
        "type": activity_stop.category,
        "lat": activity_stop.lat,
        "lng": activity_stop.lng,
        "source": "mock",
        "wait_time_min": 18,
        "rating": 4.6,
        "tags": ["family", "kids", "indoor", "exhibition"],
    }
    activity_alternative = {
        "id": "activity_alternative",
        "poi_id": "activity_alternative",
        "name": "徐汇儿童科学体验展",
        "type": "亲子展览",
        "lat": activity_stop.lat + 0.006,
        "lng": activity_stop.lng + 0.006,
        "source": "mock",
        "wait_time_min": 5,
        "rating": 4.7,
        "tags": ["family", "kids", "indoor", "exhibition"],
    }
    restaurant = {
        "id": "restaurant_original",
        "restaurant_id": "restaurant_original",
        "name": restaurant_stop.name,
        "type": "火锅",
        "lat": restaurant_stop.lat,
        "lng": restaurant_stop.lng,
        "source": "mock",
        "wait_time_min": 70,
        "avg_price": 120,
        "rating": 4.3,
        "tags": ["hotpot", "family"],
    }
    restaurant_alternative = {
        "id": "restaurant_alternative",
        "restaurant_id": "restaurant_alternative",
        "name": "海底捞徐家汇店",
        "type": "火锅",
        "lat": restaurant_stop.lat + 0.004,
        "lng": restaurant_stop.lng + 0.004,
        "source": "mock",
        "wait_time_min": 10,
        "avg_price": 125,
        "rating": 4.7,
        "tags": ["hotpot", "family", "low_wait"],
    }
    return plan, [
        ToolExecutionResult(
            task_id=activity_task.task_id,
            tool_name=activity_task.tool_name,
            status="success",
            selected_result=activity,
            candidates=[activity, activity_alternative],
        ),
        ToolExecutionResult(
            task_id=restaurant_task.task_id,
            tool_name=restaurant_task.tool_name,
            status="success",
            selected_result=restaurant,
            candidates=[restaurant, restaurant_alternative],
        ),
    ]


def _exception_api():
    try:
        from src.core.exception_detector import detect_exceptions
        from src.core.replan_service import build_replan_proposals
    except ModuleNotFoundError:
        pytest.fail("exception detection modules are not implemented")
    return detect_exceptions, build_replan_proposals


def test_plan_response_exposes_uniform_exception_collections():
    plan, _ = _plan_and_tool_results()

    assert hasattr(plan, "exceptions")
    assert hasattr(plan, "replan_proposals")
    assert plan.exceptions == []
    assert plan.replan_proposals == []


def test_restaurant_full_produces_replacement_without_mutating_plan():
    detect_exceptions, build_replan_proposals = _exception_api()
    plan, tool_results = _plan_and_tool_results()
    reservation = next(
        action for action in plan.actions if action.type == "reservation"
    )
    reservation.status = "mock_failed"
    reservation.message = "预计到达时段暂无可预约座位"
    reservation.details = {
        "reason": "restaurant_full",
        "requested_time": reservation.details.get("time", "18:00"),
    }
    before = copy.deepcopy(plan.model_dump(mode="json"))

    exceptions = detect_exceptions(
        plan,
        tool_results,
        scenario="restaurant_full",
    )
    proposals = build_replan_proposals(plan, exceptions, tool_results)

    assert plan.model_dump(mode="json") == before
    assert [item.exception_type for item in exceptions] == ["restaurant_full"]
    assert exceptions[0].source_task_id
    assert proposals[0].requires_consent is True
    assert proposals[0].status == "pending"
    assert {
        option.operation for option in proposals[0].options
    } >= {"replace_restaurant", "keep_original"}
    replacement = next(
        option
        for option in proposals[0].options
        if option.operation == "replace_restaurant"
    )
    assert replacement.replacement_place is not None
    assert replacement.replacement_place["name"] == "海底捞徐家汇店"
    assert replacement.estimated_saved_minutes == 60


@pytest.mark.parametrize("reason", ["sold_out", "venue_closed"])
def test_activity_unavailable_keeps_activity_category_for_alternative(reason):
    detect_exceptions, build_replan_proposals = _exception_api()
    plan, tool_results = _plan_and_tool_results()
    before = copy.deepcopy(plan.model_dump(mode="json"))

    exceptions = detect_exceptions(
        plan,
        tool_results,
        scenario="activity_unavailable",
        activity_reason=reason,
    )
    proposals = build_replan_proposals(plan, exceptions, tool_results)

    assert plan.model_dump(mode="json") == before
    assert exceptions[0].exception_type == "activity_unavailable"
    assert exceptions[0].impact["reason"] == reason
    replacement = next(
        option
        for option in proposals[0].options
        if option.operation == "replace_activity"
    )
    assert replacement.replacement_place is not None
    assert "亲子展" in replacement.replacement_place["type"]
    assert replacement.replacement_place["name"] == "徐汇儿童科学体验展"


def test_traffic_delay_produces_three_consent_options():
    detect_exceptions, build_replan_proposals = _exception_api()
    plan, tool_results = _plan_and_tool_results()
    reservation = next(
        action for action in plan.actions if action.type == "reservation"
    )
    restaurant_item = next(
        item for item in plan.timeline.items if item.type == "restaurant"
    )
    reservation.details["time"] = restaurant_item.time
    before = copy.deepcopy(plan.model_dump(mode="json"))

    exceptions = detect_exceptions(
        plan,
        tool_results,
        scenario="traffic_delay",
        traffic_delay_minutes=25,
    )
    proposals = build_replan_proposals(plan, exceptions, tool_results)

    assert plan.model_dump(mode="json") == before
    assert exceptions[0].exception_type == "schedule_conflict"
    assert exceptions[0].impact["delay_minutes"] == 25
    assert exceptions[0].impact["latest_arrival"] > restaurant_item.time
    assert {
        option.operation for option in proposals[0].options
    } == {"adjust_reservation", "replace_restaurant", "keep_original"}


def test_normal_scenario_does_not_change_existing_response():
    detect_exceptions, build_replan_proposals = _exception_api()
    plan, tool_results = _plan_and_tool_results()

    exceptions = detect_exceptions(plan, tool_results, scenario="normal")
    proposals = build_replan_proposals(plan, exceptions, tool_results)

    assert exceptions == []
    assert proposals == []


def test_activity_without_qualified_alternative_is_explicit():
    detect_exceptions, build_replan_proposals = _exception_api()
    plan, tool_results = _plan_and_tool_results()
    activity_result = next(
        result
        for result in tool_results
        if result.selected_result
        and result.selected_result.get("poi_id")
    )
    activity_result.candidates = [activity_result.selected_result]

    exceptions = detect_exceptions(
        plan,
        tool_results,
        scenario="activity_unavailable",
    )
    proposals = build_replan_proposals(plan, exceptions, tool_results)

    assert len(proposals[0].options) == 1
    assert proposals[0].options[0].operation == "keep_original"
    assert "没有找到符合条件的替代活动" in proposals[0].options[0].description


def test_restaurant_full_scenario_drives_mock_tool_and_planner(
    monkeypatch,
):
    monkeypatch.setenv("DEMO_SCENARIO", "restaurant_full")
    plan, _ = _plan_and_tool_results()
    reservation = next(
        action for action in plan.actions if action.type == "reservation"
    )

    assert reservation.status == "mock_failed"
    assert reservation.details["reason"] == "restaurant_full"
    assert [item.exception_type for item in plan.exceptions] == [
        "restaurant_full"
    ]
    assert plan.replan_proposals[0].status == "pending"


def test_activity_unavailable_scenario_is_attached_by_planner(monkeypatch):
    monkeypatch.setenv("DEMO_SCENARIO", "activity_unavailable")

    plan = _planner().run(QUERY)

    assert [item.exception_type for item in plan.exceptions] == [
        "activity_unavailable"
    ]
    assert plan.exceptions[0].impact["available"] is False
    assert any(
        option.operation == "replace_activity"
        for option in plan.replan_proposals[0].options
    )


def test_traffic_delay_scenario_is_attached_without_applying_it(
    monkeypatch,
):
    monkeypatch.setenv("DEMO_SCENARIO", "traffic_delay")
    normal = _planner().run(QUERY)
    monkeypatch.setenv("DEMO_SCENARIO", "normal")
    baseline = _planner().run(QUERY)

    assert [item.exception_type for item in normal.exceptions] == [
        "schedule_conflict"
    ]
    assert normal.route == baseline.route
    assert normal.timeline == baseline.timeline


def test_exception_flow_emits_concise_progress(monkeypatch):
    monkeypatch.setenv("DEMO_SCENARIO", "restaurant_full")
    events = []

    _planner().run(QUERY, event_callback=events.append)

    stages = [event.stage for event in events]
    assert "exception_detected" in stages
    assert "replan_search" in stages
    assert "replan_pending" in stages
    assert any("等待你的确认" in event.message for event in events)


def test_direct_reservation_tool_can_simulate_restaurant_full(monkeypatch):
    monkeypatch.setenv("DEMO_SCENARIO", "restaurant_full")
    plan, tool_results = _plan_and_tool_results()
    restaurant = next(
        result.selected_result
        for result in tool_results
        if result.selected_result
        and result.selected_result.get("restaurant_id")
    )

    action = reserve_restaurant(
        restaurant,
        "18:00",
        plan.user_intent,
    )

    assert action.status == "mock_failed"
    assert action.details == {
        "reason": "restaurant_full",
        "requested_time": "18:00",
        "source": "mock_demo_scenario",
    }


@pytest.mark.parametrize(
    ("scenario", "query", "exception_type"),
    [
        (
            "restaurant_full",
            "今天下午去看展，晚上吃火锅，最好提前预约，不想排队",
            "restaurant_full",
        ),
        (
            "activity_unavailable",
            "下午带 5 岁孩子去亲子展览，之后找个清淡餐厅吃饭",
            "activity_unavailable",
        ),
        (
            "traffic_delay",
            "下午去展览，16:30 预约餐厅吃饭",
            "schedule_conflict",
        ),
    ],
)
def test_required_demo_inputs_reach_exception_confirmation(
    monkeypatch,
    scenario,
    query,
    exception_type,
):
    monkeypatch.setenv("DEMO_SCENARIO", scenario)

    plan = _planner().run(query)

    assert [item.exception_type for item in plan.exceptions] == [
        exception_type
    ]
    assert plan.replan_proposals
    assert plan.replan_proposals[0].status == "pending"
    assert any(
        option.operation == "keep_original"
        for option in plan.replan_proposals[0].options
    )
    assert any(
        option.operation != "keep_original"
        for option in plan.replan_proposals[0].options
    )
    if scenario == "activity_unavailable":
        replacement = next(
            option.replacement_place
            for option in plan.replan_proposals[0].options
            if option.operation == "replace_activity"
        )
        assert replacement is not None
        min_age, max_age = replacement["age_range"]
        assert min_age <= 5 <= max_age
