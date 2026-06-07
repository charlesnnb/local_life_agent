"""Failed future tasks must not stretch an otherwise completed itinerary."""

from src.core.intent_parser import parse_intent
from src.core.itinerary_composer import compose_itinerary
from src.core.llm_task_planner import build_rule_task_plan
from src.schemas.models import ToolExecutionResult
from src.services.location_service import resolve_location


QUERY = "今天下午带孩子去爬山，孩子5岁，晚上去酒吧"


def _compose():
    intent = parse_intent(QUERY)
    plan = build_rule_task_plan(QUERY, intent)
    climbing = next(task for task in plan.tasks if task.target == "爬山")
    bar = next(task for task in plan.tasks if task.task_type == "bar_visit")
    results = [
        ToolExecutionResult(
            task_id=climbing.task_id,
            tool_name=climbing.tool_name,
            status="success",
            selected_result={
                "id": "mountain_1",
                "name": "佘山国家森林公园登山步道",
                "lat": 31.098,
                "lng": 121.191,
                "avg_duration_min": 90,
                "source": "amap",
            },
        ),
        ToolExecutionResult(
            task_id=bar.task_id,
            tool_name=bar.tool_name,
            status="failed",
            message="no_relevant_result",
            rejected_candidates=[{
                "id": "hotel_bar",
                "name": "某酒店大堂吧",
                "reason": "普通酒吧查询降低酒店大堂吧优先级",
            }],
        ),
    ]
    return compose_itinerary(
        intent,
        plan,
        results,
        resolve_location(intent),
    )


def _minutes(value: str) -> int:
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def test_failed_evening_task_does_not_delay_return_until_1930():
    itinerary = _compose()
    return_item = next(
        item for item in itinerary.timeline.items if item.type == "return"
    )

    assert _minutes(return_item.time) < 19 * 60 + 30


def test_failed_task_is_preserved_as_warning_or_pending_step():
    itinerary = _compose()

    assert any("酒吧" in warning and "未找到" in warning for warning in itinerary.warnings)
    assert any(
        step.action == "待确认" and "酒吧" in step.description
        for step in itinerary.plan.steps
    )


def test_successful_task_still_generates_route_and_timeline():
    itinerary = _compose()

    assert [stop.name for stop in itinerary.route.stops] == [
        "佘山国家森林公园登山步道"
    ]
    assert any(item.type == "activity" for item in itinerary.timeline.items)
    assert any(item.type == "return" for item in itinerary.timeline.items)
    assert any(item.type == "arrival" for item in itinerary.timeline.items)


def test_timeline_has_no_multi_hour_gap_caused_by_failed_task():
    itinerary = _compose()
    times = sorted(_minutes(item.time) for item in itinerary.timeline.items)
    gaps = [
        later - earlier
        for earlier, later in zip(times, times[1:])
    ]

    assert max(gaps) < 180
    assert itinerary.timeline.total_duration_minutes < 240
