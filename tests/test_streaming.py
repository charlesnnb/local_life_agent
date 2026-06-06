"""Priority 3 coverage for planner progress and SSE delivery."""

import asyncio
import json
from pathlib import Path

import httpx

from src.agents.planner_agent import PlannerAgent
from src.app import app


QUERY = "今天下午想带老婆孩子出去玩几个小时，别太远，孩子5岁，老婆最近在减肥"


async def _collect_stream_events() -> list[dict]:
    events = []
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        async with client.stream(
            "POST",
            "/api/plan/stream",
            json={"query": QUERY},
        ) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith(
                "text/event-stream"
            )
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    events.append(json.loads(line.removeprefix("data: ")))
    return events


def _stream_events() -> list[dict]:
    return asyncio.run(_collect_stream_events())


def test_streaming_endpoint_emits_progress_and_complete_result():
    events = _stream_events()
    progress_events = [event for event in events if event["type"] == "progress"]

    assert len(progress_events) >= 8
    assert events[-1]["type"] == "result"
    assert events[-1]["stage"] == "completed"

    result = events[-1]["data"]
    assert result["plan"]["steps"]
    assert result["route"]["origin"]
    assert result["route"]["stops"]
    assert result["timeline"]["items"]
    assert result["actions"]


def test_streaming_covers_expected_agent_stages():
    stages = {
        event["stage"]
        for event in _stream_events()
        if event["type"] == "progress"
    }

    assert {
        "intent_parsing",
        "intent_parsed",
        "activity_search",
        "restaurant_search",
        "route_planning",
        "timeline_building",
        "reservation_mock",
        "message_generation",
        "completed",
    } <= stages


def test_regular_plan_endpoint_still_works():
    async def post_plan():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            return await client.post("/api/plan", json={"query": QUERY})

    response = asyncio.run(post_plan())

    assert response.status_code == 200
    payload = response.json()
    assert payload["plan"]["steps"]
    assert payload["route"]["stops"]
    assert payload["timeline"]["items"]


def test_callback_failure_does_not_break_planning():
    callback_calls = 0

    def flaky_callback(_event):
        nonlocal callback_calls
        callback_calls += 1
        if callback_calls == 1:
            raise RuntimeError("mock client disconnected")

    result = PlannerAgent().run(QUERY, event_callback=flaky_callback)

    assert callback_calls > 1
    assert result.plan.steps
    assert result.route.stops


def test_no_streaming_specific_orchestrator_exists():
    root = Path(__file__).resolve().parents[1]
    forbidden = {
        "stream_orchestrator.py",
        "orchestrator_v3.py",
        "planner_agent_stream.py",
    }
    python_files = {path.name for path in root.rglob("*.py")}

    assert forbidden.isdisjoint(python_files)
