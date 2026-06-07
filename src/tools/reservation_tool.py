"""Mock restaurant reservation tool."""

from datetime import datetime
import uuid

from src.config.settings import current_demo_scenario, load_json, settings
from src.schemas.models import ActionResult, UserIntent


def reserve_restaurant(
    restaurant: dict,
    requested_time: str,
    intent: UserIntent,
) -> ActionResult:
    """Reserve an available local-data slot, using the nearest later slot as fallback."""
    if current_demo_scenario() == "restaurant_full":
        return ActionResult(
            type="reservation",
            target=restaurant.get("name", "餐厅"),
            status="mock_failed",
            message="预计到达时段暂无可预约座位",
            details={
                "reason": "restaurant_full",
                "requested_time": requested_time,
                "source": "mock_demo_scenario",
            },
        )

    if restaurant.get("source") == "amap":
        if not restaurant.get("reservation_available", False):
            return ActionResult(
                type="reservation",
                target=restaurant.get("name", "餐厅"),
                status="mock_failed",
                message="该真实地点仅使用 Mock 商户能力，当前模拟为不可预约。",
                details={
                    "source": "mock_local_commerce",
                    "execution_source": _execution_source(),
                },
            )
        return _mock_amap_reservation(restaurant, requested_time, intent)

    slots = [
        item
        for item in load_json("availability.json").get("availability", [])
        if item.get("restaurant_id") == restaurant.get("restaurant_id")
        and item.get("available")
        and item.get("remaining_tables", 0) > 0
    ]
    slots.sort(key=lambda item: item.get("time", "99:99"))

    chosen = next((slot for slot in slots if slot.get("time") == requested_time), None)
    if chosen is None:
        chosen = next((slot for slot in slots if slot.get("time", "") >= requested_time), None)
    if chosen is None and slots:
        chosen = slots[-1]

    if chosen is None:
        return ActionResult(
            type="reservation",
            target=restaurant.get("name", "餐厅"),
            status="mock_failed",
            message="Mock 数据中没有可用餐位，建议现场取号。",
        )

    reservation_id = f"MOCK-RESV-{uuid.uuid4().hex[:8].upper()}"
    note_parts = []
    if intent.child_age is not None:
        note_parts.append(f"{intent.child_age}岁儿童同行")
    if {"减脂", "清淡", "低油"} & set(intent.diet_preferences):
        note_parts.append("优先安排清淡低脂菜品")

    return ActionResult(
        type="reservation",
        target=restaurant.get("name", "餐厅"),
        status="mock_success",
        message=f"已模拟预约 {chosen['time']} 的 {intent.party_size} 人位。",
        details={
            "reservation_id": reservation_id,
            "execution_source": _execution_source(),
            "time": chosen["time"],
            "party_size": intent.party_size,
            "note": "；".join(note_parts),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        },
    )


def _mock_amap_reservation(
    restaurant: dict,
    requested_time: str,
    intent: UserIntent,
) -> ActionResult:
    note_parts = []
    if intent.child_age is not None:
        note_parts.append(f"{intent.child_age}岁儿童同行")
    if {"减脂", "清淡", "低油"} & set(intent.diet_preferences):
        note_parts.append("优先安排清淡低脂菜品")
    return ActionResult(
        type="reservation",
        target=restaurant.get("name", "餐厅"),
        status="mock_success",
        message=f"已通过 Mock Local Commerce 模拟预约 {requested_time} 的 {intent.party_size} 人位。",
        details={
            "reservation_id": f"MOCK-AMAP-{uuid.uuid4().hex[:8].upper()}",
            "time": requested_time,
            "party_size": intent.party_size,
            "note": "；".join(note_parts),
            "source": "mock_local_commerce",
            "execution_source": _execution_source(),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        },
    )


def _execution_source() -> str:
    if settings.run_mode == "live" and not settings.use_mock_actions:
        return "mock_fallback"
    return "mock"
