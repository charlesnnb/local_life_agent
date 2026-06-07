"""Rank validated candidates with task relevance as the dominant signal."""

from dataclasses import dataclass

from src.core.result_validator import validate_candidate
from src.schemas.models import PlannedTask, PreferenceProfile, UserIntent


@dataclass(frozen=True)
class TaskRankingResult:
    selected_candidate: dict | None
    ranked_candidates: list[dict]
    rejected_candidates: list[dict]


def rank_task_candidates(
    task: PlannedTask,
    candidates: list[dict],
    intent: UserIntent,
    profile: PreferenceProfile,
) -> TaskRankingResult:
    """Filter irrelevant candidates, then rank the remaining task-aware set."""
    ranked: list[dict] = []
    rejected: list[dict] = []

    for candidate in candidates:
        validation = validate_candidate(candidate, task)
        if not validation.is_relevant:
            rejected.append({
                "id": candidate.get("id"),
                "name": candidate.get("name", "未命名地点"),
                "reason": validation.reason,
                "source": candidate.get("source", "unknown"),
                "matched_terms": validation.matched_terms,
                "excluded_terms": validation.excluded_terms,
                "negative_terms": validation.negative_terms,
                "reasons": validation.reasons,
                "task_category": validation.category,
            })
            continue

        components = {
            "task_relevance": validation.relevance_score,
            "distance": _distance_score(candidate, profile),
            "rating": _rating_score(candidate),
            "wait_time": _wait_score(candidate),
            "preference": _preference_score(candidate, profile),
            "time_window": _time_window_score(candidate, task),
            "budget": _budget_score(candidate, profile),
            "indoor_outdoor": _indoor_score(candidate, profile),
            "child_suitability": _child_score(candidate, task, intent),
        }
        score = round(
            (
                components["task_relevance"] * 0.55
                + components["distance"] * 0.10
                + components["rating"] * 0.09
                + components["wait_time"] * 0.07
                + components["preference"] * 0.07
                + components["time_window"] * 0.04
                + components["budget"] * 0.03
                + components["indoor_outdoor"] * 0.02
                + components["child_suitability"] * 0.03
            )
            * 100,
            2,
        )
        ranked.append({
            **candidate,
            "score": score,
            "task_category": validation.category,
            "matched_terms": validation.matched_terms,
            "negative_terms": validation.negative_terms,
            "reasons": validation.reasons,
            "score_components": components,
            "ranking_reasons": [
                validation.reason,
                _summary_reason(components),
            ],
            "selection_reasons": [
                validation.reason,
                _summary_reason(components),
            ],
        })

    ranked.sort(key=_ranking_key, reverse=True)
    return TaskRankingResult(
        selected_candidate=ranked[0] if ranked else None,
        ranked_candidates=ranked,
        rejected_candidates=rejected,
    )


def _distance_score(candidate: dict, profile: PreferenceProfile) -> float:
    meters = candidate.get("distance_meters")
    if isinstance(meters, (int, float)) and meters >= 0:
        preferred_meters = profile.preference.max_travel_minutes * 500
        return round(max(0.0, 1 - meters / max(preferred_meters, 1)), 4)
    distance_km = candidate.get("distance_km")
    if isinstance(distance_km, (int, float)) and distance_km >= 0:
        preferred_km = profile.preference.max_travel_minutes / 2
        return round(max(0.0, 1 - distance_km / max(preferred_km, 1)), 4)
    return 0.5


def _rating_score(candidate: dict) -> float:
    try:
        return round(min(max(float(candidate.get("rating") or 0), 0) / 5, 1), 4)
    except (TypeError, ValueError):
        return 0.5


def _wait_score(candidate: dict) -> float:
    try:
        wait = max(0, float(candidate.get("wait_time_min", 15)))
    except (TypeError, ValueError):
        wait = 15
    return round(max(0.0, 1 - min(wait, 60) / 60), 4)


def _preference_score(candidate: dict, profile: PreferenceProfile) -> float:
    text = _candidate_text(candidate)
    matches = 0
    for value in [
        *profile.preference.activity_types,
        *profile.preference.dining_preferences,
    ]:
        keywords = {
            "亲子乐园": ("亲子", "儿童", "kids", "family"),
            "展览": ("展览", "美术", "博物", "exhibition"),
            "citywalk": ("citywalk", "街区", "步行"),
            "商场轻松逛": ("商场", "购物", "mall"),
            "户外公园": ("户外", "公园", "森林", "outdoor"),
            "酒吧/夜生活": ("酒吧", "清吧", "bar", "night"),
        }.get(value.lower(), (value.lower(),))
        matches += int(any(keyword in text for keyword in keywords))
    total = len(profile.preference.activity_types) + len(
        profile.preference.dining_preferences
    )
    return round(matches / total, 4) if total else 0.5


def _time_window_score(candidate: dict, task: PlannedTask) -> float:
    text = _candidate_text(candidate)
    if "晚上" in task.time_window:
        return 1.0 if any(
            word in text for word in ("酒吧", "清吧", "夜", "bar", "lounge")
        ) else 0.5
    if "下午" in task.time_window:
        return 1.0 if "night" not in text else 0.5
    return 0.7


def _budget_score(candidate: dict, profile: PreferenceProfile) -> float:
    try:
        price = float(candidate.get("price") or candidate.get("cost") or 0)
    except (TypeError, ValueError):
        return 0.5
    if price <= 0:
        return 0.5
    level = profile.preference.budget_level
    if level == "low":
        return 1.0 if price <= 80 else max(0.0, 80 / price)
    if level == "high":
        return 1.0 if price >= 100 else 0.7
    return 1.0 if price <= 180 else max(0.3, 180 / price)


def _indoor_score(candidate: dict, profile: PreferenceProfile) -> float:
    indoor = bool(candidate.get("indoor"))
    if profile.preference.prefer_indoor:
        return 1.0 if indoor else 0.0
    return 0.6 if indoor else 0.8


def _child_score(
    candidate: dict,
    task: PlannedTask,
    intent: UserIntent,
) -> float:
    child_age = getattr(task, "child_age", None)
    if child_age is None:
        return 0.5
    age_range = candidate.get("age_range", [0, 99])
    try:
        in_range = age_range[0] <= child_age <= age_range[1]
    except (IndexError, TypeError):
        in_range = True
    if candidate.get("child_friendly"):
        return 1.0 if in_range else 0.45
    return 0.6 if in_range else 0.25


def _candidate_text(candidate: dict) -> str:
    return " ".join(
        [
            str(candidate.get("name", "")),
            str(candidate.get("type", "")),
            " ".join(str(tag) for tag in candidate.get("tags", [])),
        ]
    ).lower()


def _summary_reason(components: dict[str, float]) -> str:
    strongest = max(
        (
            (name, value)
            for name, value in components.items()
            if name != "task_relevance"
        ),
        key=lambda item: item[1],
    )
    labels = {
        "distance": "距离",
        "rating": "评分",
        "wait_time": "排队",
        "preference": "用户偏好",
        "time_window": "时段",
        "budget": "预算",
        "indoor_outdoor": "室内外偏好",
        "child_suitability": "儿童适配",
    }
    return f"次要排序优势：{labels[strongest[0]]}"


def _ranking_key(candidate: dict) -> tuple[float, ...]:
    components = candidate["score_components"]
    return (
        components["task_relevance"],
        components["distance"],
        components["preference"],
        components["rating"],
        components["wait_time"],
        components["budget"],
        components["time_window"],
        components["indoor_outdoor"],
        components["child_suitability"],
    )
