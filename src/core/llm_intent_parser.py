"""DeepSeek-assisted intent parsing with the rule parser as the source of truth."""

import json

from pydantic import ValidationError

from src.core.intent_parser import parse_intent
from src.providers.deepseek_provider import DeepSeekProvider
from src.schemas.models import PreferenceProfile, UserIntent


SYSTEM_PROMPT = """你是本地生活短时规划 Agent 的意图解析器。
只返回一个 JSON object，不要 Markdown，不要输出思维链。
public_reasoning 只能是简短、可展示的判断依据，不得包含隐藏推理过程。
必须使用这些字段：
raw_query, scene, time_window, duration_hours, companions, party_size,
child_age, gender_mix, distance_preference, activity_preferences,
diet_preferences, budget_preference, avoid, weather_constraint, city,
public_reasoning。
scene 只能是 family/friends/couple/solo。
duration_hours 必须是两个数字组成的数组，例如 [3, 4]。
distance_preference 只能是 nearby/normal/flexible。
budget_preference 只能是 not_expensive/normal/flexible。
不确定的可空字段使用 null，列表字段使用 []。"""


def parse_intent_with_llm(
    query: str,
    profile: PreferenceProfile,
    provider: DeepSeekProvider,
) -> tuple[UserIntent, bool, str | None]:
    """Use validated LLM fields when possible, otherwise return rule output."""
    fallback = parse_intent(query)
    if not provider.is_available:
        return fallback, False, provider.unavailable_reason

    prompt = json.dumps(
        {
            "query": query,
            "preference": profile.preference.model_dump(mode="json"),
            "weights": profile.weights.model_dump(mode="json"),
            "rule_parser_baseline": fallback.model_dump(mode="json"),
        },
        ensure_ascii=False,
    )
    payload = provider.chat_json(SYSTEM_PROMPT, prompt, "UserIntent")
    if payload is None:
        return fallback, False, provider.last_error

    merged = fallback.model_dump(mode="python")
    merged.update(payload)
    merged["raw_query"] = query
    merged["tasks"] = fallback.model_dump(mode="python")["tasks"]
    merged["time_windows"] = fallback.time_windows
    merged["duration_hours"] = _normalize_duration(
        merged.get("duration_hours"),
        fallback.duration_hours,
    )
    try:
        return UserIntent.model_validate(merged), True, None
    except ValidationError as exc:
        return fallback, False, f"DeepSeek intent schema 校验失败: {exc}"


def _normalize_duration(value, fallback: list[float]) -> list[float]:
    if isinstance(value, (int, float)):
        return [float(value), float(value)]
    if isinstance(value, list) and len(value) == 2:
        return value
    return fallback
