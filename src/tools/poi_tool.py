"""Task-driven place search using AMap with local deterministic fallback."""

import re

from src.core.result_validator import validate_candidate
from src.config.settings import current_demo_scenario, load_json
from src.providers.amap_provider import AmapProvider
from src.providers.local_commerce_provider import enrich_activity
from src.schemas.models import PlannedTask, ResolvedLocation, UserIntent


MOCK_WAIT_MINUTES = {
    "poi_001": 12,
    "poi_002": 8,
    "poi_003": 18,
    "poi_004": 2,
    "poi_005": 15,
    "poi_006": 5,
    "poi_007": 20,
    "poi_008": 10,
    "poi_009": 8,
    "poi_010": 6,
    "poi_011": 5,
    "poi_012": 8,
    "poi_013": 6,
    "poi_014": 5,
    "poi_015": 5,
    "poi_016": 4,
    "poi_017": 8,
    "poi_018": 6,
    "poi_019": 7,
}

TASK_QUERIES = {
    "公园": ["公园", "小花园", "绿地", "体育公园", "滨江步道"],
    "打台球": ["台球", "桌球", "九球", "台球俱乐部", "自助台球"],
    "台球": ["台球", "桌球", "九球", "台球俱乐部", "自助台球"],
    "喝茶": ["茶馆", "茶室", "茶楼", "茶客厅", "茗茶"],
    "茶馆": ["茶馆", "茶室", "茶楼", "茶客厅", "茗茶"],
    "爬山": ["爬山", "登山", "森林公园", "郊野公园", "登山步道"],
    "登山": ["登山", "爬山", "森林公园", "郊野公园", "登山步道"],
    "钓鱼": ["钓鱼", "钓鱼场", "垂钓"],
    "蹦床": ["蹦床馆", "蹦床", "室内蹦床"],
    "酒吧": ["酒吧", "清吧", "小酒馆"],
    "高档酒店": ["高档酒店", "五星级酒店", "酒店酒廊"],
    "酒店酒廊": ["酒店酒廊", "五星级酒店", "高档酒店"],
}


def search_pois(
    intent: UserIntent,
    location: ResolvedLocation,
    queries: list[str] | None = None,
    amap_provider: AmapProvider | None = None,
) -> list[dict]:
    """Return normalized real places, or deterministic local mock candidates."""
    if amap_provider and amap_provider.is_available:
        real_candidates = _search_amap(
            intent,
            location,
            queries or intent.activity_preferences or ["休闲活动"],
            amap_provider,
        )
        if real_candidates:
            return real_candidates
    return _search_mock(intent, location)


def search_task_pois(
    intent: UserIntent,
    location: ResolvedLocation,
    task: PlannedTask,
    amap_provider: AmapProvider | None = None,
) -> list[dict]:
    """Search POIs for one offline task with deterministic local fallback."""
    queries = _task_queries(task)
    if amap_provider and amap_provider.is_available:
        candidates = _search_amap(
            intent,
            location,
            queries,
            amap_provider,
        )
        if candidates:
            return candidates
    return _search_task_mock(intent, location, task)


def _search_amap(
    intent: UserIntent,
    location: ResolvedLocation,
    queries: list[str],
    provider: AmapProvider,
) -> list[dict]:
    candidates: list[dict] = []
    seen: set[str] = set()
    per_query_limit = 4 if len(queries) > 1 else 8
    total_limit = 20
    for query in queries[:5]:
        query_count = 0
        for place in provider.search_poi(
            query,
            city=location.city,
            location=(location.lat, location.lng),
        ):
            if not place.get("id") or place["id"] in seen:
                continue
            seen.add(place["id"])
            candidate = enrich_activity(place, intent, query)
            candidates.append(candidate)
            query_count += 1
            if len(candidates) >= total_limit:
                return candidates
            if query_count >= per_query_limit:
                break
    return candidates


def _search_mock(
    intent: UserIntent,
    location: ResolvedLocation,
) -> list[dict]:
    candidates = []
    for poi in load_json("pois.json").get("pois", []):
        if intent.scene not in poi.get("suitable_scenes", []):
            continue

        if intent.child_age is not None:
            min_age, max_age = poi.get("age_range", [0, 99])
            if not min_age <= intent.child_age <= max_age:
                continue

        candidate = dict(poi)
        candidate["id"] = poi["poi_id"]
        candidate["address"] = f"{location.city}{poi.get('district', '')}"
        candidate["wait_time_min"] = MOCK_WAIT_MINUTES.get(poi["poi_id"], 10)
        candidate["source"] = "mock"
        candidate["child_friendly"] = bool(
            {"kids", "family", "playground"} & set(poi.get("tags", []))
        )
        candidates.append(candidate)
    return candidates


def _search_task_mock(
    intent: UserIntent,
    location: ResolvedLocation,
    task: PlannedTask,
) -> list[dict]:
    candidates = []
    allow_scene_fallback = (
        current_demo_scenario() == "activity_unavailable"
    )
    for poi in load_json("pois.json").get("pois", []):
        if (
            task.task_type != "bar_visit"
            and intent.scene not in poi.get("suitable_scenes", [])
            and not allow_scene_fallback
        ):
            continue
        if not _matches_task(poi, task):
            continue
        candidate = dict(poi)
        candidate["id"] = poi["poi_id"]
        candidate["address"] = f"{location.city}{poi.get('district', '')}"
        candidate["wait_time_min"] = MOCK_WAIT_MINUTES.get(
            poi["poi_id"],
            10,
        )
        candidate["source"] = "mock"
        candidate["child_friendly"] = bool(
            {"kids", "family", "playground"} & set(poi.get("tags", []))
        )
        candidates.append(candidate)
    return candidates


def _matches_task(poi: dict, task: PlannedTask) -> bool:
    target = (task.target or "").lower()
    if target in {"休闲活动", "亲子活动"}:
        return True
    return validate_candidate(poi, task).is_relevant


def _task_queries(task: PlannedTask) -> list[str]:
    explicit = [
        item.strip()
        for item in re.split(r"[/|、，,]+|\s+", task.search_query or "")
        if item.strip()
    ]
    defaults = TASK_QUERIES.get(task.target or "", [])
    queries = list(dict.fromkeys([*explicit, *defaults]))
    return queries or [task.target or task.description]
