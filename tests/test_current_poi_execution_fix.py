"""Regression coverage for task-category-aware POI execution."""

import importlib
import importlib.util

from src.agents.planner_agent import PlannerAgent
from src.core.intent_parser import parse_intent
from src.core.llm_task_planner import build_rule_task_plan
from src.core.result_validator import validate_candidate
from src.providers.amap_provider import AmapProvider
from src.providers.deepseek_provider import DeepSeekProvider
from src.schemas.models import PlannedTask


FULL_DAY_QUERY = (
    "今天早上想去公园玩，然后中午点个外卖吃肯德基，"
    "下午去打台球，晚上去喝茶，夜宵吃个刘大妈螺狮粉吧"
)


def _task(target: str, search_query: str | None = None) -> PlannedTask:
    return PlannedTask(
        task_id="task_1",
        time_window="下午",
        task_type="poi_search",
        target=target,
        search_query=search_query or target,
        tool_name="amap_poi_tool",
        route_needed=True,
        description=f"去{target}",
    )


def _candidate(candidate_id: str, name: str, poi_type: str = "") -> dict:
    return {
        "id": candidate_id,
        "name": name,
        "type": poi_type,
        "lat": 31.2,
        "lng": 121.4,
        "rating": 4.5,
        "source": "amap",
    }


def test_task_category_normalizes_supported_place_intents():
    assert importlib.util.find_spec("src.core.task_category") is not None
    module = importlib.import_module("src.core.task_category")
    normalize_task_category = module.normalize_task_category

    assert normalize_task_category(_task("打台球")) == "billiards"
    assert normalize_task_category(_task("喝茶")) == "tea_house"
    assert normalize_task_category(_task("公园")) == "park"
    assert normalize_task_category(_task("爬山")) == "mountain_hiking"
    assert normalize_task_category(_task("咖啡店")) == "cafe"


def test_billiards_candidates_are_relevant():
    names = [
        "新九球会台球俱乐部",
        "king台球棋牌俱乐部",
        "银怡桌球牌艺",
        "康溪台球",
        "貘鱼台球凯旋店",
        "幻境宇宙桌球俱乐部",
        "谈小娱24h自助台球",
        "V8台球俱乐部",
    ]

    for index, name in enumerate(names):
        validation = validate_candidate(
            _candidate(f"billiards_{index}", name),
            _task("打台球"),
        )
        assert validation.is_relevant, name
        assert validation.matched_terms
        assert validation.negative_terms == []
        assert validation.reasons


def test_tea_candidates_are_relevant():
    names = [
        "棋乐坊棋牌茶室",
        "木寸野集茶客厅",
        "裕蘭茶楼",
        "君安·棋牌·茶馆",
    ]

    for index, name in enumerate(names):
        validation = validate_candidate(
            _candidate(f"tea_{index}", name),
            _task("喝茶"),
        )
        assert validation.is_relevant, name
        assert validation.matched_terms


def test_park_candidates_are_relevant():
    names = [
        "乐山小花园",
        "徐家汇体育公园",
        "某某绿地",
        "滨江步道",
    ]

    for index, name in enumerate(names):
        validation = validate_candidate(
            _candidate(f"park_{index}", name),
            _task("公园"),
        )
        assert validation.is_relevant, name
        assert validation.matched_terms


def test_category_negative_terms_reject_wrong_place_types():
    validation = validate_candidate(
        _candidate(
            "swimming",
            "亲子游泳馆",
            "体育休闲服务;游泳馆",
        ),
        _task("爬山"),
    )

    assert validation.is_relevant is False
    assert "游泳" in validation.negative_terms
    assert validation.reasons


def test_tea_route_label_not_bar():
    result = _planner().run("晚上去喝茶")

    assert len(result.route.stops) == 1
    assert result.route.stops[0].label in {"茶馆", "喝茶", "茶室"}
    assert result.route.stops[0].label != "酒吧"
    assert "酒吧" not in result.natural_language


def test_full_day_case():
    events = []

    result = _planner().run(FULL_DAY_QUERY, event_callback=events.append)

    assert result.task_plan is not None
    assert [
        (task.time_window, task.task_type, task.target)
        for task in result.task_plan.tasks
    ] == [
        ("早上", "poi_search", "公园"),
        ("中午", "food_delivery", "肯德基"),
        ("下午", "poi_search", "打台球"),
        ("晚上", "poi_search", "喝茶"),
        ("夜宵", "food_delivery", "刘大妈螺狮粉"),
    ]

    assert [stop.label for stop in result.route.stops] == [
        "公园",
        "台球",
        "茶馆",
    ]
    route_text = " ".join(stop.name for stop in result.route.stops)
    assert "肯德基" not in route_text
    assert "螺狮粉" not in route_text

    timeline_text = " ".join(
        f"{item.time} {item.title} {item.description}"
        for item in result.timeline.items
    )
    assert timeline_text.index("公园") < timeline_text.index("肯德基")
    assert timeline_text.index("肯德基") < timeline_text.index("台球")
    assert timeline_text.index("台球") < timeline_text.index("茶")
    assert timeline_text.index("茶") < timeline_text.index("螺狮粉")
    assert _has_unexplained_timeline_gap(result) is False

    message = next(
        action.message
        for action in result.actions
        if action.type == "send_message"
    )
    assert "喝茶" in (message or "")
    assert "酒吧" not in (message or "")
    assert "酒吧" not in result.natural_language

    selection_events = [
        event for event in events if event.data.get("selected_result")
    ]
    rejection_events = [
        event for event in events if event.data.get("rejected_candidates")
    ]
    assert selection_events
    assert rejection_events
    for event in selection_events:
        selected = event.data["selected_result"]
        assert selected["matched_terms"]
        assert selected["negative_terms"] == []
        assert selected["reasons"]
    assert all(
        not event.data.get("rejected_candidates")
        for event in selection_events
    )
    assert all(
        not event.data.get("selected_result")
        for event in rejection_events
    )


def test_full_day_case_uses_category_rules_in_local_fallback():
    result = PlannerAgent(
        deepseek_provider=DeepSeekProvider(enabled=False),
        amap_provider=AmapProvider(enabled=False),
    ).run(FULL_DAY_QUERY)

    assert [stop.label for stop in result.route.stops] == [
        "公园",
        "台球",
        "茶馆",
    ]
    assert not any(
        "台球" in warning or "喝茶" in warning
        for warning in result.planning_warnings
    )


class CurrentPoiAmap:
    enabled = True
    is_available = True
    last_error = None
    unavailable_reason = None

    def search_poi(self, keywords, city=None, location=None):
        if any(word in keywords for word in ("台球", "桌球", "九球")):
            return [
                _candidate("billiards", "V8台球俱乐部", "台球;桌球"),
                _candidate("billiards_wrong", "游泳健身中心", "游泳;健身"),
            ]
        if any(word in keywords for word in ("茶馆", "茶室", "茶楼", "喝茶")):
            return [
                _candidate("tea", "木寸野集茶客厅", "茶馆;茶室"),
                _candidate("tea_wrong", "潮流酒吧", "酒吧;夜店"),
            ]
        if any(word in keywords for word in ("公园", "花园", "绿地", "步道")):
            return [
                _candidate("park", "乐山小花园", "公园;绿地"),
                _candidate("park_wrong", "公园路购物中心", "商场"),
            ]
        return []

    def route_duration(self, *_args, **_kwargs):
        return None


def _planner() -> PlannerAgent:
    return PlannerAgent(
        deepseek_provider=DeepSeekProvider(enabled=False),
        amap_provider=CurrentPoiAmap(),
    )


def _has_unexplained_timeline_gap(result) -> bool:
    items = sorted(
        result.timeline.items,
        key=lambda item: int(item.time[:2]) * 60 + int(item.time[3:]),
    )
    for earlier, later in zip(items, items[1:], strict=False):
        earlier_time = int(earlier.time[:2]) * 60 + int(earlier.time[3:])
        later_time = int(later.time[:2]) * 60 + int(later.time[3:])
        if later_time - earlier_time <= 45:
            continue
        if earlier.type == "free_time" or later.type == "free_time":
            continue
        if "安排约" in earlier.description:
            continue
        return True
    return False
