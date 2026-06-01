"""Scoring functions for POI, restaurant, and plan evaluation."""

import math


def score_poi(
    poi: dict,
    distance_km: float,
    scene: str,
    constraints: dict,
    availability: dict | None = None,
) -> float:
    """Score a POI candidate using weighted criteria.

    POI_score = 0.25 * distance_score + 0.20 * scene_score + 0.20 * time_score
              + 0.15 * preference_score + 0.10 * rating_score + 0.10 * availability_score
    """
    max_dist = constraints.get("max_distance_km", 8)
    child_age = constraints.get("child_age")

    # Distance score (closer is better, capped at max_distance)
    if distance_km <= max_dist:
        distance_score = 1.0 - (distance_km / max_dist) * 0.5
    else:
        distance_score = max(0, 1.0 - (distance_km - max_dist) / max_dist)

    # Scene match score
    suitable = poi.get("suitable_scenes", [])
    scene_score = 1.0 if scene in suitable else 0.3

    # Time score: check if open during our window
    open_t = _time_to_minutes(poi.get("open_time", "00:00"))
    close_t = _time_to_minutes(poi.get("close_time", "23:59"))
    start_t = _time_to_minutes(constraints.get("start_time", "14:00"))
    end_t = _time_to_minutes(constraints.get("end_time", "19:00"))
    window_overlap = min(end_t, close_t) - max(start_t, open_t)
    time_score = max(0, min(1.0, window_overlap / 180))  # normalize to ~3 hours

    # Preference/tag match
    prefs = constraints.get("preferences", [])
    tags = poi.get("tags", [])
    if prefs:
        matches = sum(1 for p in prefs if _tag_matches(p, tags))
        preference_score = matches / max(len(prefs), 1)
    else:
        preference_score = 0.5

    # Rating score
    rating = poi.get("rating", 3.5)
    rating_score = min(1.0, rating / 5.0)

    # Availability score
    if availability and availability.get("available"):
        availability_score = 1.0
    elif availability:
        availability_score = 0.3
    else:
        availability_score = 0.8  # no info = neutral

    # Child age filter: hard penalty if age doesn't match
    if child_age is not None:
        age_min, age_max = poi.get("age_range", [0, 99])
        if child_age < age_min or child_age > age_max:
            return -1.0  # hard filter

    return (
        0.25 * distance_score
        + 0.20 * scene_score
        + 0.20 * time_score
        + 0.15 * preference_score
        + 0.10 * rating_score
        + 0.10 * availability_score
    )


def score_restaurant(
    restaurant: dict,
    distance_km: float,
    scene: str,
    constraints: dict,
    availability: dict | None = None,
) -> float:
    """Score a restaurant candidate.

    Restaurant_score = 0.20 * distance_score + 0.20 * availability_score
                      + 0.20 * diet_match_score + 0.15 * scene_score
                      + 0.10 * price_score + 0.10 * rating_score
                      + 0.05 * queue_score
    """
    max_dist = constraints.get("max_distance_km", 8)

    # Distance score
    if distance_km <= max_dist:
        distance_score = 1.0 - (distance_km / max_dist) * 0.5
    else:
        distance_score = max(0, 1.0 - (distance_km - max_dist) / max_dist)

    # Availability
    if availability and availability.get("available"):
        availability_score = 1.0
    elif availability and availability.get("remaining_tables", 0) > 0:
        availability_score = 0.6
    elif availability:
        availability_score = 0.2
    else:
        availability_score = 0.8

    # Diet match
    prefs = constraints.get("preferences", [])
    diet_score = 0.5
    if scene == "family":
        if restaurant.get("has_low_fat_meal"):
            diet_score += 0.3
        if restaurant.get("has_kids_meal"):
            diet_score += 0.2
    else:
        tags = restaurant.get("tags", [])
        for pref in ["social", "healthy", "chat_friendly"]:
            if pref in tags:
                diet_score += 0.15
    diet_match_score = min(1.0, diet_score)

    # Scene match
    suitable = restaurant.get("suitable_scenes", [])
    scene_score = 1.0 if scene in suitable else 0.3

    # Price score: lower price = higher score (within reason)
    price = restaurant.get("avg_price", 100)
    if price <= 80:
        price_score = 1.0
    elif price <= 120:
        price_score = 0.8
    elif price <= 200:
        price_score = 0.5
    else:
        price_score = 0.3

    # Rating
    rating = restaurant.get("rating", 3.5)
    rating_score = min(1.0, rating / 5.0)

    # Queue score
    queue_min = availability.get("queue_time_min", 0) if availability else 5
    queue_score = max(0, 1.0 - queue_min / 45)

    return (
        0.20 * distance_score
        + 0.20 * availability_score
        + 0.20 * diet_match_score
        + 0.15 * scene_score
        + 0.10 * price_score
        + 0.10 * rating_score
        + 0.05 * queue_score
    )


def score_plan(
    total_time_min: int,
    route_smoothness: float,
    people_match: float,
    execution_success: float,
    experience_richness: float,
) -> float:
    """Score the overall plan.

    Plan_score = 0.30 * total_time_feasibility + 0.25 * route_smoothness
               + 0.20 * people_match + 0.15 * execution_success_probability
               + 0.10 * experience_richness
    """
    # Time feasibility: 240-360 min is ideal
    if 240 <= total_time_min <= 360:
        time_score = 1.0
    elif 180 <= total_time_min <= 420:
        time_score = 0.7
    else:
        time_score = max(0, 1.0 - abs(total_time_min - 300) / 300)

    return (
        0.30 * time_score
        + 0.25 * route_smoothness
        + 0.20 * people_match
        + 0.15 * execution_success
        + 0.10 * experience_richness
    )


def _time_to_minutes(t: str) -> int:
    parts = t.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def _tag_matches(preference: str, tags: list[str]) -> bool:
    """Check if a preference keyword matches any tag."""
    mapping = {
        "child_friendly": ["kids", "family", "playground", "children"],
        "low_fat": ["low_fat", "healthy", "light_food", "vegetarian"],
        "not_too_far": [],
        "indoor_preferred": ["indoor"],
        "social": ["social", "group", "chat_friendly"],
        "photo_friendly": ["photo_friendly", "art", "historic"],
        "good_food": ["food", "chinese", "japanese", "italian", "western"],
        "not_too_tiring": ["indoor", "casual", "relaxing"],
        "chat_friendly": ["chat_friendly", "cozy", "quiet", "social"],
    }
    keywords = mapping.get(preference, [preference])
    for kw in keywords:
        if kw in tags:
            return True
    return False
