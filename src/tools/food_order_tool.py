"""Mock food ordering for multi-stage plans."""

from src.config.settings import settings
from src.schemas.models import ActionResult


def order_food(
    brand: str,
    time_window: str,
    location: str,
) -> ActionResult:
    """Return a simulated delivery result without placing a real order."""
    estimated_delivery_minutes = 30
    return ActionResult(
        type="food_order",
        target=brand,
        status="mock_success",
        message=(
            f"已模拟为你下单{brand}，预计 "
            f"{estimated_delivery_minutes} 分钟送达"
        ),
        details={
            "tool_name": "food_order_tool",
            "action": "order_food",
            "execution_source": _execution_source(),
            "brand": brand,
            "time_window": time_window,
            "location": location,
            "estimated_delivery_minutes": estimated_delivery_minutes,
        },
    )


def _execution_source() -> str:
    if settings.run_mode == "live" and not settings.use_mock_actions:
        return "mock_fallback"
    return "mock"
