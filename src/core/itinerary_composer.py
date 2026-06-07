"""Compose ordered tasks and tool results into one executable itinerary."""

from src.core.task_category import category_label, normalize_task_category
from src.providers.amap_provider import AmapProvider
from src.schemas.models import (
    ActionResult,
    ActivityPlan,
    MultiStepItinerary,
    PlanStep,
    ResolvedLocation,
    RouteOrigin,
    RoutePlan,
    TaskPlan,
    Timeline,
    TimelineItem,
    ToolExecutionResult,
    UserIntent,
)
from src.tools.reservation_tool import reserve_restaurant
from src.tools.route_tool import build_ordered_route_plan, estimate_route


TIME_ANCHORS = {
    "早上": 8 * 60,
    "上午": 9 * 60 + 30,
    "中午": 12 * 60,
    "下午": 14 * 60,
    "傍晚": 18 * 60,
    "晚上": 19 * 60 + 30,
    "夜宵": 22 * 60,
}


def compose_itinerary(
    intent: UserIntent,
    task_plan: TaskPlan,
    tool_results: list[ToolExecutionResult],
    location: ResolvedLocation,
    amap_provider: AmapProvider | None = None,
) -> MultiStepItinerary:
    """Build route, timeline, actions, and warnings without calling search tools."""
    results_by_task = {result.task_id: result for result in tool_results}
    places = _route_places(task_plan, results_by_task)
    route_plan, route_legs, return_leg = _build_route(
        location,
        places,
        amap_provider,
    )
    leg_by_task = {
        place["task_id"]: leg
        for place, leg in zip(places, route_legs, strict=True)
    }

    items: list[TimelineItem] = []
    steps: list[PlanStep] = []
    actions: list[ActionResult] = []
    warnings = _schedule_warnings(task_plan)
    warnings.extend(
        constraint
        for task in task_plan.tasks
        for constraint in task.constraints
    )
    current_end = 0
    previous_place = _origin_name(location)
    offline_index = 0

    for task in task_plan.tasks:
        result = results_by_task.get(task.task_id)
        anchor = _time_anchor(task.time_window)
        if result is None or result.status == "failed":
            warning = (
                f"{task.description}未找到可执行结果，任务已保留，"
                "请稍后重试或手动选择地点。"
            )
            warnings.append(warning)
            steps.append(
                PlanStep(
                    time=_format_time(anchor),
                    action="待确认",
                    place=task.target,
                    description=warning,
                )
            )
            pending_time = current_end or anchor
            items.append(
                TimelineItem(
                    time=_format_time(pending_time),
                    type="break",
                    title=f"{task.time_window}{category_label(normalize_task_category(task))}任务待确认",
                    description=(
                        f"{warning} 这段时间暂作为自由安排。"
                    ),
                )
            )
            continue

        if task.task_type == "food_delivery":
            action = ActionResult.model_validate(result.selected_result)
            actions.append(action)
            order_time = max(anchor, current_end)
            _append_gap_explanation(items, current_end, order_time, task.description)
            delivery_time = order_time + int(
                action.details.get("estimated_delivery_minutes", 30)
            )
            items.extend([
                TimelineItem(
                    time=_format_time(order_time),
                    type="food_order",
                    title=f"{task.time_window}点{task.target or '餐食'}",
                    description=action.message or "已模拟完成外卖点餐。",
                ),
                TimelineItem(
                    time=_format_time(delivery_time),
                    type="delivery",
                    title=f"{task.target or '餐食'}预计送达",
                    description="外卖送到当前位置，不加入线下路线。",
                ),
            ])
            steps.append(
                PlanStep(
                    time=_format_time(order_time),
                    action="点餐",
                    place=task.target,
                    description=action.message or "已模拟完成外卖点餐。",
                    source="mock",
                )
            )
            current_end = delivery_time
            continue

        place = result.selected_result or {}
        leg = leg_by_task.get(task.task_id)
        if leg is None:
            continue
        departure = max(anchor, current_end)
        _append_gap_explanation(items, current_end, departure, task.description)
        arrival = departure + leg.duration_min
        duration = _task_duration(task.task_type, place)
        finish = arrival + duration
        category = normalize_task_category(task)
        item_type = _timeline_type(task.task_type, category)
        action_label = _action_label(task.task_type, task.target, category)

        items.extend([
            TimelineItem(
                time=_format_time(departure),
                type="departure" if offline_index == 0 else "transfer",
                title=f"前往{place.get('name', task.target or '目的地')}",
                description=(
                    f"从{previous_place}出发，预计 {leg.duration_min} 分钟"
                ),
            ),
            TimelineItem(
                time=_format_time(arrival),
                type=item_type,
                title=f"到达{place.get('name', task.target or '目的地')}",
                description=f"{task.description}，安排约 {duration} 分钟。",
            ),
        ])
        steps.extend([
            PlanStep(
                time=_format_time(departure),
                action="前往",
                place=place.get("name"),
                description=f"预计通勤 {leg.duration_min} 分钟。",
                source=place.get("source", "mock"),
            ),
            PlanStep(
                time=_format_time(arrival),
                action=action_label,
                place=place.get("name"),
                description=f"{task.description}，安排约 {duration} 分钟。",
                source=place.get("source", "mock"),
            ),
        ])
        if task.task_type == "restaurant_search":
            actions.append(
                reserve_restaurant(place, _format_time(arrival), intent)
            )
        previous_place = place.get("name", previous_place)
        current_end = finish
        offline_index += 1

    if places and return_leg is not None:
        return_start = current_end
        home_arrival = return_start + return_leg.duration_min
        items.extend([
            TimelineItem(
                time=_format_time(return_start),
                type="return",
                title="结束并返回",
                description=f"预计返程 {return_leg.duration_min} 分钟。",
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
        current_end = home_arrival

    if not items:
        items.append(
            TimelineItem(
                time="12:00",
                type="break",
                title="暂无可执行任务",
                description="任务规划未产生可执行结果。",
            )
        )
    items.sort(key=lambda item: _parse_time(item.time))
    steps.sort(key=lambda step: _parse_time(step.time))
    first_time = min(_parse_time(item.time) for item in items)
    last_time = max(_parse_time(item.time) for item in items)
    summary_targets = "、".join(
        task.target or task.description for task in task_plan.tasks
    )
    plan = ActivityPlan(
        summary=f"按任务安排：{summary_targets}",
        steps=steps,
        reasons=[
            "按用户原始表达保留全部任务和时间顺序",
            "外卖任务不进入线下路线",
            "线下地点由对应任务的工具结果决定",
        ],
    )
    return MultiStepItinerary(
        plan=plan,
        route=route_plan,
        timeline=Timeline(
            items=items,
            total_duration_minutes=max(0, last_time - first_time),
        ),
        actions=actions,
        warnings=list(dict.fromkeys(warnings)),
    )


def _route_places(
    task_plan: TaskPlan,
    results: dict[str, ToolExecutionResult],
) -> list[dict]:
    places = []
    for task in task_plan.tasks:
        result = results.get(task.task_id)
        if (
            not task.route_needed
            or result is None
            or result.status != "success"
            or not result.selected_result
        ):
            continue
        place = dict(result.selected_result)
        if place.get("lat") is None or place.get("lng") is None:
            continue
        place["task_id"] = task.task_id
        place["task_type"] = task.task_type
        place["task_category"] = normalize_task_category(task)
        place["route_label"] = category_label(place["task_category"])
        places.append(place)
    return places


def _build_route(
    location: ResolvedLocation,
    places: list[dict],
    amap_provider: AmapProvider | None,
):
    if not places:
        return (
            RoutePlan(
                origin=RouteOrigin(
                    name=_origin_name(location),
                    lat=location.lat,
                    lng=location.lng,
                ),
                stops=[],
                return_to_origin_minutes=0,
                total_travel_minutes=0,
                source="mock",
            ),
            [],
            None,
        )

    legs = []
    previous_id = location.location_id
    previous: ResolvedLocation | dict = location
    for place in places:
        leg = estimate_route(
            previous_id,
            place["id"],
            previous,
            place,
            amap_provider,
        )
        legs.append(leg)
        previous_id = place["id"]
        previous = place
    return_leg = estimate_route(
        previous_id,
        location.location_id,
        previous,
        location.model_dump(mode="python"),
        amap_provider,
    )
    return (
        build_ordered_route_plan(location, places, legs, return_leg),
        legs,
        return_leg,
    )


def _schedule_warnings(task_plan: TaskPlan) -> list[str]:
    afternoon_active = [
        task
        for task in task_plan.tasks
        if "下午" in task.time_window
        and task.task_type in {"poi_search", "bar_visit", "hotel_search"}
    ]
    low_energy = task_plan.constraints.get("energy_level") == "low"
    if len(afternoon_active) >= 2 and low_energy:
        targets = "和".join(
            task.target or task.description for task in afternoon_active
        )
        return [
            f"你今天精力偏低，下午同时安排{targets}可能偏赶；"
            f"建议主方案保留{afternoon_active[0].target}，"
            f"将{afternoon_active[1].target}作为备选或二选一。"
        ]
    return []


def _timeline_type(task_type: str, category: str) -> str:
    if category == "bar":
        return "bar"
    if category == "hotel_lounge":
        return "hotel"
    if category == "restaurant":
        return "restaurant"
    return {
        "restaurant_search": "restaurant",
        "bar_visit": "bar",
        "hotel_search": "hotel",
    }.get(task_type, "activity")


def _action_label(
    task_type: str,
    target: str | None,
    category: str,
) -> str:
    legacy_labels = {
        "restaurant_search": "晚餐",
        "bar_visit": "酒吧放松",
        "hotel_search": "酒店放松",
    }
    if task_type in legacy_labels:
        return legacy_labels[task_type]
    if category not in {"unknown", "food_delivery"}:
        return category_label(category)
    return (
        "亲子活动"
        if target == "亲子活动"
        else "活动" if target == "休闲活动" else target or "活动"
    )


def _task_duration(task_type: str, place: dict) -> int:
    defaults = {
        "restaurant_search": 70,
        "bar_visit": 120,
        "hotel_search": 120,
        "poi_search": 90,
    }
    return int(place.get("avg_duration_min", defaults.get(task_type, 90)))


def _time_anchor(time_window: str) -> int:
    for label, minutes in TIME_ANCHORS.items():
        if label in time_window:
            return minutes
    return 14 * 60


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


def _append_gap_explanation(
    items: list[TimelineItem],
    current_end: int,
    next_start: int,
    next_task: str,
) -> None:
    gap = next_start - current_end
    if current_end <= 0 or gap <= 45:
        return
    items.append(
        TimelineItem(
            time=_format_time(current_end),
            type="free_time",
            title="自由安排",
            description=(
                f"距离“{next_task}”还有约 {gap} 分钟，"
                "可休息、就近活动或提前出发。"
            ),
        )
    )
