"""Explain an already-made decision without allowing new candidates."""

import json
import re

from pydantic import ValidationError

from src.providers.deepseek_provider import DeepSeekProvider
from src.schemas.models import (
    DecisionExplanation,
    PreferenceProfile,
    RejectedReason,
    RouteEstimate,
    UserIntent,
)
from src.services.preference_service import build_preference_explanation


SYSTEM_PROMPT = """你是本地活动方案的决策解释器。
只返回 JSON object，不要 Markdown，不要思维链。
只能引用输入候选地点中的 name，禁止编造新地点。
字段必须是 selected_reasons, rejected_reasons,
preference_explanation, public_reasoning。
rejected_reasons 每项包含 name 和 reason。
所有文字必须是面向用户可展示的简短解释。"""


def explain_decision(
    intent: UserIntent,
    profile: PreferenceProfile,
    poi_candidates: list[dict],
    restaurant_candidates: list[dict],
    selected_poi: dict,
    selected_restaurant: dict,
    route_estimates: dict[str, RouteEstimate],
    provider: DeepSeekProvider,
) -> tuple[DecisionExplanation, bool, str | None]:
    fallback = build_rule_explanation(
        intent,
        profile,
        poi_candidates,
        restaurant_candidates,
        selected_poi,
        selected_restaurant,
        route_estimates,
    )
    if not provider.is_available:
        return fallback, False, provider.unavailable_reason

    prompt = json.dumps(
        {
            "intent": intent.model_dump(mode="json"),
            "preference": profile.preference.model_dump(mode="json"),
            "weights": profile.weights.model_dump(mode="json"),
            "poi_candidates": _compact_candidates(poi_candidates),
            "restaurant_candidates": _compact_candidates(
                restaurant_candidates
            ),
            "selected_poi": _compact_candidate(selected_poi),
            "selected_restaurant": _compact_candidate(selected_restaurant),
            "route_estimates": {
                key: value.model_dump(mode="json")
                for key, value in route_estimates.items()
            },
        },
        ensure_ascii=False,
    )
    payload = provider.chat_json(
        SYSTEM_PROMPT,
        prompt,
        "DecisionExplanation",
    )
    if payload is None:
        return fallback, False, provider.last_error
    payload = _normalize_payload(payload)
    try:
        explanation = DecisionExplanation.model_validate(payload)
    except ValidationError as exc:
        return fallback, False, f"DeepSeek explanation schema 校验失败: {exc}"

    allowed_names = {
        item["name"]
        for item in poi_candidates + restaurant_candidates
        if item.get("name")
    }
    if any(
        item.name not in allowed_names
        for item in explanation.rejected_reasons
    ):
        return fallback, False, "DeepSeek explanation 引用了候选集外地点"
    selected_names = {selected_poi["name"], selected_restaurant["name"]}
    if any(
        _references_unknown_selected_place(reason, selected_names)
        for reason in explanation.selected_reasons
    ):
        return fallback, False, "DeepSeek explanation 疑似选择了候选集外地点"
    return explanation, True, None


def _normalize_payload(payload: dict) -> dict:
    normalized = dict(payload)
    for field in ("selected_reasons", "preference_explanation"):
        if isinstance(normalized.get(field), str):
            normalized[field] = [normalized[field]]
    if isinstance(normalized.get("rejected_reasons"), dict):
        normalized["rejected_reasons"] = [normalized["rejected_reasons"]]
    return normalized


def _references_unknown_selected_place(
    reason: str,
    selected_names: set[str],
) -> bool:
    for match in re.finditer(r"(?:选择|推荐)([^，。；]{2,30})", reason):
        phrase = match.group(1)
        if phrase.startswith(("这个", "该", "它")):
            continue
        if not any(name in phrase or phrase in name for name in selected_names):
            return True
    return False


def build_rule_explanation(
    intent: UserIntent,
    profile: PreferenceProfile,
    poi_candidates: list[dict],
    restaurant_candidates: list[dict],
    selected_poi: dict,
    selected_restaurant: dict,
    route_estimates: dict[str, RouteEstimate],
) -> DecisionExplanation:
    selected_reasons = [
        (
            f"选择{selected_poi['name']}，因为它匹配活动偏好，"
            f"通勤约 {route_estimates[selected_poi['id']].duration_min} 分钟。"
        ),
        (
            f"选择{selected_restaurant['name']}，因为它更符合餐饮、"
            "同行人和等待时间要求。"
        ),
    ]
    rejected = []
    for item in (poi_candidates[1:3] + restaurant_candidates[1:3]):
        if item["name"] in {
            selected_poi["name"],
            selected_restaurant["name"],
        }:
            continue
        reason = "综合距离、偏好匹配度和等待时间后排序较低。"
        rejected.append(RejectedReason(name=item["name"], reason=reason))
    return DecisionExplanation(
        selected_reasons=selected_reasons,
        rejected_reasons=rejected,
        preference_explanation=build_preference_explanation(
            profile.preference
        ),
        public_reasoning=(
            "已综合距离、同行人适配、餐饮需求、等待时间和路线顺畅度。"
        ),
    )


def _compact_candidates(candidates: list[dict]) -> list[dict]:
    return [_compact_candidate(item) for item in candidates[:6]]


def _compact_candidate(candidate: dict) -> dict:
    fields = (
        "id",
        "name",
        "source",
        "tags",
        "rating",
        "wait_time_min",
        "score",
        "score_components",
        "ranking_reasons",
    )
    return {key: candidate.get(key) for key in fields if key in candidate}
