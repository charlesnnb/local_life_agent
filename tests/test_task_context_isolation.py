"""Per-task companion and child constraints must not leak across stages."""

from src.core.intent_parser import parse_intent
from src.core.itinerary_composer import compose_itinerary
from src.core.llm_task_planner import build_rule_task_plan
from src.core.tool_router import ToolRouter
from src.agents.planner_agent import PlannerAgent
from src.providers.amap_provider import AmapProvider
from src.providers.deepseek_provider import DeepSeekProvider
from src.services.location_service import resolve_location
from src.services.preference_service import get_current_profile


FAMILY_QUERY = (
    "今天下午想带老婆孩子出去玩几个小时爬山去，孩子5岁，"
    "老婆最近在增肥，晚上去酒吧之类的"
)


class ContextAmap:
    enabled = True
    is_available = True
    last_error = None
    unavailable_reason = None

    def search_poi(self, keywords, city=None, location=None):
        if any(word in keywords for word in ("酒吧", "清吧", "小酒馆")):
            return [{
                "id": "bar_1",
                "name": "梧桐里清吧",
                "type": "体育休闲服务;酒吧;清吧",
                "address": city or "上海",
                "lat": 31.211,
                "lng": 121.438,
                "rating": 4.5,
                "source": "amap",
            }]
        return [{
            "id": "mountain_1",
            "name": "佘山国家森林公园登山步道",
            "type": "风景名胜;森林公园;登山步道",
            "address": city or "上海",
            "lat": 31.098,
            "lng": 121.191,
            "rating": 4.6,
            "source": "amap",
        }]


def _family_plan():
    intent = parse_intent(FAMILY_QUERY)
    plan = build_rule_task_plan(FAMILY_QUERY, intent)
    intent.tasks = plan.tasks
    intent.time_windows = plan.time_windows
    return intent, plan


def test_family_child_context_is_kept_on_afternoon_climbing_task():
    _, plan = _family_plan()
    assert [task.task_type for task in plan.tasks] == [
        "poi_search",
        "bar_visit",
    ]
    climbing = next(task for task in plan.tasks if task.target == "爬山")

    assert climbing.companions == ["老婆", "孩子"]
    assert climbing.child_age == 5


def test_family_child_context_does_not_leak_into_evening_bar_task():
    _, plan = _family_plan()
    bar = next(task for task in plan.tasks if task.task_type == "bar_visit")

    assert bar.companions == ["adult"]
    assert bar.child_age is None
    assert any("成人场景" in constraint for constraint in bar.constraints)


def test_family_bar_still_returns_result_and_emits_adult_context_warning():
    intent, plan = _family_plan()
    location = resolve_location(intent)
    results = ToolRouter(ContextAmap()).execute(
        plan.tasks,
        intent,
        location,
        profile=get_current_profile(),
    )

    bar_result = next(
        result
        for task, result in zip(plan.tasks, results, strict=True)
        if task.task_type == "bar_visit"
    )
    assert bar_result.status == "success"
    assert "清吧" in bar_result.selected_result["name"]

    itinerary = compose_itinerary(intent, plan, results, location)
    assert any("成人场景" in warning for warning in itinerary.warnings)


def test_explicit_child_at_bar_creates_warning_without_hard_filtering():
    query = "晚上带孩子去酒吧，孩子5岁"
    intent = parse_intent(query)
    plan = build_rule_task_plan(query, intent)
    bar = plan.tasks[0]
    intent.tasks = plan.tasks
    intent.time_windows = plan.time_windows

    assert bar.child_age == 5
    assert "孩子" in bar.companions
    assert any("需确认" in constraint for constraint in bar.constraints)

    result = ToolRouter(ContextAmap()).execute(
        plan.tasks,
        intent,
        resolve_location(intent),
        profile=get_current_profile(),
    )[0]
    assert result.status == "success"


def test_acceptance_query_has_climbing_and_bar_in_offline_fallback():
    result = PlannerAgent(
        deepseek_provider=DeepSeekProvider(enabled=False),
        amap_provider=AmapProvider(enabled=False),
    ).run(FAMILY_QUERY)
    stop_names = [stop.name for stop in result.route.stops]

    assert any(
        any(word in name for word in ("山", "森林", "登山", "步道"))
        for name in stop_names
    )
    assert any(
        any(word in name for word in ("酒吧", "清吧", "小酒馆"))
        for name in stop_names
    )
    assert all("游泳" not in name for name in stop_names)
    assert all(stop.type != "restaurant" for stop in result.route.stops)
