"""Refine final copy while preserving selected places, times, and actions."""

import json
import re

from pydantic import ValidationError

from src.providers.deepseek_provider import DeepSeekProvider
from src.schemas.models import (
    ActionResult,
    ActivityPlan,
    FinalComposition,
    RoutePlan,
    Timeline,
)


SYSTEM_PROMPT = """你是本地活动方案文案编辑。
只返回 JSON object，不要 Markdown，不要思维链。
字段必须是 summary, timeline_explanation, share_message。
不得修改或新增输入中的地点、时间、路线和执行结果。
不得编造付款、下单、预约或消息发送状态。
文案自然、简洁，可直接展示或转发。"""


def compose_final_copy(
    plan: ActivityPlan,
    timeline: Timeline,
    route: RoutePlan,
    actions: list[ActionResult],
    preference_explanation: list[str],
    fallback_share_message: str,
    provider: DeepSeekProvider,
) -> tuple[FinalComposition, bool, str | None]:
    fallback = FinalComposition(
        summary=plan.summary,
        timeline_explanation=(
            f"路线按活动、餐厅和返程顺序安排，总通勤约 "
            f"{route.total_travel_minutes} 分钟。"
        ),
        share_message=fallback_share_message,
    )
    if not provider.is_available:
        return fallback, False, provider.unavailable_reason

    prompt = json.dumps(
        {
            "plan": plan.model_dump(mode="json"),
            "timeline": timeline.model_dump(mode="json"),
            "route": route.model_dump(mode="json"),
            "actions": [item.model_dump(mode="json") for item in actions],
            "preference_explanation": preference_explanation,
            "required_place_names_in_share_message": [
                step.place
                for step in plan.steps
                if step.place
                and step.action in {"亲子活动", "活动", "晚餐"}
            ],
            "required_times_in_share_message": [
                step.time
                for step in plan.steps
                if step.action in {"出发", "晚餐"}
            ],
            "instruction": (
                "share_message 必须逐字包含 required_place_names_in_share_message "
                "中的每个名称，不得改写名称。"
            ),
        },
        ensure_ascii=False,
    )
    payload = provider.chat_json(SYSTEM_PROMPT, prompt, "FinalComposition")
    if payload is None:
        return fallback, False, provider.last_error
    try:
        composition = FinalComposition.model_validate(payload)
    except ValidationError as exc:
        return fallback, False, f"DeepSeek final copy schema 校验失败: {exc}"

    selected_places = [
        step.place
        for step in plan.steps
        if step.place and step.action in {"亲子活动", "活动", "晚餐"}
    ]
    if any(place not in composition.share_message for place in selected_places):
        return fallback, False, "DeepSeek share message 遗漏已选地点"
    required_times = [
        step.time
        for step in plan.steps
        if step.action in {"出发", "晚餐"}
    ]
    if any(time not in composition.share_message for time in required_times):
        return fallback, False, "DeepSeek share message 遗漏既定时间"
    allowed_times = {item.time for item in timeline.items}
    mentioned_times = set(
        re.findall(
            r"(?:[01]\d|2[0-3]):[0-5]\d",
            " ".join([
                composition.summary,
                composition.timeline_explanation,
                composition.share_message,
            ]),
        )
    )
    if not mentioned_times <= allowed_times:
        return fallback, False, "DeepSeek final copy 修改了既定时间"
    if any(word in composition.share_message for word in ["已付款", "支付成功"]):
        return fallback, False, "DeepSeek share message 编造了支付结果"
    reservation = next(
        (item for item in actions if item.type == "reservation"),
        None,
    )
    if (
        reservation
        and reservation.status != "mock_success"
        and any(
            word in composition.share_message
            for word in ["约好了", "预约成功", "已预约"]
        )
    ):
        return fallback, False, "DeepSeek share message 编造了预约结果"
    return composition, True, None
