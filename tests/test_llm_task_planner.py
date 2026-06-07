"""DeepSeek-first ordered task planning and deterministic fallback coverage."""

import json

import httpx

from src.core.intent_parser import parse_intent
from src.core.llm_task_planner import plan_tasks
from src.providers.deepseek_provider import DeepSeekProvider
from src.services.preference_service import get_current_profile


QUERY = (
    "今天工作完特别累，中午给我点个汉堡，下午出去玩蹦床，"
    "找个可以钓鱼的地方，晚上去高档酒店"
)


def _provider(handler) -> DeepSeekProvider:
    return DeepSeekProvider(
        api_key="test-key",
        enabled=True,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_rule_fallback_keeps_all_ordered_tasks():
    intent = parse_intent(QUERY)

    plan, used_llm, error = plan_tasks(
        QUERY,
        intent,
        get_current_profile(),
        DeepSeekProvider(enabled=False),
    )

    assert used_llm is False
    assert error == "DeepSeek 未启用"
    assert plan.time_windows == ["中午", "下午", "晚上"]
    assert [task.task_type for task in plan.tasks] == [
        "food_delivery",
        "poi_search",
        "poi_search",
        "hotel_search",
    ]
    assert [task.target for task in plan.tasks] == [
        "汉堡",
        "蹦床",
        "钓鱼",
        "高档酒店",
    ]
    assert plan.tasks[0].route_needed is False
    assert all(task.route_needed for task in plan.tasks[1:])
    assert plan.constraints["energy_level"] == "low"


def test_deepseek_valid_task_plan_is_primary():
    def handler(request):
        payload = json.loads(request.content)
        assert payload["response_format"] == {"type": "json_object"}
        assert "不负责编造 POI" in payload["messages"][0]["content"]
        content = {
            "scene": "personal",
            "mood": "relaxed",
            "time_windows": ["晚上"],
            "tasks": [
                {
                    "task_id": "llm_task",
                    "time_window": "晚上",
                    "task_type": "hotel_search",
                    "target": "酒店酒廊",
                    "search_query": "高档酒店 酒店酒廊",
                    "tool_name": "amap_poi_tool",
                    "route_needed": True,
                    "description": "晚上去酒店酒廊放松",
                }
            ],
            "constraints": {
                "energy_level": "normal",
                "avoid": [],
                "preference": ["放松"],
            },
        }
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": json.dumps(content, ensure_ascii=False)}}
                ]
            },
        )

    query = "晚上想去酒店酒廊放松"
    plan, used_llm, error = plan_tasks(
        query,
        parse_intent(query),
        get_current_profile(),
        _provider(handler),
    )

    assert used_llm is True
    assert error is None
    assert len(plan.tasks) == 1
    assert plan.tasks[0].task_id == "task_1"
    assert plan.tasks[0].target == "酒店酒廊"


def test_deepseek_numeric_task_ids_are_normalized_and_tasks_preserved():
    def handler(_request):
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
                    "search_query": "附近适合孩子的游乐场",
                    "tool_name": "amap_poi_tool",
                    "route_needed": True,
                    "description": "找附近适合孩子的游乐场",
                },
                {
                    "task_id": "2",
                    "time_window": "今天下午",
                    "task_type": "restaurant_search",
                    "target": "川菜",
                    "search_query": "附近川菜馆",
                    "tool_name": "restaurant_tool",
                    "route_needed": True,
                    "description": "找附近的川菜馆",
                },
                {
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

    query = "今天下午带孩子找个游乐场，川菜，霸王茶姬，别太远"
    plan, used_llm, error = plan_tasks(
        query,
        parse_intent(query),
        get_current_profile(),
        _provider(handler),
    )

    assert used_llm is True
    assert error is None
    assert [task.task_id for task in plan.tasks] == [
        "task_1",
        "task_2",
        "task_3",
    ]
    assert [task.target for task in plan.tasks] == [
        "游乐场",
        "川菜",
        "霸王茶姬",
    ]


def test_invalid_deepseek_json_uses_rule_fallback_without_dropping_tasks():
    def handler(_request):
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "{broken"}}]},
        )

    plan, used_llm, error = plan_tasks(
        QUERY,
        parse_intent(QUERY),
        get_current_profile(),
        _provider(handler),
    )

    assert used_llm is False
    assert "非法 JSON" in (error or "")
    assert [task.target for task in plan.tasks] == [
        "汉堡",
        "蹦床",
        "钓鱼",
        "高档酒店",
    ]


def test_generic_legacy_demo_gets_task_contract_from_fallback():
    query = "今天下午想带老婆孩子出去玩几个小时，别太远，孩子5岁，老婆最近在减肥"

    plan, _, _ = plan_tasks(
        query,
        parse_intent(query),
        get_current_profile(),
        DeepSeekProvider(enabled=False),
    )

    assert [task.task_type for task in plan.tasks] == [
        "poi_search",
        "restaurant_search",
    ]
    assert plan.tasks[0].route_needed is True
    assert plan.tasks[1].tool_name == "restaurant_tool"


def test_rule_fallback_recognizes_explicit_playground_cuisine_and_brand():
    query = "今天下午带孩子找个游乐场，川菜，霸王茶姬，别太远"

    plan, used_llm, error = plan_tasks(
        query,
        parse_intent(query),
        get_current_profile(),
        DeepSeekProvider(enabled=False),
    )

    assert used_llm is False
    assert error == "DeepSeek 未启用"
    assert [task.target for task in plan.tasks] == [
        "游乐场",
        "川菜",
        "霸王茶姬",
    ]
    assert [task.task_type for task in plan.tasks] == [
        "poi_search",
        "restaurant_search",
        "poi_search",
    ]
