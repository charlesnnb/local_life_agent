"""Task-aware candidate validation and ranking coverage."""

from src.core.intent_parser import parse_intent
from src.core.task_ranker import rank_task_candidates
from src.core.tool_router import ToolRouter
from src.schemas.models import PlannedTask
from src.services.location_service import resolve_location
from src.services.preference_service import get_current_profile


def _task(
    target: str,
    task_type: str = "poi_search",
    search_query: str | None = None,
) -> PlannedTask:
    return PlannedTask(
        task_id="task_1",
        time_window="下午",
        task_type=task_type,
        target=target,
        search_query=search_query or target,
        tool_name="amap_poi_tool",
        route_needed=True,
        description=f"找一个{target}地点",
    )


def _candidate(
    candidate_id: str,
    name: str,
    poi_type: str,
    rating: float = 4.5,
    **extra,
) -> dict:
    return {
        "id": candidate_id,
        "name": name,
        "type": poi_type,
        "lat": 31.2,
        "lng": 121.4,
        "rating": rating,
        "wait_time_min": 10,
        "price": 80,
        "source": "amap",
        **extra,
    }


def test_climbing_rejects_parent_child_swimming_club():
    task = _task("爬山", search_query="爬山 适合儿童 亲子")
    candidates = [
        _candidate(
            "swim",
            "龙格亲子游泳俱乐部",
            "体育休闲服务;运动场馆;游泳馆",
            rating=4.9,
            child_friendly=True,
        ),
        _candidate(
            "mountain",
            "佘山国家森林公园",
            "风景名胜;公园广场;森林公园",
            rating=4.5,
        ),
    ]

    result = rank_task_candidates(
        task,
        candidates,
        parse_intent("下午带孩子爬山，孩子5岁"),
        get_current_profile(),
    )

    assert result.selected_candidate["name"] == "佘山国家森林公园"
    rejected = {item["name"]: item["reason"] for item in result.rejected_candidates}
    assert "龙格亲子游泳俱乐部" in rejected
    assert "游泳" in rejected["龙格亲子游泳俱乐部"]


def test_climbing_prefers_mountain_park_forest_and_trail_candidates():
    task = _task("登山")
    candidates = [
        _candidate("mall", "环球港购物中心", "购物服务;商场"),
        _candidate("park", "辰山植物园登山步道", "公园;自然风景;户外"),
        _candidate("forest", "佘山国家森林公园", "森林公园;风景区"),
    ]

    result = rank_task_candidates(
        task,
        candidates,
        parse_intent("下午去登山"),
        get_current_profile(),
    )

    assert result.selected_candidate["id"] in {"park", "forest"}
    assert all(
        item["id"] != "mall"
        for item in result.ranked_candidates
    )


def test_regular_bar_prefers_pub_over_hotel_lobby_bar():
    task = _task("酒吧", "bar_visit", "酒吧 清吧 小酒馆")
    candidates = [
        _candidate(
            "lobby",
            "上海建国宾馆-大堂吧",
            "体育休闲服务;娱乐场所;酒吧",
            rating=4.9,
        ),
        _candidate(
            "pub",
            "衡山路静谧小酒馆",
            "体育休闲服务;酒吧;清吧",
            rating=4.6,
        ),
    ]

    result = rank_task_candidates(
        task,
        candidates,
        parse_intent("晚上去酒吧之类的"),
        get_current_profile(),
    )

    assert result.selected_candidate["id"] == "pub"
    lobby = next(item for item in result.ranked_candidates if item["id"] == "lobby")
    assert lobby["score_components"]["task_relevance"] < 1


def test_bar_search_collects_clear_bar_query_before_ranking():
    intent = parse_intent("晚上去酒吧之类的")
    task = _task("酒吧", "bar_visit", "酒吧 清吧 小酒馆")

    class QueryAwareAmap:
        enabled = True
        is_available = True
        last_error = None
        unavailable_reason = None

        def __init__(self):
            self.queries = []

        def search_poi(self, keywords, city=None, location=None):
            self.queries.append(keywords)
            if keywords == "酒吧":
                return [
                    _candidate(
                        f"lobby_{index}",
                        f"测试宾馆{index}-大堂吧",
                        "体育休闲服务;娱乐场所;酒吧",
                    )
                    for index in range(10)
                ]
            if keywords == "清吧":
                return [
                    _candidate(
                        "clear_bar",
                        "梧桐里清吧",
                        "体育休闲服务;娱乐场所;清吧",
                    )
                ]
            return []

    amap = QueryAwareAmap()
    result = ToolRouter(amap).execute(
        [task],
        intent,
        resolve_location(intent),
        profile=get_current_profile(),
    )[0]

    assert "清吧" in amap.queries
    assert result.selected_result["id"] == "amap_clear_bar"


def test_luxury_hotel_accepts_lobby_bar_and_lounge():
    task = _task(
        "高档酒店",
        "hotel_search",
        "高档酒店 五星级酒店 酒店酒廊",
    )
    candidates = [
        _candidate(
            "lounge",
            "浦东香格里拉大堂酒廊",
            "五星级宾馆;酒店酒廊;lounge",
        )
    ]

    result = rank_task_candidates(
        task,
        candidates,
        parse_intent("晚上去高档酒店酒廊"),
        get_current_profile(),
    )

    assert result.selected_candidate["id"] == "lounge"
    assert result.rejected_candidates == []


def test_router_returns_no_relevant_result_instead_of_first_candidate():
    intent = parse_intent("下午去爬山")
    task = _task("爬山", search_query="爬山")
    events = []

    class IrrelevantAmap:
        enabled = True
        is_available = True
        last_error = None
        unavailable_reason = None

        def search_poi(self, keywords, city=None, location=None):
            return [
                _candidate(
                    "swim",
                    "龙格亲子游泳俱乐部",
                    "运动场馆;游泳馆",
                ),
                _candidate("mall", "附近购物中心", "购物服务;商场"),
            ]

    result = ToolRouter(IrrelevantAmap()).execute(
        [task],
        intent,
        resolve_location(intent),
        event_callback=events.append,
        profile=get_current_profile(),
    )[0]

    assert result.status == "failed"
    assert result.selected_result is None
    assert result.message == "no_relevant_result"
    assert {item["name"] for item in result.rejected_candidates} == {
        "龙格亲子游泳俱乐部",
        "附近购物中心",
    }
    search_event = next(
        event
        for event in reversed(events)
        if event.stage == "task_poi_search"
    )
    assert search_event.source == "amap"
    assert search_event.data["rejected_candidates"]
    assert "游泳" in search_event.data["rejected_candidates"][0]["reason"]
