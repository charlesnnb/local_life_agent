"""Runtime contracts for Demo, Hybrid, and Live presentation modes."""

import asyncio

import httpx

import src.app as app_module
from src.agents.planner_agent import PlannerAgent
from src.config.settings import Settings
from src.providers.amap_provider import AmapProvider
from src.providers.deepseek_provider import DeepSeekProvider


FAMILY_QUERY = (
    "今天下午想带老婆孩子出去玩几个小时，别太远，"
    "孩子5岁，老婆最近在减肥"
)


def _runtime_payload(monkeypatch, runtime: Settings) -> dict:
    monkeypatch.setattr(app_module, "settings", runtime)

    async def request():
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            return await client.get("/api/runtime")

    response = asyncio.run(request())
    assert response.status_code == 200
    return response.json()


def test_runtime_endpoint_reports_all_three_modes(monkeypatch):
    demo = Settings(
        run_mode="demo",
        demo_mode=True,
        use_mock_llm=True,
        use_mock_amap=True,
        use_mock_actions=True,
    )
    assert _runtime_payload(monkeypatch, demo) == {
        "mode": "demo",
        "llm": "mock",
        "amap": "mock",
        "actions": "mock",
    }

    hybrid = Settings(
        run_mode="hybrid",
        demo_mode=False,
        use_mock_llm=False,
        use_mock_amap=False,
        use_mock_actions=True,
        enable_llm=True,
        deepseek_api_key="test-key",
        enable_amap=True,
        amap_api_key="test-key",
    )
    assert _runtime_payload(monkeypatch, hybrid) == {
        "mode": "hybrid",
        "llm": "deepseek",
        "amap": "amap",
        "actions": "mock",
    }

    live = Settings(
        run_mode="live",
        demo_mode=False,
        use_mock_llm=False,
        use_mock_amap=False,
        use_mock_actions=False,
        enable_llm=True,
        deepseek_api_key="test-key",
        enable_amap=True,
        amap_api_key="test-key",
    )
    assert _runtime_payload(monkeypatch, live) == {
        "mode": "live",
        "llm": "deepseek",
        "amap": "amap",
        "actions": "mock_fallback",
    }


def test_hybrid_selects_real_llm_and_amap_but_mock_actions():
    runtime = Settings(
        run_mode="hybrid",
        demo_mode=False,
        use_mock_llm=False,
        use_mock_amap=False,
        use_mock_actions=True,
        enable_llm=True,
        deepseek_api_key="test-key",
        enable_amap=True,
        amap_api_key="test-key",
    )

    deepseek = DeepSeekProvider(runtime_settings=runtime)
    amap = AmapProvider(runtime_settings=runtime)

    assert deepseek.is_available is True
    assert amap.is_available is True
    assert runtime.use_mock_actions is True
    assert runtime.llm_timeout_seconds <= 8
    assert runtime.amap_timeout_seconds <= 8


def test_hybrid_provider_errors_fall_back_to_complete_plan(monkeypatch):
    calls = {"deepseek": 0, "amap": 0}

    def deepseek_handler(_request):
        calls["deepseek"] += 1
        return httpx.Response(429, json={"error": "rate limited"})

    def amap_handler(_request):
        calls["amap"] += 1
        return httpx.Response(
            503,
            json={"status": "0", "info": "SERVICE_UNAVAILABLE"},
        )

    runtime = Settings(
        run_mode="hybrid",
        demo_mode=False,
        use_mock_llm=False,
        use_mock_amap=False,
        use_mock_actions=True,
        enable_llm=True,
        deepseek_api_key="test-key",
        enable_amap=True,
        amap_api_key="test-key",
        llm_timeout_seconds=0.5,
        amap_timeout_seconds=0.5,
    )
    planner = PlannerAgent(
        deepseek_provider=DeepSeekProvider(
            runtime_settings=runtime,
            client=httpx.Client(
                transport=httpx.MockTransport(deepseek_handler),
            ),
        ),
        amap_provider=AmapProvider(
            runtime_settings=runtime,
            client=httpx.Client(
                transport=httpx.MockTransport(amap_handler),
            ),
        ),
    )
    events = []

    result = planner.run(FAMILY_QUERY, event_callback=events.append)

    assert calls["deepseek"] > 0
    assert calls["amap"] > 0
    assert result.route.source == "mock"
    assert result.timeline.items
    assert result.actions
    assert all(action.status.startswith("mock_") for action in result.actions)
    assert any(
        event.stage == "api_fallback_triggered"
        for event in events
    )

