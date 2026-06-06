"""Deterministic, preference-aware candidate ranking for the MVP."""

from src.schemas.models import (
    PreferenceWeights,
    RouteEstimate,
    UserIntent,
    UserPreference,
)
from src.services.preference_service import build_preference_weights


def rank_pois(
    candidates: list[dict],
    intent: UserIntent,
    routes: dict[str, RouteEstimate],
    weather: dict,
    preference: UserPreference | None = None,
    weights: PreferenceWeights | None = None,
) -> list[dict]:
    """Rank activities with intent constraints and questionnaire weights."""
    preference = preference or UserPreference()
    weights = weights or build_preference_weights(preference)
    ranked = []

    for candidate in candidates:
        route = routes[candidate["id"]]
        child_score = _child_friendly_score(candidate, intent)
        indoor_score = _indoor_score(candidate, preference, weather)
        components = {
            "distance": _travel_score(
                route.duration_min,
                preference.max_travel_minutes,
            ),
            "activity_match": _poi_activity_score(candidate, preference),
            "child_friendly": child_score,
            "diet_match": 0.0,
            "popularity": _rating_score(candidate),
            "budget": _budget_score(
                candidate.get("price", 0),
                preference.budget_level,
                kind="activity",
            ),
            "indoor": indoor_score,
            "low_wait": _wait_score(candidate.get("wait_time_min", 10)),
        }
        score = _weighted_score(components, weights)
        reasons = [f"通勤约 {route.duration_min} 分钟"]
        if components["activity_match"] >= 0.7:
            reasons.append("匹配活动偏好")
        if intent.child_age is not None and child_score == 1:
            reasons.append(f"适合 {intent.child_age} 岁孩子")
        if preference.prefer_indoor and candidate.get("indoor"):
            reasons.append("符合室内优先偏好")
        if preference.prefer_low_wait and components["low_wait"] >= 0.7:
            reasons.append("预计等待较少")

        ranked.append({
            **candidate,
            "score": score,
            "score_components": components,
            "ranking_reasons": reasons,
            "route": route.model_dump(),
        })

    return sorted(ranked, key=lambda item: item["score"], reverse=True)


def rank_restaurants(
    candidates: list[dict],
    intent: UserIntent,
    routes: dict[str, RouteEstimate],
    preference: UserPreference | None = None,
    weights: PreferenceWeights | None = None,
) -> list[dict]:
    """Rank restaurants with dietary, budget, travel, and wait preferences."""
    preference = preference or UserPreference()
    weights = weights or build_preference_weights(preference)
    ranked = []

    for candidate in candidates:
        route = routes[candidate["id"]]
        diet_score = _restaurant_diet_score(
            candidate,
            preference,
            intent,
        )
        child_score = _restaurant_child_score(candidate, intent)
        components = {
            "distance": _travel_score(
                route.duration_min,
                preference.max_travel_minutes,
            ),
            "activity_match": (
                1.0
                if intent.scene in candidate.get("suitable_scenes", [])
                else 0.0
            ),
            "child_friendly": child_score,
            "diet_match": diet_score,
            "popularity": _rating_score(candidate),
            "budget": _budget_score(
                candidate.get("avg_price", 0),
                _effective_budget(preference, intent),
                kind="restaurant",
            ),
            "indoor": 1.0 if preference.prefer_indoor else 0.5,
            "low_wait": _wait_score(candidate.get("wait_time_min", 15)),
        }
        score = _weighted_score(components, weights)
        reasons = [f"距离活动地点约 {route.distance_km:g} 公里"]
        if diet_score >= 0.7:
            reasons.append("匹配餐饮偏好")
        if intent.child_age is not None and child_score == 1:
            reasons.append("提供儿童友好选择")
        if preference.prefer_low_wait and components["low_wait"] >= 0.7:
            reasons.append("预计等待较少")

        ranked.append({
            **candidate,
            "score": score,
            "score_components": components,
            "ranking_reasons": reasons,
            "route": route.model_dump(),
        })

    return sorted(ranked, key=lambda item: item["score"], reverse=True)


def _weighted_score(
    components: dict[str, float],
    weights: PreferenceWeights,
) -> float:
    value = (
        components["distance"] * weights.distance_weight
        + components["activity_match"] * weights.activity_match_weight
        + components["child_friendly"] * weights.child_friendly_weight
        + components["diet_match"] * weights.diet_match_weight
        + components["popularity"] * weights.popularity_weight
        + components["budget"] * weights.budget_weight
        + components["indoor"] * weights.indoor_weight
        + components["low_wait"] * weights.low_wait_weight
    )
    return round(value * 100, 2)


def _travel_score(duration_min: int, max_travel_minutes: int) -> float:
    if duration_min <= max_travel_minutes:
        return round(
            1 - 0.4 * duration_min / max_travel_minutes,
            4,
        )
    return round(
        max(
            0.0,
            0.5 - (duration_min - max_travel_minutes)
            / max_travel_minutes,
        ),
        4,
    )


def _poi_activity_score(
    candidate: dict,
    preference: UserPreference,
) -> float:
    type_score = max(
        (
            _activity_type_match(candidate, activity_type)
            for activity_type in preference.activity_types
        ),
        default=0.5,
    )
    intensity_score = _intensity_score(candidate, preference)
    return round(type_score * 0.8 + intensity_score * 0.2, 4)


def _activity_type_match(candidate: dict, activity_type: str) -> float:
    poi_type = str(candidate.get("type", "")).lower()
    tags = {str(tag).lower() for tag in candidate.get("tags", [])}
    normalized = activity_type.lower()
    mappings = {
        "亲子乐园": {"亲子", "乐园", "kids", "playground", "family"},
        "展览": {"展览", "科普馆", "exhibition", "art", "museum"},
        "citywalk": {"citywalk", "historic"},
        "商场轻松逛": {"商场", "shopping", "mall"},
        "户外公园": {"公园", "outdoor", "nature"},
        "酒吧/夜生活": {"酒吧", "bar", "night"},
    }
    keywords = mappings.get(normalized, {normalized})
    if any(keyword in poi_type for keyword in keywords):
        return 1.0
    if tags & keywords:
        return 1.0
    return 0.0


def _intensity_score(
    candidate: dict,
    preference: UserPreference,
) -> float:
    tags = set(candidate.get("tags", []))
    duration = int(candidate.get("avg_duration_min", 90))
    if preference.activity_intensity == "light":
        return 1.0 if candidate.get("indoor") or duration <= 90 else 0.5
    if preference.activity_intensity == "high":
        return 1.0 if "outdoor" in tags and duration >= 60 else 0.4
    return 1.0 if 60 <= duration <= 120 else 0.6


def _child_friendly_score(candidate: dict, intent: UserIntent) -> float:
    tags = set(candidate.get("tags", []))
    min_age, max_age = candidate.get("age_range", [0, 99])
    has_child_features = bool(
        {"kids", "family", "playground", "educational"} & tags
    )
    if intent.child_age is not None:
        if not min_age <= intent.child_age <= max_age:
            return 0.0
        return 1.0 if has_child_features else 0.5
    return 1.0 if has_child_features else 0.0


def _restaurant_child_score(candidate: dict, intent: UserIntent) -> float:
    tags = set(candidate.get("tags", []))
    child_friendly = (
        candidate.get("has_kids_meal")
        or "family_friendly" in tags
        or "kids_friendly" in tags
    )
    if intent.child_age is not None:
        return 1.0 if child_friendly else 0.0
    return 0.7 if child_friendly else 0.0


def _restaurant_diet_score(
    candidate: dict,
    preference: UserPreference,
    intent: UserIntent,
) -> float:
    tags = set(candidate.get("tags", []))
    matches = []
    preferences = set(preference.dining_preferences)
    if {"减脂", "清淡", "低油"} & set(intent.diet_preferences):
        preferences.add("清淡健康")

    for dining_preference in preferences:
        if dining_preference == "清淡健康":
            matches.append(
                bool(
                    candidate.get("has_low_fat_meal")
                    or {"healthy", "light_food", "low_fat"} & tags
                )
            )
        elif dining_preference == "亲子友好":
            matches.append(
                bool(
                    candidate.get("has_kids_meal")
                    or {"family_friendly", "kids_friendly"} & tags
                )
            )
        elif dining_preference == "网红打卡":
            matches.append("photo_friendly" in tags)
        elif dining_preference == "性价比":
            matches.append(
                candidate.get("avg_price", 999) <= 80
                or "affordable" in tags
            )
        elif dining_preference == "火锅烧烤":
            matches.append(bool({"hotpot", "barbecue", "spicy"} & tags))

    if not matches:
        return 0.5
    return round(sum(matches) / len(matches), 4)


def _budget_score(price: float, budget_level: str, kind: str) -> float:
    low_limit = 60 if kind == "activity" else 80
    medium_limit = 150 if kind == "activity" else 130
    if budget_level == "low":
        return 1.0 if price <= low_limit else max(0.0, low_limit / price)
    if budget_level == "high":
        return 1.0 if price >= low_limit else 0.8
    return 1.0 if price <= medium_limit else max(0.3, medium_limit / price)


def _effective_budget(
    preference: UserPreference,
    intent: UserIntent,
) -> str:
    if intent.budget_preference == "not_expensive":
        return "low"
    return preference.budget_level


def _indoor_score(
    candidate: dict,
    preference: UserPreference,
    weather: dict,
) -> float:
    if preference.prefer_indoor or not weather.get("outdoor_friendly", True):
        return 1.0 if candidate.get("indoor") else 0.0
    return 0.6 if candidate.get("indoor") else 0.8


def _wait_score(wait_time_min: int) -> float:
    return round(max(0.0, 1 - min(wait_time_min, 45) / 45), 4)


def _rating_score(candidate: dict) -> float:
    return round(min(float(candidate.get("rating", 0)) / 5, 1.0), 4)
