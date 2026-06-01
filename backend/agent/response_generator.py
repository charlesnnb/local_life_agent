"""Final response generator: creates summary, share message, and complete output."""

from backend.data_loader import get_user


def generate_summary(scene: str, itinerary: list[dict], selected_poi: dict | None,
                     selected_restaurant: dict | None) -> str:
    """Generate a human-readable summary of the plan."""
    if scene == "family":
        return _family_summary(itinerary, selected_poi, selected_restaurant)
    else:
        return _friends_summary(itinerary, selected_poi, selected_restaurant)


def generate_share_message(
    scene: str,
    itinerary: list[dict],
    selected_poi: dict | None,
    selected_restaurant: dict | None,
    completed_actions: list[dict],
    constraints: dict,
) -> str:
    """Generate a shareable message for family/friends chat."""
    if scene == "family":
        return _family_share_message(itinerary, selected_poi, selected_restaurant,
                                     completed_actions, constraints)
    else:
        return _friends_share_message(itinerary, selected_poi, selected_restaurant,
                                      completed_actions, constraints)


def generate_full_response(
    scene: str,
    constraints: dict,
    planning_trace: list[dict],
    tool_calls: list[dict],
    itinerary: list[dict],
    completed_actions: list[dict],
    fallback_actions: list[dict],
    selected_poi: dict | None,
    selected_restaurant: dict | None,
    plan_score: float,
    total_time_min: int,
) -> dict:
    """Assemble the complete response."""
    summary = generate_summary(scene, itinerary, selected_poi, selected_restaurant)
    share_message = generate_share_message(
        scene, itinerary, selected_poi, selected_restaurant,
        completed_actions, constraints,
    )

    status = "success"
    if fallback_actions:
        has_required_fallback = any(
            "reservation" in str(f) or "ticket_order" in str(f)
            for f in fallback_actions
        )
        if has_required_fallback:
            status = "partial"

    return {
        "status": status,
        "scene": scene,
        "summary": summary,
        "constraints": constraints,
        "planning_trace": planning_trace,
        "tool_calls": tool_calls,
        "itinerary": itinerary,
        "completed_actions": completed_actions,
        "fallback_actions": fallback_actions,
        "share_message": share_message,
        "plan_score": plan_score,
        "total_time_min": total_time_min,
    }


def _family_summary(itinerary, poi, restaurant) -> str:
    poi_name = poi["name"] if poi else "活动地点"
    rest_name = restaurant["name"] if restaurant else "餐厅"
    home_time = itinerary[-1]["time_end"] if itinerary else "18:20"

    return (
        f"推荐方案：亲子轻松下午路线\n\n"
        f"下午从家出发，前往{poi_name}游玩，"
        f"随后前往{rest_name}享用晚餐，"
        f"预计{home_time}左右到家。"
        f"已为您自动完成门票购买、餐厅预约和打车订单。"
    )


def _friends_summary(itinerary, poi, restaurant) -> str:
    poi_name = poi["name"] if poi else "活动地点"
    rest_name = restaurant["name"] if restaurant else "餐厅"
    home_time = itinerary[-1]["time_end"] if itinerary else "19:40"

    return (
        f"推荐方案：轻社交朋友下午路线\n\n"
        f"下午出发，前往{poi_name}，"
        f"随后前往{rest_name}享用晚餐，"
        f"预计{home_time}左右自由返程。"
        f"已为您自动完成门票购买、餐厅预约和打车订单。"
    )


def _family_share_message(itinerary, poi, restaurant, actions, constraints) -> str:
    poi_name = poi["name"] if poi else "活动地点"
    rest_name = restaurant["name"] if restaurant else "餐厅"
    start_time = constraints.get("start_time", "14:00")
    home_time = itinerary[-1]["time_end"] if itinerary else "18:20"

    has_low_fat = restaurant.get("has_low_fat_meal") if restaurant else False
    has_kids = restaurant.get("has_kids_meal") if restaurant else False
    party_size = constraints.get("party_size", 3)

    parts = [
        f"搞定了，下午 {start_time[:2]} 点出发，先去{poi_name}，",
        f"孩子能玩一个多小时；"
        f"下午5点左右去{rest_name}吃饭，我已经约好了 {party_size} 人位",
    ]
    if has_low_fat and has_kids:
        parts.append("，有低脂套餐和儿童餐")
    elif has_low_fat:
        parts.append("，有低脂套餐")
    elif has_kids:
        parts.append("，有儿童餐")

    # Check for cake order
    has_cake = any("cake" in str(a) or "extra" in str(a) for a in actions)
    if has_cake:
        parts.append("；饭后顺路取低糖蛋糕")

    parts.append(f"，预计 {home_time[:2]} 点多到家。")
    return "".join(parts)


def _friends_share_message(itinerary, poi, restaurant, actions, constraints) -> str:
    poi_name = poi["name"] if poi else "活动地点"
    rest_name = restaurant["name"] if restaurant else "餐厅"
    start_time = constraints.get("start_time", "14:30")
    home_time = itinerary[-1]["time_end"] if itinerary else "19:40"
    party_size = constraints.get("party_size", 4)

    return (
        f"搞定了，下午 {start_time[:2]}:{start_time[3:]} 出发，先去{poi_name}，大概玩到4点多；"
        f"然后去附近逛一下，下午6点去{rest_name}吃饭，我已经约了 {party_size} 人位。"
        f"全程打车20分钟左右，适合拍照聊天，不会太累。"
        f"预计 {home_time[:2]} 点多自由返程。"
    )
