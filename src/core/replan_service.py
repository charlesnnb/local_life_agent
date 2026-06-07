"""Generate consent-based alternatives and apply only confirmed changes."""

from datetime import datetime, timedelta
import math
import uuid

from src.schemas.models import (
    PlanException,
    PlanResponse,
    ReplanOption,
    ReplanProposal,
    ToolExecutionResult,
)


def build_replan_proposals(
    plan: PlanResponse,
    exceptions: list[PlanException],
    tool_results: list[ToolExecutionResult] | None = None,
) -> list[ReplanProposal]:
    """Build display-ready alternatives without changing the current plan."""
    results = tool_results or []
    proposals = []
    for exception in exceptions:
        if exception.exception_type == "restaurant_full":
            options = _restaurant_options(exception, results)
        elif exception.exception_type == "activity_unavailable":
            options = _activity_options(exception, results)
        elif exception.exception_type == "schedule_conflict":
            options = _traffic_options(exception, results)
        else:
            options = [_keep_option(exception)]
        proposals.append(
            ReplanProposal(
                proposal_id=f"proposal_{uuid.uuid4().hex[:10]}",
                exception=exception,
                options=options,
            )
        )
    return proposals


def apply_replan(
    current_plan: PlanResponse,
    proposal_id: str,
    option_id: str,
) -> PlanResponse:
    """Return a copied plan with exactly one confirmed option applied."""
    updated = current_plan.model_copy(deep=True)
    proposal = next(
        (
            item
            for item in updated.replan_proposals
            if item.proposal_id == proposal_id
        ),
        None,
    )
    if proposal is None:
        raise ValueError("未找到对应的重规划提案。")
    if proposal.status != "pending":
        raise ValueError("该重规划提案已经处理。")
    option = next(
        (item for item in proposal.options if item.option_id == option_id),
        None,
    )
    if option is None:
        raise ValueError("未找到对应的重规划选项。")

    if option.operation == "keep_original":
        proposal.status = "kept"
        proposal.selected_option_id = option.option_id
        proposal.exception.status = "acknowledged"
        _sync_exception_status(updated, proposal.exception)
        updated.planning_warnings.append(
            f"已选择保留原计划：{proposal.exception.title}"
        )
        return updated

    if option.operation in {"replace_restaurant", "replace_activity"}:
        _apply_place_replacement(updated, option)
    elif option.operation == "adjust_reservation":
        _apply_schedule_adjustment(updated, option)

    proposal.status = "accepted"
    proposal.selected_option_id = option.option_id
    proposal.exception.status = "resolved"
    _sync_exception_status(updated, proposal.exception)
    return updated


def _restaurant_options(
    exception: PlanException,
    results: list[ToolExecutionResult],
) -> list[ReplanOption]:
    old = exception.impact.get("old_place", {})
    alternative = _best_alternative(exception, results)
    options: list[ReplanOption] = []
    if alternative is not None:
        old_wait = int(exception.impact.get("wait_minutes", 70))
        new_wait = int(alternative.get("wait_time_min", 10))
        saved = max(0, old_wait - new_wait)
        options.append(
            ReplanOption(
                option_id=_option_id("restaurant"),
                title="切换到附近低等待餐厅",
                description=(
                    f"{alternative.get('name')}预计等待 {new_wait} 分钟，"
                    "并尽量保留菜系、预算和同行偏好。"
                ),
                changes=[
                    "替换餐厅地点",
                    "重新计算路线与时间线",
                    "更新模拟预约和分享消息",
                ],
                estimated_saved_minutes=saved,
                replacement_place=alternative,
                operation="replace_restaurant",
                original_plan=_place_summary(old, old_wait),
                proposed_plan=_place_summary(alternative, new_wait),
                metadata={
                    "old_place_name": exception.impact.get("old_place_name"),
                    "source_task_id": exception.source_task_id,
                    "travel_delta_minutes": _estimated_place_delay(
                        old,
                        alternative,
                    ),
                },
            )
        )
    options.append(
        ReplanOption(
            option_id=_option_id("keep"),
            title="保留原餐厅",
            description="不覆盖当前计划，改为现场排队或自行调整到店时间。",
            changes=["保留原路线、时间线和执行结果"],
            operation="keep_original",
            original_plan=_place_summary(
                old,
                int(exception.impact.get("wait_minutes", 70)),
            ),
            proposed_plan={"name": "保留原计划"},
            metadata={"old_place_name": exception.impact.get("old_place_name")},
        )
    )
    return options


def _activity_options(
    exception: PlanException,
    results: list[ToolExecutionResult],
) -> list[ReplanOption]:
    old = exception.impact.get("old_place", {})
    alternative = _best_alternative(exception, results)
    options: list[ReplanOption] = []
    if alternative is not None:
        delay = _estimated_place_delay(old, alternative)
        options.append(
            ReplanOption(
                option_id=_option_id("activity"),
                title="替换为同类可用活动",
                description=(
                    f"改去{alternative.get('name')}，"
                    "保留原活动类别和同行约束。"
                ),
                changes=[
                    "替换活动地点",
                    "重新计算路线与时间线",
                    "更新后续到达时间和分享消息",
                ],
                estimated_delay_minutes=delay,
                replacement_place=alternative,
                operation="replace_activity",
                original_plan=_place_summary(old),
                proposed_plan=_place_summary(alternative),
                metadata={
                    "old_place_name": exception.impact.get("old_place_name"),
                    "source_task_id": exception.source_task_id,
                },
            )
        )
    keep = _keep_option(exception)
    if alternative is None:
        keep.description = (
            "当前没有找到符合条件的替代活动，"
            "建议扩大距离或更换活动类型。"
        )
    options.append(keep)
    return options


def _traffic_options(
    exception: PlanException,
    results: list[ToolExecutionResult],
) -> list[ReplanOption]:
    impact = exception.impact
    delay = int(impact.get("delay_minutes", 25))
    latest_arrival = str(impact.get("latest_arrival"))
    new_time = _ceil_half_hour(latest_arrival)
    old = impact.get("old_place", {})
    options = [
        ReplanOption(
            option_id=_option_id("schedule"),
            title=f"将预约调整到 {new_time}",
            description="保留原餐厅，按拥堵后的预计到达时间调整模拟预约。",
            changes=[
                f"路线增加 {delay} 分钟",
                f"预约调整到 {new_time}",
                "顺延时间线和分享消息",
            ],
            estimated_delay_minutes=delay,
            operation="adjust_reservation",
            original_plan={
                "name": impact.get("old_place_name"),
                "arrival": impact.get("original_arrival"),
                "reservation_time": impact.get("reservation_time"),
            },
            proposed_plan={
                "name": impact.get("old_place_name"),
                "arrival": latest_arrival,
                "reservation_time": new_time,
            },
            metadata={
                "delay_minutes": delay,
                "new_time": new_time,
                "original_arrival": impact.get("original_arrival"),
                "latest_arrival": latest_arrival,
                "old_place_name": impact.get("old_place_name"),
            },
        )
    ]
    alternative = _best_alternative(exception, results)
    if alternative is not None:
        options.append(
            ReplanOption(
                option_id=_option_id("traffic_restaurant"),
                title="切换到附近低等待餐厅",
                description=(
                    f"改去{alternative.get('name')}，降低迟到和排队风险。"
                ),
                changes=[
                    "替换餐厅地点",
                    "重新计算路线与时间线",
                    "更新模拟预约和分享消息",
                ],
                estimated_saved_minutes=max(
                    0,
                    delay - int(alternative.get("wait_time_min", 10)),
                ),
                replacement_place=alternative,
                operation="replace_restaurant",
                original_plan=_place_summary(old),
                proposed_plan=_place_summary(alternative),
                metadata={
                    "old_place_name": impact.get("old_place_name"),
                    "source_task_id": exception.source_task_id,
                    "travel_delta_minutes": _estimated_place_delay(
                        old,
                        alternative,
                    ),
                },
            )
        )
    options.append(_keep_option(exception))
    return options


def _keep_option(exception: PlanException) -> ReplanOption:
    return ReplanOption(
        option_id=_option_id("keep"),
        title="保持原计划",
        description="不自动修改路线、时间线、执行结果或分享消息。",
        changes=["保留原计划并显示风险提醒"],
        operation="keep_original",
        original_plan={
            "name": exception.impact.get("old_place_name"),
            "summary": exception.impact.get("summary"),
        },
        proposed_plan={"name": "保留原计划"},
        metadata={"old_place_name": exception.impact.get("old_place_name")},
    )


def _best_alternative(
    exception: PlanException,
    results: list[ToolExecutionResult],
) -> dict | None:
    result = next(
        (
            item
            for item in results
            if item.task_id == exception.source_task_id
        ),
        None,
    )
    if result is None:
        return None
    old_name = exception.impact.get("old_place_name")
    alternatives = [
        dict(candidate)
        for candidate in result.candidates
        if candidate.get("name") != old_name
        and _matches_exception_constraints(candidate, exception)
    ]
    if not alternatives:
        return None
    alternatives.sort(
        key=lambda item: (
            int(item.get("wait_time_min", 15)),
            -float(item.get("rating", 0)),
            float(item.get("avg_price", item.get("price", 0)) or 0),
        )
    )
    return alternatives[0]


def _matches_exception_constraints(
    candidate: dict,
    exception: PlanException,
) -> bool:
    if exception.exception_type != "activity_unavailable":
        return True
    child_age = exception.impact.get("child_age")
    if child_age is None:
        return True
    age_range = candidate.get("age_range")
    if not isinstance(age_range, list) or len(age_range) < 2:
        return True
    try:
        return int(age_range[0]) <= int(child_age) <= int(age_range[1])
    except (TypeError, ValueError):
        return False


def _apply_place_replacement(
    plan: PlanResponse,
    option: ReplanOption,
) -> None:
    replacement = option.replacement_place or {}
    old_name = str(option.metadata.get("old_place_name") or "")
    new_name = str(replacement.get("name") or "")
    if not old_name or not new_name:
        raise ValueError("替代地点信息不完整。")
    stop_type = (
        "restaurant"
        if option.operation == "replace_restaurant"
        else "activity"
    )
    stop = next(
        (
            item
            for item in plan.route.stops
            if item.type == stop_type and item.name == old_name
        ),
        None,
    )
    if stop is None:
        raise ValueError("原计划中没有找到需要替换的地点。")
    old_minutes = stop.estimated_travel_minutes
    delay = (
        int(option.metadata.get("travel_delta_minutes", 0))
        if option.operation == "replace_restaurant"
        else option.estimated_delay_minutes
    )
    new_minutes = max(5, min(45, old_minutes + delay))
    stop.name = new_name
    stop.lat = float(replacement.get("lat", stop.lat))
    stop.lng = float(replacement.get("lng", stop.lng))
    stop.category = str(
        replacement.get("type")
        or replacement.get("task_category")
        or stop.category
    )
    stop.source = str(replacement.get("source", "mock"))
    stop.estimated_travel_minutes = new_minutes
    route_delta = new_minutes - old_minutes
    plan.route.total_travel_minutes = max(
        0,
        plan.route.total_travel_minutes + route_delta,
    )

    _replace_place_text(plan, old_name, new_name)
    if route_delta:
        _shift_timeline_from_place(plan, new_name, route_delta)
    if option.operation == "replace_restaurant":
        reservation = next(
            (
                action
                for action in plan.actions
                if action.type == "reservation"
            ),
            None,
        )
        if reservation is not None:
            reservation.target = new_name
            reservation.status = "mock_success"
            reservation.message = f"已为{new_name}完成模拟预约。"
            reservation.details.update({
                "source": "mock_replan",
                "reason": "accepted_replacement",
            })


def _apply_schedule_adjustment(
    plan: PlanResponse,
    option: ReplanOption,
) -> None:
    delay = int(option.metadata.get("delay_minutes", 0))
    new_time = str(option.metadata.get("new_time", ""))
    restaurant_stop = next(
        (stop for stop in plan.route.stops if stop.type == "restaurant"),
        None,
    )
    if restaurant_stop is not None:
        restaurant_stop.estimated_travel_minutes = min(
            45,
            restaurant_stop.estimated_travel_minutes + delay,
        )
    plan.route.total_travel_minutes += delay
    latest_arrival = str(option.metadata.get("latest_arrival") or "")
    if latest_arrival:
        _align_traffic_timeline(
            plan,
            latest_arrival,
            restaurant_stop.estimated_travel_minutes
            if restaurant_stop is not None
            else delay,
        )
        _align_traffic_steps(
            plan,
            option.metadata.get("old_place_name"),
            latest_arrival,
            restaurant_stop.estimated_travel_minutes
            if restaurant_stop is not None
            else delay,
        )
    else:
        _shift_timeline_from_type(plan, "restaurant", delay)
        _shift_plan_steps(plan, option.metadata.get("old_place_name"), delay)

    reservation = next(
        (
            action
            for action in plan.actions
            if action.type == "reservation"
        ),
        None,
    )
    if reservation is not None:
        reservation.status = "mock_success"
        reservation.message = (
            f"交通延误后已将模拟预约调整到 {new_time}。"
        )
        reservation.details.update({
            "time": new_time,
            "source": "mock_replan",
            "traffic_delay_minutes": delay,
        })
    _append_share_update(plan, f"交通延误后预约调整到 {new_time}")


def _replace_place_text(
    plan: PlanResponse,
    old_name: str,
    new_name: str,
) -> None:
    for step in plan.plan.steps:
        if step.place == old_name:
            step.place = new_name
        step.description = step.description.replace(old_name, new_name)
    for item in plan.timeline.items:
        item.title = item.title.replace(old_name, new_name)
        item.description = item.description.replace(old_name, new_name)
    for action in plan.actions:
        if action.type == "send_message":
            action.message = _replace_or_append(
                action.message,
                old_name,
                new_name,
                f"调整后改去{new_name}。",
            )
    if plan.composition is not None:
        plan.composition.share_message = _replace_or_append(
            plan.composition.share_message,
            old_name,
            new_name,
            f"调整后改去{new_name}。",
        )
    plan.natural_language = _replace_or_append(
        plan.natural_language,
        old_name,
        new_name,
        f"调整后改去{new_name}。",
    )


def _shift_timeline_from_place(
    plan: PlanResponse,
    place_name: str,
    delta: int,
) -> None:
    start = next(
        (
            index
            for index, item in enumerate(plan.timeline.items)
            if place_name in item.title or place_name in item.description
        ),
        len(plan.timeline.items),
    )
    for item in plan.timeline.items[start:]:
        item.time = _add_minutes(item.time, delta)


def _shift_timeline_from_type(
    plan: PlanResponse,
    item_type: str,
    delta: int,
) -> None:
    start = next(
        (
            index
            for index, item in enumerate(plan.timeline.items)
            if item.type == item_type
        ),
        len(plan.timeline.items),
    )
    for item in plan.timeline.items[start:]:
        item.time = _add_minutes(item.time, delta)


def _align_traffic_timeline(
    plan: PlanResponse,
    latest_arrival: str,
    travel_minutes: int,
) -> None:
    index = next(
        (
            item_index
            for item_index, item in enumerate(plan.timeline.items)
            if item.type == "restaurant"
        ),
        None,
    )
    if index is None:
        return
    old_arrival = plan.timeline.items[index].time
    shift = _time_delta(old_arrival, latest_arrival)
    for item in plan.timeline.items[index:]:
        item.time = _add_minutes(item.time, shift)
    if index > 0 and plan.timeline.items[index - 1].type in {
        "departure",
        "transfer",
    }:
        plan.timeline.items[index - 1].time = _add_minutes(
            latest_arrival,
            -travel_minutes,
        )
    timeline_minutes = [
        _time_to_minutes(item.time) for item in plan.timeline.items
    ]
    plan.timeline.total_duration_minutes = max(timeline_minutes) - min(
        timeline_minutes
    )


def _align_traffic_steps(
    plan: PlanResponse,
    place_name: object,
    latest_arrival: str,
    travel_minutes: int,
) -> None:
    indexes = [
        index
        for index, step in enumerate(plan.plan.steps)
        if step.place == place_name
    ]
    if not indexes:
        return
    arrival_index = indexes[-1]
    shift = _time_delta(
        plan.plan.steps[arrival_index].time,
        latest_arrival,
    )
    plan.plan.steps[indexes[0]].time = _add_minutes(
        latest_arrival,
        -travel_minutes,
    )
    plan.plan.steps[arrival_index].time = latest_arrival
    for step in plan.plan.steps[arrival_index + 1:]:
        step.time = _add_minutes(step.time, shift)


def _shift_plan_steps(
    plan: PlanResponse,
    place_name: object,
    delta: int,
) -> None:
    start = next(
        (
            index
            for index, step in enumerate(plan.plan.steps)
            if step.place == place_name
        ),
        len(plan.plan.steps),
    )
    for step in plan.plan.steps[start:]:
        step.time = _add_minutes(step.time, delta)


def _append_share_update(plan: PlanResponse, note: str) -> None:
    for action in plan.actions:
        if action.type == "send_message":
            action.message = f"{action.message or ''} {note}。".strip()
    if plan.composition is not None:
        plan.composition.share_message = (
            f"{plan.composition.share_message} {note}。".strip()
        )
    plan.natural_language = f"{plan.natural_language} {note}。".strip()


def _sync_exception_status(
    plan: PlanResponse,
    exception: PlanException,
) -> None:
    for item in plan.exceptions:
        if item.exception_id == exception.exception_id:
            item.status = exception.status


def _place_summary(place: dict, wait_minutes: int | None = None) -> dict:
    summary = {
        "name": place.get("name"),
        "type": place.get("type") or place.get("task_category"),
        "distance_km": place.get("distance_km"),
        "wait_time_min": place.get("wait_time_min"),
    }
    if wait_minutes is not None:
        summary["wait_time_min"] = wait_minutes
    return {key: value for key, value in summary.items() if value is not None}


def _estimated_place_delay(old: dict, new: dict) -> int:
    try:
        lat_delta = float(new.get("lat")) - float(old.get("lat"))
        lng_delta = float(new.get("lng")) - float(old.get("lng"))
    except (TypeError, ValueError):
        return 8
    distance_hint = math.sqrt(lat_delta**2 + lng_delta**2)
    return max(1, min(15, round(distance_hint * 1000)))


def _replace_or_append(
    value: str | None,
    old: str,
    new: str,
    fallback: str,
) -> str:
    current = value or ""
    if old and old in current:
        return current.replace(old, new)
    return f"{current} {fallback}".strip()


def _ceil_half_hour(value: str) -> str:
    parsed = datetime.strptime(value, "%H:%M")
    if parsed.minute in {0, 30}:
        return parsed.strftime("%H:%M")
    add = 30 - (parsed.minute % 30)
    return (parsed + timedelta(minutes=add)).strftime("%H:%M")


def _add_minutes(value: str, minutes: int) -> str:
    parsed = datetime.strptime(value, "%H:%M")
    return (parsed + timedelta(minutes=minutes)).strftime("%H:%M")


def _time_delta(start: str, end: str) -> int:
    return _time_to_minutes(end) - _time_to_minutes(start)


def _time_to_minutes(value: str) -> int:
    parsed = datetime.strptime(value, "%H:%M")
    return parsed.hour * 60 + parsed.minute


def _option_id(prefix: str) -> str:
    return f"option_{prefix}_{uuid.uuid4().hex[:10]}"
