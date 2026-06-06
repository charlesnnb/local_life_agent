"""In-memory preference profile and deterministic weight generation."""

from threading import Lock

from src.schemas.models import (
    PreferenceProfile,
    PreferenceSetup,
    PreferenceWeights,
    UserPreference,
)


PREFERENCE_OPTIONS = {
    "activity_types": [
        "亲子乐园",
        "展览",
        "Citywalk",
        "商场轻松逛",
        "户外公园",
        "酒吧/夜生活",
    ],
    "max_travel_minutes": [15, 30, 45],
    "dining_preferences": [
        "清淡健康",
        "亲子友好",
        "网红打卡",
        "性价比",
        "火锅烧烤",
    ],
    "activity_intensity": ["light", "medium", "high"],
    "budget_level": ["low", "medium", "high"],
}

_lock = Lock()
_current_preference = UserPreference()


def build_preference_weights(
    preference: UserPreference,
) -> PreferenceWeights:
    """Convert questionnaire answers into normalized ranking weights."""
    raw = {
        "distance_weight": 0.20,
        "activity_match_weight": 0.16,
        "child_friendly_weight": 0.16,
        "diet_match_weight": 0.16,
        "popularity_weight": 0.10,
        "budget_weight": 0.08,
        "indoor_weight": 0.07,
        "low_wait_weight": 0.07,
    }

    if preference.max_travel_minutes == 15:
        raw["distance_weight"] += 0.12
    elif preference.max_travel_minutes == 45:
        raw["distance_weight"] -= 0.04
        raw["popularity_weight"] += 0.04

    if preference.activity_types:
        raw["activity_match_weight"] += 0.06
    if "亲子乐园" in preference.activity_types:
        raw["child_friendly_weight"] += 0.06
    if preference.dining_preferences:
        raw["diet_match_weight"] += 0.08
    if preference.budget_level != "medium":
        raw["budget_weight"] += 0.05
    if preference.prefer_indoor:
        raw["indoor_weight"] += 0.08
    if preference.prefer_low_wait:
        raw["low_wait_weight"] += 0.06

    total = sum(raw.values())
    normalized = {
        name: round(value / total, 6)
        for name, value in raw.items()
    }
    rounding_gap = round(1.0 - sum(normalized.values()), 6)
    normalized["distance_weight"] += rounding_gap
    return PreferenceWeights(**normalized)


def get_default_setup() -> PreferenceSetup:
    preference = UserPreference()
    return PreferenceSetup(
        options=PREFERENCE_OPTIONS,
        preference=preference,
        weights=build_preference_weights(preference),
    )


def get_current_profile() -> PreferenceProfile:
    with _lock:
        preference = _current_preference.model_copy(deep=True)
    return PreferenceProfile(
        preference=preference,
        weights=build_preference_weights(preference),
    )


def save_preference(preference: UserPreference) -> PreferenceProfile:
    global _current_preference
    with _lock:
        _current_preference = preference.model_copy(deep=True)
    return get_current_profile()


def reset_current_preference() -> PreferenceProfile:
    """Restore defaults; primarily useful for deterministic tests and demos."""
    return save_preference(UserPreference())


def build_preference_explanation(
    preference: UserPreference,
) -> list[str]:
    explanations = [
        (
            "根据你的通勤偏好，优先选择"
            f"{preference.max_travel_minutes}分钟内可到达的地点"
        )
    ]
    if preference.activity_types:
        explanations.append(
            "活动偏好优先匹配：" + "、".join(preference.activity_types)
        )
    if preference.dining_preferences:
        explanations.append(
            "餐饮偏好优先匹配：" + "、".join(preference.dining_preferences)
        )
    if preference.prefer_indoor:
        explanations.append("你偏好室内活动，因此提高了室内场所排序")
    if preference.prefer_low_wait:
        explanations.append("你偏好少排队，因此降低了高等待地点的排序")
    budget_labels = {"low": "低预算", "medium": "中等预算", "high": "高预算"}
    explanations.append(
        f"预算按{budget_labels[preference.budget_level]}进行匹配"
    )
    return explanations
