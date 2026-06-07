"""End-to-end coverage for the corrected task-driven planning pipeline."""

import json

import httpx

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
RECOVERED_TASK_QUERY = "今天下午带孩子找个游乐场，川菜，霸王茶姬，别太远"


def _planner() -> PlannerAgent:
    return PlannerAgent(
        deepseek_provider=DeepSeekProvider(enabled=False),
        amap_provider=AmapProvider(enabled=False),
    )


def _deepseek_provider_for_recovered_tasks() -> DeepSeekProvider:
    def handler(request):
        payload = json.loads(request.content)
        system_prompt = payload["messages"][0]["content"]
        if "意图解析器" in system_prompt:
            content = {
                "raw_query": RECOVERED_TASK_QUERY,
                "scene": "family",
                "time_window": "今天下午",
                "duration_hours": [3, 4],
                "companions": ["孩子"],
                "party_size": 2,
                "child_age": 5,
                "gender_mix": None,
                "distance_preference": "nearby",
                "activity_preferences": ["游乐场", "亲子"],
                "diet_preferences": ["川菜"],
                "budget_preference": "normal",
                "avoid": ["太远"],
                "weather_constraint": None,
                "city": None,
                "public_reasoning": "识别出亲子游乐场、川菜和茶饮需求。",
            }
        else:
            content = {
                "scene": "family",
                "mood": "normal",
                "time_windows": ["今天下午"],
                "tasks": [
                    {
                        "task_id": 1,
                        "time_window": "今天下午",
                        "task_type": "poi_search",
                        "target": "游乐场",
                        "search_query": "亲子乐园 儿童乐园 游乐场",
                        "tool_name": "amap_poi_tool",
                        "route_needed": True,
                        "description": "找附近适合孩子的游乐场",
                    },
                    {
                        "task_id": 2,
                        "time_window": "今天下午",
                        "task_type": "restaurant_search",
                        "target": "川菜",
                        "search_query": "川菜",
                        "tool_name": "restaurant_tool",
                        "route_needed": True,
                        "description": "找附近的川菜馆",
                    },
                    {
                        "task_id": 3,
                        "time_window": "今天下午",
                        "task_type": "food_delivery",
                        "target": "霸王茶姬",
                        "search_query": "霸王茶姬",
                        "tool_name": "food_order_tool",
                        "route_needed": False,
                        "description": "点霸王茶姬外卖",
                    },
                ],
                "constraints": {"avoid": ["太远"], "preference": ["顺路"]},
            }
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": json.dumps(content, ensure_ascii=False)}}
                ]
            },
        )

    return DeepSeekProvider(
        api_key="test-key",
        enabled=True,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
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


def test_numeric_deepseek_task_ids_do_not_enter_compatibility_flow():
    result = PlannerAgent(
        deepseek_provider=_deepseek_provider_for_recovered_tasks(),
        amap_provider=AmapProvider(enabled=False),
    ).run(RECOVERED_TASK_QUERY)

    assert result.task_plan is not None
    assert [task.target for task in result.task_plan.tasks] == [
        "游乐场",
        "川菜",
        "霸王茶姬",
    ]
    assert [task.task_id for task in result.task_plan.tasks] == [
        "task_1",
        "task_2",
        "task_3",
    ]
    assert "按任务安排" in result.plan.summary
    assert "霸王茶姬" in result.model_dump_json()
    assert any(action.type == "food_order" for action in result.actions)
    assert any(stop.type == "restaurant" for stop in result.route.stops)


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
