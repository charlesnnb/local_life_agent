"""Clear rule-based intent parsing for Priority 1."""

import re

from src.schemas.models import UserIntent


KNOWN_CITIES = ["上海", "北京", "广州", "深圳", "杭州"]


def parse_intent(query: str) -> UserIntent:
    """Parse a local-life request into explicit planning constraints."""
    normalized = query.strip()
    companions = _parse_companions(normalized)
    child_age = _parse_child_age(normalized)
    gender_mix = _parse_gender_mix(normalized)
    scene = _parse_scene(normalized, companions, child_age)

    distance_preference = _parse_distance_preference(normalized)
    weather_constraint = _parse_weather_constraint(normalized)
    activity_preferences = _parse_activity_preferences(
        normalized,
        scene,
        distance_preference,
        weather_constraint,
    )
    diet_preferences = _parse_diet_preferences(normalized)
    avoid = _parse_avoid(normalized, weather_constraint)

    intent = UserIntent(
        raw_query=query,
        scene=scene,
        time_window=_parse_time_window(normalized),
        duration_hours=_parse_duration_hours(normalized),
        companions=companions,
        party_size=_parse_party_size(normalized, scene, companions, gender_mix),
        child_age=child_age,
        gender_mix=gender_mix,
        distance_preference=distance_preference,
        activity_preferences=activity_preferences,
        diet_preferences=diet_preferences,
        budget_preference=_parse_budget_preference(normalized),
        avoid=avoid,
        weather_constraint=weather_constraint,
        city=next((city for city in KNOWN_CITIES if city in normalized), None),
    )
    from src.core.task_decomposer import decompose_tasks

    intent.tasks = decompose_tasks(normalized, intent)
    intent.time_windows = list(dict.fromkeys(
        task.time_window for task in intent.tasks if task.time_window
    ))
    return intent


def _parse_companions(query: str) -> list[str]:
    groups = [
        ("老婆", ["老婆", "妻子", "媳妇"]),
        ("老公", ["老公", "丈夫"]),
        ("孩子", ["孩子", "小孩", "宝宝", "女儿", "儿子"]),
        ("朋友", ["朋友", "哥们", "闺蜜", "同事"]),
    ]
    return [
        label
        for label, keywords in groups
        if any(keyword in query for keyword in keywords)
    ]


def _parse_child_age(query: str) -> int | None:
    patterns = [
        r"(?:孩子|小孩|宝宝|女儿|儿子)\s*(\d{1,2})\s*岁",
        r"(\d{1,2})\s*岁(?:的)?(?:孩子|小孩|宝宝|女儿|儿子)",
    ]
    for pattern in patterns:
        match = re.search(pattern, query)
        if match:
            return int(match.group(1))
    return None


def _parse_gender_mix(query: str) -> dict[str, int] | None:
    match = re.search(r"(\d+)\s*男\s*(\d+)\s*女", query)
    if not match:
        match = re.search(r"(\d+)\s*个?男(?:生)?\s*(\d+)\s*个?女(?:生)?", query)
    if not match:
        return None
    return {"male": int(match.group(1)), "female": int(match.group(2))}


def _parse_scene(
    query: str,
    companions: list[str],
    child_age: int | None,
) -> str:
    if "孩子" in companions or child_age is not None or "亲子" in query:
        return "family"
    if "朋友" in companions or any(word in query for word in ["聚会", "组局", "朋友局"]):
        return "friends"
    if (
        any(person in companions for person in ["老婆", "老公"])
        or any(word in query for word in ["约会", "情侣", "二人世界"])
    ):
        return "couple"
    return "solo"


def _parse_time_window(query: str) -> str:
    day = ""
    if "今天" in query:
        day = "今天"
    elif "明天" in query:
        day = "明天"
    elif any(word in query for word in ["周末", "星期六", "星期日", "周六", "周日"]):
        day = "周末"

    period = ""
    if any(word in query for word in ["下午", "午后"]):
        period = "下午"
    elif any(word in query for word in ["晚上", "傍晚", "晚饭", "晚餐"]):
        period = "晚上"
    elif any(word in query for word in ["上午", "早上", "早晨"]):
        period = "上午"

    return f"{day}{period}" or "未指定"


def _parse_duration_hours(query: str) -> list[float]:
    range_match = re.search(
        r"(\d+(?:\.\d+)?)\s*[-到至]\s*(\d+(?:\.\d+)?)\s*个?小时",
        query,
    )
    if range_match:
        return [float(range_match.group(1)), float(range_match.group(2))]

    exact_match = re.search(r"(\d+(?:\.\d+)?)\s*个?小时", query)
    if exact_match:
        hours = float(exact_match.group(1))
        return [hours, hours]

    if "半天" in query:
        return [4.0, 6.0]
    return [3.0, 4.0]


def _parse_party_size(
    query: str,
    scene: str,
    companions: list[str],
    gender_mix: dict[str, int] | None,
) -> int:
    explicit_patterns = [
        r"和\s*(\d+)\s*个?(?:朋友|人)",
        r"(\d+)\s*个?(?:朋友|人)",
    ]
    for pattern in explicit_patterns:
        match = re.search(pattern, query)
        if match:
            return int(match.group(1))

    if gender_mix:
        return gender_mix["male"] + gender_mix["female"]
    if scene == "family":
        return max(2, 1 + len(companions))
    if scene == "couple":
        return 2
    if scene == "friends":
        return 4
    return 1


def _parse_distance_preference(query: str) -> str:
    if any(word in query for word in ["别太远", "不远", "附近", "离家近", "就近"]):
        return "nearby"
    if any(word in query for word in ["远一点也行", "距离无所谓", "不限距离"]):
        return "flexible"
    return "normal"


def _parse_activity_preferences(
    query: str,
    scene: str,
    distance_preference: str,
    weather_constraint: str | None,
) -> list[str]:
    keyword_groups = [
        ("聊天", ["聊天", "聊聊天"]),
        ("拍照", ["拍照", "打卡", "出片"]),
        ("吃饭", ["吃饭", "用餐", "餐厅"]),
        ("安静", ["安静", "静一点", "安静点"]),
        ("散步", ["散步", "走走"]),
        ("室内", ["室内"]),
        ("逛逛", ["逛逛", "逛街", "逛一逛"]),
        ("轻松", ["轻松", "休闲", "不累", "别太累"]),
        ("亲子", ["亲子"]),
    ]
    preferences = [
        label
        for label, keywords in keyword_groups
        if any(keyword in query for keyword in keywords)
    ]

    if scene == "family":
        preferences.append("亲子")
    if scene == "family" and distance_preference == "nearby":
        preferences.append("轻松")
    if weather_constraint == "rain":
        preferences.append("室内")

    return _unique(preferences)


def _parse_diet_preferences(query: str) -> list[str]:
    preferences = []
    if any(word in query for word in ["减肥", "减脂", "控脂", "低脂"]):
        preferences.extend(["减脂", "清淡", "低油"])
    else:
        if "清淡" in query:
            preferences.append("清淡")
        if any(word in query for word in ["少油", "低油"]):
            preferences.append("低油")
    if any(word in query for word in ["素食", "吃素"]):
        preferences.append("素食")
    return _unique(preferences)


def _parse_budget_preference(query: str) -> str:
    if any(word in query for word in ["别太贵", "不贵", "便宜", "实惠", "预算有限"]):
        return "not_expensive"
    if any(word in query for word in ["预算无所谓", "价格无所谓", "贵一点也行"]):
        return "flexible"
    return "normal"


def _parse_avoid(query: str, weather_constraint: str | None) -> list[str]:
    avoid = []
    if any(word in query for word in ["别太远", "不要太远", "不想跑太远"]):
        avoid.append("太远")
    if any(word in query for word in ["不想太吵", "不要太吵", "别太吵", "怕吵"]):
        avoid.append("太吵")
    if any(word in query for word in ["不想排队", "不要排队", "别排队"]):
        avoid.append("排队")
    if weather_constraint == "rain":
        avoid.append("户外")
    return _unique(avoid)


def _parse_weather_constraint(query: str) -> str | None:
    if any(word in query for word in ["下雨", "雨天", "有雨"]):
        return "rain"
    if any(word in query for word in ["下雪", "雪天"]):
        return "snow"
    if any(word in query for word in ["太热", "高温", "炎热"]):
        return "hot"
    if any(word in query for word in ["太冷", "降温", "寒冷"]):
        return "cold"
    return None


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))
