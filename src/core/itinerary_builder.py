"""Build ordered plans for multiple time windows and task types."""

from src.schemas.models import (
    ActivityPlan,
    MultiStepItinerary,
    PlanStep,
    ResolvedLocation,
    RouteEstimate,
    Timeline,
    TimelineItem,
    UserIntent,
)
from src.tools.food_order_tool import order_food
from src.tools.route_tool import build_ordered_route_plan, estimate_route


TIME_ANCHORS = {
    "早上": 8 * 60,
    "上午": 9 * 60 + 30,
    "中午": 12 * 60,
    "下午": 14 * 60 + 30,
    "傍晚": 18 * 60,
    "晚上": 19 * 60,
}


def build_multistep_itinerary(
    intent: UserIntent,
    location: ResolvedLocation,
    selected_places: list[dict],
    route_legs: list[RouteEstimate] | None = None,
    return_leg: RouteEstimate | None = None,
) -> MultiStepItinerary:
    """Build one timeline while keeping delivery out of offline route stops."""
    places_by_task = {
        place["task_id"]: place for place in selected_places
    }
    legs, final_return = _resolve_routes(
        location,
        selected_places,
        route_legs,
        return_leg,
    )
    route_plan = build_ordered_route_plan(
        location,
        selected_places,
        legs,
        final_return,
    )

    items: list[TimelineItem] = []
    steps: list[PlanStep] = []
    actions = []
    current_end = 0
    offline_index = 0

    for task in intent.tasks:
        anchor = _time_anchor(task.time_window)
        if task.task_type == "food_order":
            brand = task.target or "餐食"
            order_action = order_food(
                brand,
                task.time_window,
                _origin_name(location),
            )
            actions.append(order_action)
            order_time = max(anchor, current_end)
            delivery_time = (
                order_time
                + order_action.details["estimated_delivery_minutes"]
            )
            items.extend([
                TimelineItem(
                    time=_format_time(order_time),
                    type="food_order",
                    title=f"{task.time_window}点{brand}",
                    description=order_action.message or "已模拟完成点餐",
                ),
                TimelineItem(
                    time=_format_time(delivery_time),
                    type="delivery",
                    title=f"{brand}预计送达",
                    description="外卖送到当前位置，不加入线下路线。",
                ),
            ])
            steps.append(
                PlanStep(
                    time=_format_time(order_time),
                    action="点餐",
                    place=brand,
                    description=order_action.message or "已模拟完成点餐",
                    source="mock",
                )
            )
            current_end = delivery_time
            continue

        place = places_by_task.get(task.task_id)
        if place is None:
            continue
        leg = legs[offline_index]
        departure = max(anchor, current_end)
        arrival = departure + leg.duration_min
        duration = _task_duration(task.task_type, place)
        finish = arrival + duration
        destination_label = (
            "酒吧" if task.task_type == "bar_visit" else f"{task.target}地点"
        )
        item_type = (
            "bar" if task.task_type == "bar_visit" else "activity"
        )
        action = (
            "酒吧放松" if task.task_type == "bar_visit" else task.target or "活动"
        )

        items.extend([
            TimelineItem(
                time=_format_time(departure),
                type="transfer",
                title=f"前往{destination_label}",
                description=(
                    f"从{_previous_place_name(location, selected_places, offline_index)}"
                    f"出发，预计 {leg.duration_min} 分钟"
                ),
            ),
            TimelineItem(
                time=_format_time(arrival),
                type=item_type,
                title=f"到达{place['name']}",
                description=(
                    f"{task.target or action}放松约 {duration // 60:g} 小时"
                ),
            ),
        ])
        if task.task_type == "activity_search":
            items.append(
                TimelineItem(
                    time=_format_time(finish),
                    type="break",
                    title=f"结束{task.target or '活动'}，稍作休息",
                    description="为下一阶段预留缓冲时间。",
                )
            )

        steps.extend([
            PlanStep(
                time=_format_time(departure),
                action=f"前往{destination_label}",
                place=place["name"],
                description=f"预计通勤 {leg.duration_min} 分钟。",
                source=place.get("source", "mock"),
            ),
            PlanStep(
                time=_format_time(arrival),
                action=action,
                place=place["name"],
                description=f"安排约 {duration} 分钟。",
                source=place.get("source", "mock"),
            ),
        ])
        current_end = finish
        offline_index += 1

    return_start = current_end
    home_arrival = return_start + final_return.duration_min
    items.extend([
        TimelineItem(
            time=_format_time(return_start),
            type="return",
            title="结束并返回",
            description=f"预计返程 {final_return.duration_min} 分钟",
        ),
        TimelineItem(
            time=_format_time(home_arrival),
            type="arrival",
            title="行程结束",
            description=f"返回{_origin_name(location)}。",
        ),
    ])
    steps.append(
        PlanStep(
            time=_format_time(home_arrival),
            action="行程结束",
            description=f"返回{_origin_name(location)}。",
        )
    )

    first_time = min(_parse_time(item.time) for item in items)
    timeline = Timeline(
        items=items,
        total_duration_minutes=home_arrival - first_time,
    )
    plan = ActivityPlan(
        summary="中午点餐、下午活动、晚上放松的多阶段计划",
        steps=steps,
        reasons=[
            "按用户表达的时间顺序安排各阶段",
            "外卖点餐不占用线下路线",
            "线下活动和酒吧按顺序规划通勤",
        ],
    )
    return MultiStepItinerary(
        plan=plan,
        route=route_plan,
        timeline=timeline,
        actions=actions,
    )


def _resolve_routes(
    location: ResolvedLocation,
    places: list[dict],
    route_legs: list[RouteEstimate] | None,
    return_leg: RouteEstimate | None,
) -> tuple[list[RouteEstimate], RouteEstimate]:
    if route_legs is not None and return_leg is not None:
        return route_legs, return_leg

    legs = []
    previous_id = location.location_id
    previous: ResolvedLocation | dict = location
    for place in places:
        leg = estimate_route(
            previous_id,
            place["id"],
            previous,
            place,
        )
        legs.append(leg)
        previous_id = place["id"]
        previous = place

    final_return = estimate_route(
        previous_id,
        location.location_id,
        previous,
        location.model_dump(mode="python"),
    )
    return legs, final_return


def _previous_place_name(
    location: ResolvedLocation,
    places: list[dict],
    offline_index: int,
) -> str:
    if offline_index == 0:
        return _origin_name(location)
    return places[offline_index - 1]["name"]


def _time_anchor(time_window: str) -> int:
    for label, minutes in TIME_ANCHORS.items():
        if label in time_window:
            return minutes
    return 14 * 60


def _task_duration(task_type: str, place: dict) -> int:
    default = 120 if task_type in {"activity_search", "bar_visit"} else 90
    return int(place.get("avg_duration_min", default))


def _origin_name(location: ResolvedLocation) -> str:
    if location.source == "demo_default":
        return "默认位置：上海徐汇"
    return location.address


def _format_time(total_minutes: int) -> str:
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours:02d}:{minutes:02d}"


def _parse_time(value: str) -> int:
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)
