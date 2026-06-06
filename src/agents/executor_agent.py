"""Execute the two MVP actions: restaurant reservation and message delivery."""

from collections.abc import Callable

from src.schemas.models import ActionResult, ActivityPlan, PlanEvent, UserIntent
from src.tools.message_tool import (
    build_share_message,
    message_target,
    send_message,
)
from src.tools.reservation_tool import reserve_restaurant

EventCallback = Callable[[PlanEvent], None]


class ExecutorAgent:
    """Run mock actions after the itinerary is settled."""

    def execute(
        self,
        intent: UserIntent,
        plan: ActivityPlan,
        restaurant: dict,
        event_callback: EventCallback | None = None,
    ) -> list[ActionResult]:
        meal_step = next(step for step in plan.steps if step.action == "晚餐")
        _emit(
            event_callback,
            PlanEvent(
                type="progress",
                stage="reservation_mock",
                message="正在模拟餐厅预约...",
                data={"restaurant": restaurant["name"], "time": meal_step.time},
            ),
        )
        reservation = reserve_restaurant(restaurant, meal_step.time, intent)
        _emit(
            event_callback,
            PlanEvent(
                type="progress",
                stage="reservation_mock",
                message="餐厅预约已完成",
                data={
                    "target": reservation.target,
                    "status": reservation.status,
                },
            ),
        )

        _emit(
            event_callback,
            PlanEvent(
                type="progress",
                stage="message_generation",
                message="正在生成可发送给同行人的消息...",
            ),
        )
        message = build_share_message(intent, plan, reservation)
        target = message_target(intent.scene)
        delivery = send_message(target, message)
        _emit(
            event_callback,
            PlanEvent(
                type="progress",
                stage="message_generation",
                message="同行消息已生成",
                data={"target": delivery.target},
            ),
        )
        return [reservation, delivery]


def _emit(
    event_callback: EventCallback | None,
    event: PlanEvent,
) -> None:
    if event_callback is not None:
        event_callback(event)
