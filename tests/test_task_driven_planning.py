"""End-to-end coverage for the corrected task-driven planning pipeline."""

from src.agents.planner_agent import PlannerAgent
from src.providers.amap_provider import AmapProvider
from src.providers.deepseek_provider import DeepSeekProvider


QUERY = (
    "今天工作完特别累，中午给我点个汉堡，下午出去玩蹦床，"
    "找个可以钓鱼的地方，晚上去高档酒店"
)
LEGACY_QUERY = (
    "今天下午想带老婆孩子出去玩几个小时，别太远，"
    "孩子5岁，老婆最近在减肥"
)


def _planner() -> PlannerAgent:
    return PlannerAgent(
        deepseek_provider=DeepSeekProvider(enabled=False),
        amap_provider=AmapProvider(enabled=False),
    )


def test_sample_query_keeps_all_tasks_and_ordered_time_windows():
    result = _planner().run(QUERY)

    assert result.task_plan is not None
    assert [task.task_type for task in result.task_plan.tasks] == [
        "food_delivery",
        "poi_search",
        "poi_search",
        "hotel_search",
    ]
    assert result.task_plan.time_windows == ["中午", "下午", "晚上"]

    payload = result.model_dump_json()
    assert "汉堡" in payload
    assert "蹦床" in payload
    assert "钓鱼" in payload
    assert "高档酒店" in payload


def test_delivery_stays_out_of_route_and_offline_tasks_stay_in():
    result = _planner().run(QUERY)

    route_names = " ".join(stop.name for stop in result.route.stops)
    assert "汉堡" not in route_names
    assert "蹦床" in route_names
    assert "钓鱼" in route_names
    assert any(
        keyword in route_names
        for keyword in ("酒店", "酒廊")
    )
    assert [stop.type for stop in result.route.stops] == [
        "activity",
        "activity",
        "hotel",
    ]


def test_timeline_is_ordered_and_dense_afternoon_is_explained():
    result = _planner().run(QUERY)

    timeline_text = " ".join(
        f"{item.time} {item.title} {item.description}"
        for item in result.timeline.items
    )
    assert timeline_text.index("汉堡") < timeline_text.index("蹦床")
    assert timeline_text.index("蹦床") < timeline_text.index("钓鱼")
    assert timeline_text.index("钓鱼") < min(
        index
        for keyword in ("酒店", "酒廊")
        if (index := timeline_text.find(keyword)) >= 0
    )
    assert result.planning_warnings
    assert any(
        keyword in " ".join(result.planning_warnings)
        for keyword in ("偏赶", "冲突", "备选", "二选一")
    )


def test_task_driven_run_emits_planner_router_and_composer_stages():
    events = []

    _planner().run(QUERY, event_callback=events.append)

    stages = {event.stage for event in events}
    assert {
        "task_decomposition",
        "tool_routing",
        "tool_execution",
        "itinerary_composing",
        "food_order_mock",
        "task_poi_search",
        "multistep_itinerary_building",
    } <= stages


def test_legacy_demo_still_returns_activity_restaurant_and_actions():
    result = _planner().run(LEGACY_QUERY)

    assert result.task_plan is not None
    assert [task.task_type for task in result.task_plan.tasks] == [
        "poi_search",
        "restaurant_search",
    ]
    assert any(stop.type == "activity" for stop in result.route.stops)
    assert any(stop.type == "restaurant" for stop in result.route.stops)
    assert any(action.type == "reservation" for action in result.actions)
    assert any(action.type == "send_message" for action in result.actions)
