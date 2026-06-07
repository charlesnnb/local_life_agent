"""Build a compact, feasible 3-4 hour activity timeline."""

from src.schemas.models import (
    ActivityPlan,
    PlanStep,
    ResolvedLocation,
    RouteEstimate,
    Timeline,
    TimelineItem,
    UserIntent,
)


def build_plan(
    intent: UserIntent,
    location: ResolvedLocation,
    poi: dict,
    restaurant: dict,
    home_to_poi: RouteEstimate,
    poi_to_restaurant: RouteEstimate,
    restaurant_to_home: RouteEstimate,
    weather: dict,
) -> ActivityPlan:
    """Combine selected places and routes into an executable timeline."""
    schedule = _build_schedule(
        intent,
        poi,
        home_to_poi,
        poi_to_restaurant,
        restaurant_to_home,
    )

    activity_reason = _activity_reason(intent, poi, home_to_poi)
    restaurant_reason = _restaurant_reason(intent, restaurant)

    steps = [
        PlanStep(
            time=_format_time(schedule["start"]),
            action="出发",
            description=(
                f"从{location.address}出发，预计 {home_to_poi.duration_min} 分钟到达"
                f"{poi['name']}。"
            ),
        ),
        PlanStep(
            time=_format_time(schedule["activity_start"]),
            action="亲子活动" if intent.scene == "family" else "活动",
            place=poi["name"],
            description=f"游玩约 {schedule['activity_duration']} 分钟。",
            reason=activity_reason,
            source=poi.get("source", "mock"),
        ),
        PlanStep(
            time=_format_time(schedule["activity_end"]),
            action="前往餐厅",
            place=restaurant["name"],
            description=f"路程约 {poi_to_restaurant.duration_min} 分钟，预留缓冲后用餐。",
        ),
        *(
            [
                PlanStep(
                    time=_format_time(schedule["restaurant_arrival"]),
                    action="到达餐厅",
                    place=restaurant["name"],
                    description=(
                        f"到达餐厅，距离用餐开始还有 "
                        f"{schedule['meal_wait_minutes']} 分钟。"
                    ),
                    source=restaurant.get("source", "mock"),
                )
            ]
            if schedule["meal_wait_minutes"] > 0
            else []
        ),
        PlanStep(
            time=_format_time(schedule["meal_start"]),
            action="晚餐",
            place=restaurant["name"],
            description="用餐约 70 分钟。",
            reason=restaurant_reason,
            source=restaurant.get("source", "mock"),
        ),
        PlanStep(
            time=_format_time(schedule["meal_end"]),
            action="返回",
            description=f"从餐厅返回，预计 {restaurant_to_home.duration_min} 分钟。",
        ),
        PlanStep(
            time=_format_time(schedule["home_arrival"]),
            action="到家",
            description="行程结束，整体节奏轻松，不会太赶。",
        ),
    ]

    reasons = [
        f"活动距离约 {home_to_poi.distance_km:g} 公里，符合就近出行要求",
        activity_reason,
        restaurant_reason,
        f"{weather.get('condition', '天气稳定')}，已纳入活动选择",
    ]
    period = next(
        (name for name in ["上午", "下午", "晚上"] if name in intent.time_window),
        "下午",
    )
    summary = (
        f"{period}亲子轻松出行方案"
        if intent.scene == "family"
        else f"{period}本地轻松出行方案"
    )
    return ActivityPlan(summary=summary, steps=steps, reasons=_unique(reasons))


def build_timeline(
    intent: UserIntent,
    location: ResolvedLocation,
    poi: dict,
    restaurant: dict,
    home_to_poi: RouteEstimate,
    poi_to_restaurant: RouteEstimate,
    restaurant_to_home: RouteEstimate,
) -> Timeline:
    """Build a typed timeline from the same schedule used by the plan."""
    schedule = _build_schedule(
        intent,
        poi,
        home_to_poi,
        poi_to_restaurant,
        restaurant_to_home,
    )
    restaurant_reason = _restaurant_reason(intent, restaurant)
    restaurant_items = [
        TimelineItem(
            time=_format_time(schedule["restaurant_arrival"]),
            type="restaurant",
            title=(
                f"到达{restaurant['name']}"
                if schedule["meal_wait_minutes"] > 0
                else f"到达并开始在{restaurant['name']}用餐"
            ),
            description=(
                "已到达餐厅，等待用餐开始。"
                if schedule["meal_wait_minutes"] > 0
                else restaurant_reason
            ),
        )
    ]
    if schedule["meal_wait_minutes"] > 0:
        restaurant_items.extend([
            TimelineItem(
                time=_format_time(schedule["restaurant_arrival"]),
                type="break",
                title="等待 / 休息",
                description=(
                    f"距离 {_format_time(schedule['meal_start'])} 开始用餐还有约 "
                    f"{schedule['meal_wait_minutes']} 分钟，可休息或提前取号。"
                ),
            ),
            TimelineItem(
                time=_format_time(schedule["meal_start"]),
                type="restaurant",
                title=f"开始在{restaurant['name']}用餐",
                description=restaurant_reason,
            ),
        ])
    return Timeline(
        items=[
            TimelineItem(
                time=_format_time(schedule["start"]),
                type="departure",
                title=f"从{_origin_title(location)}出发",
                description=f"预计通勤 {home_to_poi.duration_min} 分钟",
            ),
            TimelineItem(
                time=_format_time(schedule["activity_start"]),
                type="activity",
                title=f"到达{poi['name']}",
                description=(
                    f"{'亲子' if intent.scene == 'family' else ''}活动约 "
                    f"{schedule['activity_duration']} 分钟"
                ),
            ),
            TimelineItem(
                time=_format_time(schedule["activity_end"]),
                type="transfer",
                title=f"前往{restaurant['name']}",
                description=f"预计通勤 {poi_to_restaurant.duration_min} 分钟",
            ),
            *restaurant_items,
            TimelineItem(
                time=_format_time(schedule["meal_end"]),
                type="return",
                title="结束并返回",
                description=f"预计返程 {restaurant_to_home.duration_min} 分钟",
            ),
            TimelineItem(
                time=_format_time(schedule["home_arrival"]),
                type="arrival",
                title="返回出发地",
                description=(
                    f"整体行程约 "
                    f"{schedule['total_duration_minutes'] / 60:.1f} 小时"
                ),
            ),
        ],
        total_duration_minutes=schedule["total_duration_minutes"],
    )


def _build_schedule(
    intent: UserIntent,
    poi: dict,
    home_to_poi: RouteEstimate,
    poi_to_restaurant: RouteEstimate,
    restaurant_to_home: RouteEstimate,
) -> dict[str, int]:
    start = _start_minutes(intent.time_window)
    activity_start = start + home_to_poi.duration_min
    activity_duration = min(max(int(poi.get("avg_duration_min", 90)), 75), 100)
    activity_end = activity_start + activity_duration
    restaurant_arrival = activity_end + poi_to_restaurant.duration_min
    meal_start = max(restaurant_arrival, start + 150)
    meal_wait_minutes = max(0, meal_start - restaurant_arrival)
    meal_end = meal_start + 70
    home_arrival = meal_end + restaurant_to_home.duration_min
    return {
        "start": start,
        "activity_start": activity_start,
        "activity_duration": activity_duration,
        "activity_end": activity_end,
        "restaurant_arrival": restaurant_arrival,
        "meal_start": meal_start,
        "meal_wait_minutes": meal_wait_minutes,
        "meal_end": meal_end,
        "home_arrival": home_arrival,
        "total_duration_minutes": home_arrival - start,
    }


def _origin_title(location: ResolvedLocation) -> str:
    if location.source == "demo_default":
        return "默认位置：上海徐汇"
    return location.address


def _activity_reason(
    intent: UserIntent,
    poi: dict,
    route: RouteEstimate,
) -> str:
    parts = [f"距离近，通勤约 {route.duration_min} 分钟"]
    if intent.child_age is not None:
        parts.append(f"适合 {intent.child_age} 岁孩子")
    if poi.get("indoor"):
        parts.append("室内活动强度低")
    return "，".join(parts)


def _restaurant_reason(intent: UserIntent, restaurant: dict) -> str:
    parts = []
    wants_light_food = bool(
        {"减脂", "清淡", "低油"} & set(intent.diet_preferences)
    )
    if wants_light_food and restaurant.get("has_low_fat_meal"):
        parts.append("有清淡低脂选择")
    if intent.child_age is not None and restaurant.get("has_kids_meal"):
        parts.append("也有儿童餐")
    if restaurant.get("reservation_supported"):
        parts.append("支持提前预约")
    return "，".join(parts) or "与同行人需求匹配"


def _start_minutes(time_window: str) -> int:
    if "上午" in time_window:
        return 9 * 60 + 30
    if "晚上" in time_window:
        return 18 * 60
    return 14 * 60


def _format_time(total_minutes: int) -> str:
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours:02d}:{minutes:02d}"


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))
