"""Build search keywords without allowing the LLM to choose final places."""

import json

from pydantic import ValidationError

from src.providers.deepseek_provider import DeepSeekProvider
from src.schemas.models import PreferenceProfile, QueryPlan, UserIntent


SYSTEM_PROMPT = """你是本地生活搜索词规划器。
只返回 JSON object，不要 Markdown，不要思维链。
你只能生成搜索关键词，不能生成、推荐或编造具体地点名称。
字段必须是 poi_queries, restaurant_queries, route_mode,
max_travel_minutes, public_reasoning。
route_mode 只能是 driving 或 walking。
public_reasoning 是一句可向用户展示的简短依据。"""


def build_query_plan(
    intent: UserIntent,
    profile: PreferenceProfile,
    provider: DeepSeekProvider,
) -> tuple[QueryPlan, bool, str | None]:
    fallback = build_fallback_query_plan(intent, profile)
    if not provider.is_available:
        return fallback, False, provider.unavailable_reason

    prompt = json.dumps(
        {
            "intent": intent.model_dump(mode="json"),
            "preference": profile.preference.model_dump(mode="json"),
            "weights": profile.weights.model_dump(mode="json"),
        },
        ensure_ascii=False,
    )
    payload = provider.chat_json(SYSTEM_PROMPT, prompt, "QueryPlan")
    if payload is None:
        return fallback, False, provider.last_error
    try:
        query_plan = QueryPlan.model_validate(payload)
    except ValidationError as exc:
        return fallback, False, f"DeepSeek query plan schema 校验失败: {exc}"
    if _contains_place_like_name(query_plan):
        return fallback, False, "DeepSeek query plan 包含疑似具体地点，已拒绝"
    return query_plan, True, None


def build_fallback_query_plan(
    intent: UserIntent,
    profile: PreferenceProfile,
) -> QueryPlan:
    poi_queries = list(profile.preference.activity_types)
    if intent.scene == "family":
        poi_queries.extend(["亲子乐园", "儿童乐园", "亲子展览"])
    if "室内" in intent.activity_preferences:
        poi_queries.append("室内活动")
    if {"散步", "拍照"} & set(intent.activity_preferences):
        poi_queries.append("Citywalk")
    if not poi_queries:
        poi_queries = ["休闲活动", "展览"]

    restaurant_queries = list(profile.preference.dining_preferences)
    if {"减脂", "清淡", "低油"} & set(intent.diet_preferences):
        restaurant_queries.extend(["轻食", "健康餐", "清淡餐厅"])
    if intent.child_age is not None:
        restaurant_queries.append("儿童友好餐厅")
    if not restaurant_queries:
        restaurant_queries = ["附近餐厅"]

    return QueryPlan(
        poi_queries=_unique(poi_queries)[:8],
        restaurant_queries=_unique(restaurant_queries)[:8],
        route_mode="driving",
        max_travel_minutes=profile.preference.max_travel_minutes,
        public_reasoning=(
            "根据本次需求和问卷偏好生成活动、餐厅搜索词，并限制通勤范围。"
        ),
    )


def _contains_place_like_name(query_plan: QueryPlan) -> bool:
    forbidden_suffixes = ("店", "馆", "中心", "公园", "广场", "乐园")
    all_queries = query_plan.poi_queries + query_plan.restaurant_queries
    return any(
        len(query) > 14 and query.endswith(forbidden_suffixes)
        for query in all_queries
    )


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item.strip() for item in items if item.strip()))
