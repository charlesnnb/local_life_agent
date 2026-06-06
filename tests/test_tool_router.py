"""Task-to-tool dispatch and task-specific AMap query coverage."""

from src.core.intent_parser import parse_intent
from src.core.llm_task_planner import plan_tasks
from src.core.tool_router import ToolRouter
from src.providers.deepseek_provider import DeepSeekProvider
from src.services.location_service import resolve_location
from src.services.preference_service import get_current_profile


QUERY = (
    "今天工作完特别累，中午给我点个汉堡，下午出去玩蹦床，"
    "找个可以钓鱼的地方，晚上去高档酒店"
)


class RecordingAmap:
    enabled = True
    is_available = True
    last_error = None
    unavailable_reason = None

    def __init__(self):
        self.queries: list[str] = []

    def search_poi(self, keywords, city=None, location=None):
        self.queries.append(keywords)
        return [
            {
                "id": f"amap_{len(self.queries)}",
                "name": f"{keywords}候选地点",
                "address": city or "上海",
                "lat": 31.2 + len(self.queries) / 1000,
                "lng": 121.4 + len(self.queries) / 1000,
                "type": keywords,
                "rating": 4.5,
                "source": "amap",
            }
        ]


def _task_plan():
    intent = parse_intent(QUERY)
    plan, _, _ = plan_tasks(
        QUERY,
        intent,
        get_current_profile(),
        DeepSeekProvider(enabled=False),
    )
    intent.tasks = plan.tasks
    intent.time_windows = plan.time_windows
    return intent, plan


def test_router_executes_delivery_without_creating_route_place():
    intent, plan = _task_plan()
    amap = RecordingAmap()

    results = ToolRouter(amap_provider=amap).execute(
        plan.tasks,
        intent,
        resolve_location(intent),
    )

    food_task = plan.tasks[0]
    food_result = results[0]
    assert food_task.task_type == "food_delivery"
    assert food_task.route_needed is False
    assert food_result.status == "success"
    assert food_result.tool_name == "food_order_tool"
    assert food_result.selected_result["type"] == "food_order"
    assert "lat" not in food_result.selected_result


def test_router_searches_each_offline_task_with_task_specific_keywords():
    intent, plan = _task_plan()
    amap = RecordingAmap()

    results = ToolRouter(amap_provider=amap).execute(
        plan.tasks,
        intent,
        resolve_location(intent),
    )

    assert len(results) == 4
    assert all(result.status == "success" for result in results)
    assert any("蹦床" in query for query in amap.queries)
    assert any(
        keyword in query
        for query in amap.queries
        for keyword in ("钓鱼", "垂钓")
    )
    assert any(
        keyword in query
        for query in amap.queries
        for keyword in ("高档酒店", "五星级酒店", "酒店酒廊")
    )
    assert [
        result.task_id for result in results
    ] == [task.task_id for task in plan.tasks]
    assert all(
        result.selected_result
        for task, result in zip(plan.tasks[1:], results[1:], strict=True)
        if task.route_needed
    )


def test_router_preserves_failed_task_in_result():
    intent, plan = _task_plan()
    router = ToolRouter(amap_provider=None)
    hotel_task = plan.tasks[-1].model_copy(
        update={
            "task_type": "poi_search",
            "target": "不存在的测试地点",
            "search_query": "不存在的测试地点",
        }
    )

    result = router.execute(
        [hotel_task],
        intent,
        resolve_location(intent),
    )[0]

    assert result.task_id == hotel_task.task_id
    assert result.status == "failed"
    assert result.selected_result is None
    assert result.message
