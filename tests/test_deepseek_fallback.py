"""DeepSeek provider validation and fallback coverage."""

import asyncio
import json

import httpx

import src.app as app_module
from src.agents.planner_agent import PlannerAgent
from src.core.llm_intent_parser import parse_intent_with_llm
from src.providers.amap_provider import AmapProvider
from src.providers.deepseek_provider import DeepSeekProvider
from src.services.preference_service import get_current_profile


QUERY = "今天下午想带老婆孩子出去玩几个小时，别太远，孩子5岁，老婆最近在减肥"


def _deepseek_with_handler(handler) -> DeepSeekProvider:
    transport = httpx.MockTransport(handler)
    return DeepSeekProvider(
        api_key="test-key",
        enabled=True,
        client=httpx.Client(transport=transport),
    )


def test_enable_llm_false_keeps_rule_flow_working():
    result = PlannerAgent(
        deepseek_provider=DeepSeekProvider(enabled=False),
        amap_provider=AmapProvider(enabled=False),
    ).run(QUERY)

    assert result.user_intent.child_age == 5
    assert result.plan.steps
    assert result.route.source == "mock"


def test_enable_llm_true_without_key_is_unavailable():
    provider = DeepSeekProvider(api_key="", enabled=True)

    assert provider.is_available is False
    assert provider.unavailable_reason == "缺少 DEEPSEEK_API_KEY"


def test_deepseek_http_error_falls_back_to_rule_parser():
    def handler(_request):
        raise httpx.ConnectError("offline")

    provider = _deepseek_with_handler(handler)
    intent, used_llm, error = parse_intent_with_llm(
        QUERY,
        get_current_profile(),
        provider,
    )

    assert used_llm is False
    assert intent.child_age == 5
    assert "调用失败" in (error or "")


def test_deepseek_invalid_json_falls_back_to_rule_parser():
    def handler(_request):
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "not-json"}}]},
        )

    provider = _deepseek_with_handler(handler)
    intent, used_llm, error = parse_intent_with_llm(
        QUERY,
        get_current_profile(),
        provider,
    )

    assert used_llm is False
    assert intent.scene == "family"
    assert "非法 JSON" in (error or "")


def test_deepseek_provider_parses_strict_json_object():
    def handler(request):
        payload = json.loads(request.content)
        assert payload["response_format"] == {"type": "json_object"}
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"ok": true}'}}]},
        )

    result = _deepseek_with_handler(handler).chat_json(
        "system",
        "user",
        "TestSchema",
    )

    assert result == {"ok": True}


def test_stream_emits_fallback_and_still_returns_result(monkeypatch):
    def handler(_request):
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "{broken"}}]},
        )

    monkeypatch.setattr(
        app_module,
        "planner",
        PlannerAgent(
            deepseek_provider=_deepseek_with_handler(handler),
            amap_provider=AmapProvider(enabled=False),
        ),
    )

    async def collect():
        events = []
        transport = httpx.ASGITransport(app=app_module.app)
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
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        events.append(json.loads(line[6:]))
        return events

    events = asyncio.run(collect())

    assert any(
        event["stage"] == "api_fallback_triggered" for event in events
    )
    assert events[-1]["type"] == "result"
    assert events[-1]["data"]["route"]
    assert events[-1]["data"]["timeline"]
