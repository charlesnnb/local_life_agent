"""Final copy must preserve structured timeline semantics."""

import json

import httpx

from src.core.final_composer import compose_final_copy
from src.providers.deepseek_provider import DeepSeekProvider
from src.schemas.models import (
    ActionResult,
    ActivityPlan,
    PlanStep,
    RouteOrigin,
    RoutePlan,
    RouteStop,
    Timeline,
    TimelineItem,
)


def test_final_composer_rejects_meal_start_as_arrival_time():
    def handler(_request):
        content = {
            "summary": "14:00出发，16:30到达川菜馆。",
            "timeline_explanation": "16:30到达川菜馆后用餐。",
            "share_message": "14:00出发，16:30到达川菜馆吃饭。",
        }
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": json.dumps(content, ensure_ascii=False)}}
                ]
            },
        )

    plan = ActivityPlan(
        summary="下午亲子轻松出行方案",
        steps=[
            PlanStep(time="14:00", action="出发", description="出发"),
            PlanStep(
                time="16:03",
                action="到达餐厅",
                place="川菜馆",
                description="到达餐厅",
            ),
            PlanStep(
                time="16:30",
                action="晚餐",
                place="川菜馆",
                description="开始用餐",
            ),
        ],
        reasons=[],
    )
    timeline = Timeline(
        total_duration_minutes=180,
        items=[
            TimelineItem(
                time="14:00",
                type="departure",
                title="出发",
                description="出发",
            ),
            TimelineItem(
                time="16:03",
                type="restaurant",
                title="到达川菜馆",
                description="到达餐厅",
            ),
            TimelineItem(
                time="16:30",
                type="restaurant",
                title="开始在川菜馆用餐",
                description="开始用餐",
            ),
        ],
    )
    route = RoutePlan(
        origin=RouteOrigin(name="上海徐汇", lat=31.1886, lng=121.4365),
        stops=[
            RouteStop(
                type="restaurant",
                label="餐厅",
                name="川菜馆",
                lat=31.18,
                lng=121.43,
                estimated_travel_minutes=16,
                distance_km=3,
            )
        ],
        return_to_origin_minutes=10,
        total_travel_minutes=26,
    )
    actions = [
        ActionResult(
            type="reservation",
            target="川菜馆",
            status="mock_success",
            message="已模拟预约 16:30 的 2 人位。",
            details={"time": "16:30"},
        )
    ]

    composition, used_llm, error = compose_final_copy(
        plan,
        timeline,
        route,
        actions,
        [],
        "14:00出发，16:30开始在川菜馆吃饭。",
        DeepSeekProvider(
            api_key="test-key",
            enabled=True,
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        ),
    )

    assert used_llm is False
    assert "到达" in (error or "")
    assert composition.share_message == "14:00出发，16:30开始在川菜馆吃饭。"
