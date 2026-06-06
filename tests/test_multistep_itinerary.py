"""Priority 4.5 coverage for ordered multi-stage planning."""

from src.agents.planner_agent import PlannerAgent
from src.core.itinerary_builder import build_multistep_itinerary
from src.core.intent_parser import parse_intent
from src.core.task_decomposer import decompose_tasks
from src.providers.amap_provider import AmapProvider
from src.providers.deepseek_provider import DeepSeekProvider
from src.services.location_service import resolve_location
from src.tools.food_order_tool import order_food
from src.tools.message_tool import build_multistep_message
from src.tools.poi_tool import search_task_pois


QUERY = (
    "今天工作完特别累，中午给我点个麦当劳，下午出去钓鱼，"
    "找个可以钓鱼的地方，晚上去酒吧"
)


def _planner() -> PlannerAgent:
    return PlannerAgent(
        deepseek_provider=DeepSeekProvider(enabled=False),
        amap_provider=AmapProvider(enabled=False),
    )


def test_decomposer_preserves_ordered_multistage_tasks():
    intent = parse_intent(QUERY)

    tasks = decompose_tasks(QUERY, intent)

    assert [task.task_type for task in tasks] == [
        "food_order",
        "activity_search",
        "bar_visit",
    ]
    assert [task.time_window for task in tasks] == ["中午", "下午", "晚上"]
    assert tasks[0].target == "麦当劳"
    assert tasks[1].target == "钓鱼"
    assert tasks[2].target == "酒吧"


def test_parser_exposes_all_time_windows_and_tasks():
    intent = parse_intent(QUERY)

    assert intent.time_windows == ["中午", "下午", "晚上"]
    assert [task.task_type for task in intent.tasks] == [
        "food_order",
        "activity_search",
        "bar_visit",
    ]


def test_order_verb_keeps_food_brand_as_delivery_task():
    intent = parse_intent("中午叫一份肯德基外卖")

    assert len(intent.tasks) == 1
    assert intent.tasks[0].task_type == "food_order"
    assert intent.tasks[0].target == "肯德基"


def test_food_order_returns_mock_action():
    action = order_food("麦当劳", "中午", "默认位置：上海徐汇")

    assert action.type == "food_order"
    assert action.status == "mock_success"
    assert action.target == "麦当劳"
    assert action.details["estimated_delivery_minutes"] == 30
    assert action.details["time_window"] == "中午"


def test_multistep_builder_keeps_only_offline_tasks_in_route():
    intent = parse_intent(QUERY)

    result = build_multistep_itinerary(
        intent=intent,
        location=resolve_location(intent),
        selected_places=[
            {
                "task_id": "task_2",
                "task_type": "activity_search",
                "id": "mock_fishing_001",
                "name": "长风公园钓鱼池",
                "lat": 31.2244,
                "lng": 121.3957,
                "avg_duration_min": 120,
                "source": "mock",
            },
            {
                "task_id": "task_3",
                "task_type": "bar_visit",
                "id": "mock_bar_001",
                "name": "梧桐里清吧",
                "lat": 31.2110,
                "lng": 121.4380,
                "avg_duration_min": 120,
                "source": "mock",
            },
        ],
    )

    assert [stop.type for stop in result.route.stops] == ["activity", "bar"]
    assert all("麦当劳" not in stop.name for stop in result.route.stops)
    assert any(item.type == "food_order" for item in result.timeline.items)
    assert any(item.type == "activity" for item in result.timeline.items)
    assert any(item.type == "bar" for item in result.timeline.items)
    assert any(action.type == "food_order" for action in result.actions)


def test_multistep_builder_preserves_midday_afternoon_evening_order():
    intent = parse_intent(QUERY)

    result = build_multistep_itinerary(
        intent=intent,
        location=resolve_location(intent),
        selected_places=[
            {
                "task_id": "task_2",
                "task_type": "activity_search",
                "id": "mock_fishing_001",
                "name": "长风公园钓鱼池",
                "lat": 31.2244,
                "lng": 121.3957,
                "avg_duration_min": 120,
                "source": "mock",
            },
            {
                "task_id": "task_3",
                "task_type": "bar_visit",
                "id": "mock_bar_001",
                "name": "梧桐里清吧",
                "lat": 31.2110,
                "lng": 121.4380,
                "avg_duration_min": 120,
                "source": "mock",
            },
        ],
    )

    timeline_text = " ".join(
        f"{item.time} {item.title} {item.description}"
        for item in result.timeline.items
    )
    assert timeline_text.index("麦当劳") < timeline_text.index("钓鱼")
    assert timeline_text.index("钓鱼") < timeline_text.index("清吧")


def test_task_poi_search_has_fishing_and_bar_mock_fallbacks():
    intent = parse_intent(QUERY)
    location = resolve_location(intent)

    fishing = search_task_pois(intent, location, intent.tasks[1])
    bars = search_task_pois(intent, location, intent.tasks[2])

    assert fishing
    assert any("钓鱼" in item["name"] for item in fishing)
    assert bars
    assert any(
        keyword in item["name"]
        for item in bars
        for keyword in ("酒吧", "清吧", "小酒馆")
    )


def test_planner_returns_ordered_multistep_response():
    result = _planner().run(QUERY)

    assert [task.task_type for task in result.user_intent.tasks] == [
        "food_delivery",
        "poi_search",
        "bar_visit",
    ]
    timeline_text = " ".join(
        f"{item.time} {item.title} {item.description}"
        for item in result.timeline.items
    )
    assert timeline_text.index("麦当劳") < timeline_text.index("钓鱼")
    assert timeline_text.index("钓鱼") < timeline_text.index("清吧")
    assert any(stop.type == "activity" for stop in result.route.stops)
    assert any(stop.type == "bar" for stop in result.route.stops)
    assert all("麦当劳" not in stop.name for stop in result.route.stops)
    assert any(action.type == "food_order" for action in result.actions)


def test_solo_multistep_message_is_a_personal_note():
    result = _planner().run(QUERY)
    message = next(
        action for action in result.actions if action.type == "send_message"
    )

    assert message.target == "自己"
    assert "老婆" not in (message.message or "")
    assert "家人" not in (message.message or "")
    assert "晚上去麦当劳吃晚餐" not in result.model_dump_json()


def test_multistep_run_emits_task_specific_progress():
    events = []

    _planner().run(QUERY, event_callback=events.append)

    stages = {event.stage for event in events}
    assert {
        "task_decomposition",
        "food_order_mock",
        "task_poi_search",
        "multistep_itinerary_building",
    } <= stages


def test_multistep_message_uses_activity_step_not_transfer_step():
    intent = parse_intent("中午点麦当劳，下午出去打球，晚上去酒吧")
    itinerary = build_multistep_itinerary(
        intent=intent,
        location=resolve_location(intent),
        selected_places=[
            {
                "task_id": "task_2",
                "task_type": "activity_search",
                "id": "mock_sports_001",
                "name": "徐汇体育馆篮球场",
                "lat": 31.1820,
                "lng": 121.4370,
                "avg_duration_min": 90,
                "source": "mock",
            },
            {
                "task_id": "task_3",
                "task_type": "bar_visit",
                "id": "mock_bar_001",
                "name": "梧桐里清吧",
                "lat": 31.2110,
                "lng": 121.4380,
                "avg_duration_min": 120,
                "source": "mock",
            },
        ],
    )

    message = build_multistep_message(intent, itinerary.plan)

    assert "下午去徐汇体育馆篮球场打球放松" in message
    assert "前往打球地点放松" not in message
