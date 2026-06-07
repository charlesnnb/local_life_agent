"""Detect plan exceptions without mutating the current itinerary."""

from datetime import datetime, timedelta
import re
import uuid

from src.schemas.models import (
    PlanException,
    PlanResponse,
    ToolExecutionResult,
)


def detect_exceptions(
    plan: PlanResponse,
    tool_results: list[ToolExecutionResult] | None = None,
    *,
    scenario: str = "normal",
    activity_reason: str = "sold_out",
    traffic_delay_minutes: int = 25,
) -> list[PlanException]:
    """Return uniform exceptions while leaving the submitted plan unchanged."""
    results = tool_results or []
    exceptions: list[PlanException] = []

    restaurant_exception = _restaurant_exception(plan, results, scenario)
    if restaurant_exception is not None:
        exceptions.append(restaurant_exception)

    if scenario == "activity_unavailable":
        activity_exception = _activity_exception(
            plan,
            results,
            activity_reason,
        )
        if activity_exception is not None:
            exceptions.append(activity_exception)

    if scenario == "traffic_delay":
        traffic_exception = _traffic_exception(
            plan,
            results,
            traffic_delay_minutes,
        )
        if traffic_exception is not None:
            exceptions.append(traffic_exception)

    return exceptions


def _restaurant_exception(
    plan: PlanResponse,
    tool_results: list[ToolExecutionResult],
    scenario: str,
) -> PlanException | None:
    reservation = next(
        (
            action
            for action in plan.actions
            if action.type == "reservation"
            and (
                action.status == "mock_failed"
                or action.details.get("reason") == "restaurant_full"
            )
        ),
        None,
    )
    if reservation is None and scenario != "restaurant_full":
        return None
    if reservation is None:
        reservation = next(
            (
                action
                for action in plan.actions
                if action.type == "reservation"
            ),
            None,
        )
    if reservation is None:
        return None

    result = _result_for_task_type(plan, tool_results, "restaurant_search")
    selected = (result.selected_result if result else None) or {}
    requested_time = str(
        reservation.details.get("requested_time")
        or reservation.details.get("time")
        or ""
    )
    wait_minutes = (
        70
        if scenario == "restaurant_full"
        else int(selected.get("wait_time_min", 70))
    )
    return PlanException(
        exception_id=_id("restaurant"),
        exception_type="restaurant_full",
        source_task_id=result.task_id if result else None,
        severity="high",
        title="首选餐厅当前无可预约座位",
        message=(
            reservation.message
            or f"{reservation.target}预计到达时段暂无可预约座位"
        ),
        impact={
            "reason": "restaurant_full",
            "old_place": selected or {"name": reservation.target},
            "old_place_name": reservation.target,
            "requested_time": requested_time,
            "wait_minutes": wait_minutes,
            "summary": (
                f"保留原餐厅预计等待 {wait_minutes} 分钟，"
                "可能推迟后续安排。"
            ),
            "mock": True,
        },
    )


def _activity_exception(
    plan: PlanResponse,
    tool_results: list[ToolExecutionResult],
    reason: str,
) -> PlanException | None:
    result = _result_for_task_type(plan, tool_results, "poi_search")
    if result is None or not result.selected_result:
        return None
    selected = result.selected_result
    reason_text = "已售罄" if reason == "sold_out" else "场馆临时关闭"
    return PlanException(
        exception_id=_id("activity"),
        exception_type="activity_unavailable",
        source_task_id=result.task_id,
        severity="high",
        title=f"原定活动{reason_text}",
        message=f"{selected.get('name', '原定活动')}{reason_text}，当前无法执行。",
        impact={
            "reason": reason,
            "available": False,
            "old_place": selected,
            "old_place_name": selected.get("name", "原定活动"),
            "child_age": plan.user_intent.child_age,
            "scene": plan.user_intent.scene,
            "summary": "原活动不能按计划入场，需要选择同类备选。",
            "mock": True,
        },
    )


def _traffic_exception(
    plan: PlanResponse,
    tool_results: list[ToolExecutionResult],
    delay_minutes: int,
) -> PlanException | None:
    reservation = next(
        (action for action in plan.actions if action.type == "reservation"),
        None,
    )
    restaurant_item = next(
        (item for item in plan.timeline.items if item.type == "restaurant"),
        None,
    )
    if reservation is None or restaurant_item is None:
        return None
    explicit_time = _explicit_time(plan.user_intent.raw_query)
    reservation_time = str(
        explicit_time
        or reservation.details.get("requested_time")
        or reservation.details.get("time")
        or restaurant_item.time
    )
    original_arrival = (
        _add_minutes(reservation_time, -10)
        if explicit_time
        else restaurant_item.time
    )
    latest_arrival = _add_minutes(original_arrival, delay_minutes)
    if latest_arrival <= reservation_time:
        return None
    result = _result_for_task_type(plan, tool_results, "restaurant_search")
    return PlanException(
        exception_id=_id("traffic"),
        exception_type="schedule_conflict",
        source_task_id=result.task_id if result else None,
        severity="high",
        title="路线拥堵，预约时间可能冲突",
        message=f"检测到路线拥堵，预计迟到 {delay_minutes} 分钟。",
        impact={
            "reason": "traffic_jam",
            "delay_minutes": delay_minutes,
            "original_arrival": original_arrival,
            "latest_arrival": latest_arrival,
            "reservation_time": reservation_time,
            "old_place": (result.selected_result if result else None) or {
                "name": reservation.target
            },
            "old_place_name": reservation.target,
            "summary": (
                f"最新预计 {latest_arrival} 到达，"
                f"原 {reservation_time} 预约可能失效。"
            ),
            "mock": True,
        },
    )


def _result_for_task_type(
    plan: PlanResponse,
    tool_results: list[ToolExecutionResult],
    task_type: str,
) -> ToolExecutionResult | None:
    if plan.task_plan is None:
        return None
    task_ids = {
        task.task_id
        for task in plan.task_plan.tasks
        if task.task_type == task_type
    }
    return next(
        (result for result in tool_results if result.task_id in task_ids),
        None,
    )


def _add_minutes(value: str, minutes: int) -> str:
    parsed = datetime.strptime(value, "%H:%M")
    return (parsed + timedelta(minutes=minutes)).strftime("%H:%M")


def _explicit_time(query: str) -> str | None:
    match = re.search(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)", query)
    if match is None:
        return None
    return f"{int(match.group(1)):02d}:{match.group(2)}"


def _id(prefix: str) -> str:
    return f"exception_{prefix}_{uuid.uuid4().hex[:10]}"
