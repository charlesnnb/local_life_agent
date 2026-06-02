"""Intent parsing and constraint extraction from natural language queries."""

import re
from backend.data_loader import get_user, get_family_profile, get_friend_group


def parse_intent(query: str) -> dict:
    """Parse user intent from natural language query using rules."""
    # Scene detection
    family_keywords = ["老婆", "孩子", "家庭", "小孩", "宝宝", "女儿", "儿子", "家人", "亲子"]
    friends_keywords = ["朋友", "哥们", "闺蜜", "聚会", "组队", "群", "男女"]

    has_family = any(kw in query for kw in family_keywords)
    has_friends = any(kw in query for kw in friends_keywords)

    # If query mentions both male and female without family context, it's friends
    has_gender_mix = ("男" in query and "女" in query) and not has_family
    # Multiple people without family context suggests friends
    has_party = bool(re.search(r"(\d+)\s*个人", query)) and not has_family
    # "我们 X 人" without family words
    has_we_party = bool(re.search(r"我们\s*\d*\s*人", query)) and not has_family

    if has_family:
        scene = "family"
    elif has_friends or has_gender_mix or has_party or has_we_party:
        scene = "friends"
    else:
        scene = "solo"  # default to solo, not family — avoids wrong profile merge

    return {
        "intent": "short_activity_planning",
        "scene": scene,
        "need_execution": True,
    }


def extract_constraints(query: str, user_id: str, scene: str) -> dict:
    """Extract structured constraints from query and user profile."""
    user = get_user(user_id)
    if not user:
        raise ValueError(f"User {user_id} not found")

    home_district = user["home_location"]["district"]
    default_transport = user.get("preferred_transport", "taxi")
    max_distance = user.get("max_distance_km", 8)

    # Detect afternoon / time
    is_afternoon = any(kw in query for kw in ["下午", "午后", "中午"])
    start_time = "14:00" if is_afternoon else "13:00"
    end_time = "19:00" if is_afternoon else "18:00"

    # Duration: default 4-6 hours
    duration_min = [240, 360]

    if scene == "family":
        return _extract_family_constraints(
            query, user_id, start_time, end_time, duration_min,
            default_transport, max_distance, home_district,
        )
    else:
        return _extract_friends_constraints(
            query, user_id, start_time, end_time, duration_min,
            default_transport, max_distance, home_district,
        )


def _extract_family_constraints(
    query: str, user_id: str, start_time: str, end_time: str,
    duration_min: list, transport: str, max_distance: float, district: str,
) -> dict:
    """Extract family-specific constraints."""
    profile = get_family_profile(user_id)
    child_age = 5
    party_size = 3

    if profile:
        for m in profile.get("members", []):
            if m["role"] == "child":
                child_age = m.get("age", 5)
        party_size = len(profile.get("members", []))

    return {
        "scene": "family",
        "start_time": start_time,
        "end_time": end_time,
        "duration_min": duration_min,
        "max_distance_km": max_distance,
        "child_age": child_age,
        "party_size": party_size,
        "preferences": ["child_friendly", "low_fat", "not_too_far", "indoor_preferred"],
        "must_include": ["activity", "meal"],
        "optional_extra": ["cake", "flower"],
        "transport": transport,
        "weather": "sunny",
        "home_district": district,
    }


def _extract_friends_constraints(
    query: str, user_id: str, start_time: str, end_time: str,
    duration_min: list, transport: str, max_distance: float, district: str,
) -> dict:
    """Extract friends-specific constraints."""
    # Parse party size from query
    party_match = re.search(r"(\d+)\s*人", query)
    party_size = int(party_match.group(1)) if party_match else 4

    # Gender mix
    male_count = len(re.findall(r"(男|哥们)", query))
    female_count = len(re.findall(r"(女|闺蜜)", query))
    if male_count == 0:
        male_count = 2
    if female_count == 0:
        female_count = party_size - male_count

    return {
        "scene": "friends",
        "start_time": start_time,
        "end_time": end_time,
        "duration_min": duration_min,
        "max_distance_km": max(max_distance, 10),
        "child_age": None,
        "party_size": party_size,
        "preferences": ["social", "photo_friendly", "good_food", "not_too_tiring", "chat_friendly"],
        "must_include": ["activity", "meal"],
        "optional_extra": ["coffee", "dessert"],
        "transport": transport,
        "weather": "sunny",
        "home_district": district,
        "gender_mix": {"male": male_count, "female": female_count},
    }
