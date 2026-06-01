"""Action executor: runs tool calls and manages fallbacks."""

import copy
from backend.tools.order_tools import (
    create_ticket_order,
    create_restaurant_reservation,
    create_flower_or_cake_order,
    create_ride_order,
)
from backend.tools.message_tools import send_plan_message, search_services


def execute_actions(
    user_id: str,
    scene: str,
    itinerary: list[dict],
    selected_poi: dict | None,
    selected_restaurant: dict | None,
    constraints: dict,
    share_message: str,
) -> dict:
    """Execute all required and optional actions for the plan.

    Returns dict with completed_actions, fallback_actions, and tool_calls log.
    """
    completed = []
    fallbacks = []
    tool_calls = []

    party_size = constraints.get("party_size", 3)
    transport = constraints.get("transport", "taxi")
    child_age = constraints.get("child_age")

    # Find key time points from itinerary
    activity_start = _find_item_time(itinerary, "activity")
    meal_time = _find_item_time(itinerary, "meal")
    return_time = _find_item_time(itinerary, "return")

    # 1. Ticket order (required for family, optional for friends)
    if selected_poi and selected_poi.get("requires_ticket"):
        adult_count = constraints.get("party_size", 3) - (1 if child_age else 0)
        child_count = 1 if child_age else 0
        tc = _exec_with_fallback(
            "create_ticket_order",
            lambda: create_ticket_order(
                poi_id=selected_poi["poi_id"],
                user_id=user_id,
                adult_count=max(1, adult_count),
                child_count=child_count,
                time=activity_start or constraints["start_time"],
            ),
            required=True,
        )
        tool_calls.append(tc)
        if tc["success"]:
            completed.append({"type": "ticket_order", "result": tc["output"]["data"]})
        else:
            fallbacks.append({
                "type": "ticket_order_fallback",
                "reason": tc["message"],
                "suggestion": "建议手动购票或换其他活动",
            })

    # 2. Restaurant reservation (required)
    if selected_restaurant:
        meal_note = ""
        if scene == "family" and selected_restaurant.get("has_kids_meal"):
            meal_note = "需要儿童座椅"
        if child_age and not selected_restaurant.get("has_kids_meal"):
            meal_note = "孩子5岁，请安排合适位置"

        tc = _exec_with_fallback(
            "create_restaurant_reservation",
            lambda: create_restaurant_reservation(
                restaurant_id=selected_restaurant["restaurant_id"],
                user_id=user_id,
                time=meal_time or "17:00",
                party_size=party_size,
                note=meal_note,
            ),
            required=True,
        )
        tool_calls.append(tc)
        if tc["success"]:
            completed.append({"type": "restaurant_reservation", "result": tc["output"]["data"]})
        else:
            fallbacks.append({
                "type": "reservation_fallback",
                "reason": tc["message"],
                "suggestion": "建议换时间或换餐厅",
            })

    # 3. Extra service (cake/flower for family, coffee/dessert for friends)
    extra_type = None
    if scene == "family":
        extra_type = "cake"
    else:
        extra_type = "coffee"

    extra_services = search_services(service_type=extra_type)
    if extra_services["success"] and extra_services["data"]:
        svc = extra_services["data"][0]
        pickup_time = _find_item_time(itinerary, "extra") or meal_time or "17:40"
        tc = _exec_with_fallback(
            "create_flower_or_cake_order",
            lambda: create_flower_or_cake_order(
                service_id=svc["service_id"],
                user_id=user_id,
                pickup_time=pickup_time,
            ),
            required=False,
        )
        tool_calls.append(tc)
        if tc["success"]:
            completed.append({"type": "extra_service_order", "result": tc["output"]["data"]})
        else:
            fallbacks.append({
                "type": "extra_service_skipped",
                "reason": tc["message"],
                "suggestion": f"可手动购买{extra_type}",
            })

    # 4. Ride orders (optional)
    home_id = f"home_{user_id}"
    for item in itinerary:
        if item["type"] in ("travel", "return"):
            from_loc = home_id if item == itinerary[0] else _prev_location(itinerary, item)
            to_loc = item.get("location_id") or home_id
            tc = _exec_with_fallback(
                "create_ride_order",
                lambda: create_ride_order(
                    user_id=user_id,
                    from_loc=from_loc,
                    to_loc=to_loc,
                    departure_time=item["time_start"],
                ),
                required=False,
            )
            tool_calls.append(tc)
            if tc["success"]:
                completed.append({"type": "ride_order", "result": tc["output"]["data"]})
            else:
                fallbacks.append({
                    "type": "ride_fallback",
                    "reason": tc["message"],
                    "suggestion": "建议手动打车",
                })

    # 5. Send plan message (required)
    tc = _exec_with_fallback(
        "send_plan_message",
        lambda: send_plan_message(
            user_id=user_id,
            to="家人" if scene == "family" else "朋友群",
            channel="wechat",
            message=share_message,
        ),
        required=True,
    )
    tool_calls.append(tc)
    if tc["success"]:
        completed.append({"type": "send_message", "result": tc["output"]["data"]})
    else:
        fallbacks.append({
            "type": "message_fallback",
            "reason": tc["message"],
            "suggestion": f"可复制以下文本手动发送:\n{share_message}",
        })

    return {
        "completed_actions": completed,
        "fallback_actions": fallbacks,
        "tool_calls": tool_calls,
    }


def _exec_with_fallback(name: str, fn, required: bool = False) -> dict:
    """Execute a tool function with retry and fallback."""
    result = fn()
    if result.get("success"):
        return {
            "tool": name,
            "input": {},
            "output": result,
            "success": True,
            "message": result.get("message", "ok"),
        }

    # Retry once
    result2 = fn()
    if result2.get("success"):
        return {
            "tool": name,
            "input": {},
            "output": result2,
            "success": True,
            "message": result2.get("message", "ok (retry)"),
        }

    return {
        "tool": name,
        "input": {},
        "output": result2,
        "success": False,
        "message": result2.get("message", "failed"),
    }


def _find_item_time(itinerary: list[dict], item_type: str) -> str | None:
    for item in itinerary:
        if item["type"] == item_type:
            return item["time_start"]
    return None


def _prev_location(itinerary: list[dict], current: dict) -> str:
    idx = itinerary.index(current) if current in itinerary else -1
    if idx > 0:
        return itinerary[idx - 1].get("location_id", "unknown")
    return "unknown"
