"""Generate and mock-send a concise family/friend message."""

from datetime import datetime
import uuid

from src.schemas.models import (
    ActionResult,
    ActivityPlan,
    TaskPlan,
    UserIntent,
)


def build_share_message(
    intent: UserIntent,
    plan: ActivityPlan,
    reservation: ActionResult,
) -> str:
    """Turn the structured plan into a message that can be sent as-is."""
    activity = next(step for step in plan.steps if step.action in {"亲子活动", "活动"})
    meal = next(step for step in plan.steps if step.action == "晚餐")
    start = plan.steps[0].time
    reservation_text = (
        f"，{reservation.details.get('time', meal.time)} 的餐位也约好了"
        if reservation.status == "mock_success"
        else "，餐厅建议提前电话确认"
    )
    audience = "大家" if intent.scene == "friends" else "你们"
    return (
        f"搞定了，{start} 出发，先去{activity.place}，"
        f"{meal.time} 左右去{meal.place}吃饭{reservation_text}。"
        f"路线不远，整体约 {intent.duration_label}，{audience}按这个计划走就行。"
    )


def build_multistep_message(
    intent: UserIntent,
    plan: ActivityPlan,
) -> str:
    """Create a personal or shareable summary of an ordered multi-stage plan."""
    activity_target = next(
        (
            task.target
            for task in intent.tasks
            if task.task_type == "activity_search" and task.target
        ),
        None,
    )
    food = next(
        (step for step in plan.steps if step.action == "点餐"),
        None,
    )
    activity = next(
        (
            step
            for step in plan.steps
            if activity_target
            and step.action == activity_target
            and step.place
        ),
        None,
    )
    bar = next(
        (step for step in plan.steps if step.action == "酒吧放松"),
        None,
    )
    parts = []
    if food:
        parts.append(f"中午点{food.place}")
    if activity:
        parts.append(f"下午去{activity.place}{activity.action}放松")
    if bar:
        parts.append(f"晚上去{bar.place}坐坐")
    prefix = "今天安排好了" if intent.scene == "solo" else "今天的安排好了"
    return f"{prefix}：{'，'.join(parts)}。整体不赶，适合工作后放松。"


def build_task_plan_message(
    intent: UserIntent,
    task_plan: TaskPlan,
    plan: ActivityPlan,
    warnings: list[str],
) -> str:
    """Summarize the task-driven plan without inventing people or actions."""
    scheduled = [
        f"{step.time} {step.action}"
        + (f"：{step.place}" if step.place else "")
        for step in plan.steps
        if step.action not in {"前往", "行程结束"}
    ]
    audience = "个人计划" if intent.scene == "solo" else "行程计划"
    task_summary = " / ".join(
        task.description for task in task_plan.tasks
    )
    warning_text = f" 提醒：{warnings[0]}" if warnings else ""
    return (
        f"{audience}已安排：{task_summary}。"
        f"{'；'.join(scheduled)}。{warning_text}"
    ).strip()


def message_target(scene: str) -> str:
    """Return the appropriate mock message audience for a scene."""
    return {
        "family": "老婆/家人",
        "friends": "朋友",
        "couple": "同行人",
        "solo": "自己",
    }[scene]


def send_message(target: str, message: str) -> ActionResult:
    """Return a mock delivery receipt without contacting a real messaging service."""
    return ActionResult(
        type="send_message",
        target=target,
        status="mock_success",
        message=message,
        details={
            "message_id": f"MOCK-MSG-{uuid.uuid4().hex[:8].upper()}",
            "channel": "mock_message",
            "sent_at": datetime.now().isoformat(timespec="seconds"),
        },
    )
