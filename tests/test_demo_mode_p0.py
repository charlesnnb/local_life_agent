"""P0 guarantees for a stable zero-key competition Demo."""

import asyncio

import httpx
import pytest

import src.app as app_module
from src.agents.planner_agent import PlannerAgent
from src.config.settings import Settings
from src.providers.amap_provider import AmapProvider
from src.providers.deepseek_provider import DeepSeekProvider
from src.schemas.models import ResolvedLocation, RouteEstimate
from src.tools.route_tool import build_ordered_route_plan


FAMILY_QUERY = (
    "今天下午想带老婆孩子出去玩几个小时，别太远，"
    "孩子5岁，老婆最近在减肥"
)
FRIENDS_QUERY = (
    "今天下午我们4个人，2男2女，想出去玩几个小时，"
    "顺便吃饭，别太远"
)
FULL_DAY_QUERY = (
    "今天早上想去公园玩，然后中午点个外卖吃肯德基，"
    "下午去打台球，晚上去喝茶，夜宵吃个螺蛳粉"
)


class NoNetworkClient:
    """Fail loudly if a Demo provider attempts an outbound request."""

    def __init__(self):
        self.calls = 0

    def post(self, *_args, **_kwargs):
        self.calls += 1
        raise AssertionError("Demo Mode must not call DeepSeek")

    def get(self, *_args, **_kwargs):
        self.calls += 1
        raise AssertionError("Demo Mode must not call AMap")


def _demo_settings(monkeypatch, configured_keys: bool = False) -> Settings:
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("USE_MOCK_LLM", "true")
    monkeypatch.setenv("USE_MOCK_AMAP", "true")
    monkeypatch.setenv("USE_MOCK_ACTIONS", "true")
    monkeypatch.setenv("ENABLE_LLM", "true")
    monkeypatch.setenv("ENABLE_AMAP", "true")
    monkeypatch.setenv(
        "DEEPSEEK_API_KEY",
        "must-not-be-used" if configured_keys else "",
    )
    monkeypatch.setenv("AMAP_API_KEY", "")
    monkeypatch.setenv(
        "AMAP_WEB_SERVICE_KEY",
        "must-not-be-used" if configured_keys else "",
    )
    return Settings()


def _demo_planner(monkeypatch, configured_keys: bool = False):
    runtime_settings = _demo_settings(monkeypatch, configured_keys)
    deepseek_client = NoNetworkClient()
    amap_client = NoNetworkClient()
    planner = PlannerAgent(
        deepseek_provider=DeepSeekProvider(
            runtime_settings=runtime_settings,
            client=deepseek_client,
        ),
        amap_provider=AmapProvider(
            runtime_settings=runtime_settings,
            client=amap_client,
        ),
    )
    return planner, runtime_settings, deepseek_client, amap_client


def _post_plan(monkeypatch, planner: PlannerAgent, query: str):
    monkeypatch.setattr(app_module, "planner", planner)

    async def post():
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            return await client.post("/api/plan", json={"query": query})

    return asyncio.run(post())


def test_demo_mode_settings_force_all_mock_providers(monkeypatch):
    planner, runtime, deepseek_client, amap_client = _demo_planner(
        monkeypatch,
        configured_keys=True,
    )
    events = []

    result = planner.run(FAMILY_QUERY, event_callback=events.append)

    assert runtime.demo_mode is True
    assert runtime.use_mock_llm is True
    assert runtime.use_mock_amap is True
    assert runtime.use_mock_actions is True
    assert planner.deepseek.is_available is False
    assert planner.amap.is_available is False
    assert deepseek_client.calls == 0
    assert amap_client.calls == 0
    assert result.route.source == "mock"
    assert any(
        event.source == "mock" and "Demo Mode" in event.message
        for event in events
    )


def test_runtime_mode_endpoint_reports_zero_key_demo(monkeypatch):
    runtime = _demo_settings(monkeypatch)
    monkeypatch.setattr(app_module, "settings", runtime)

    async def get_runtime():
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            return await client.get("/api/runtime")

    response = asyncio.run(get_runtime())

    assert response.status_code == 200
    assert response.json() == {
        "mode": "demo",
        "llm": "mock",
        "amap": "mock",
        "actions": "mock",
    }


def test_runtime_mode_never_claims_actions_are_live(monkeypatch):
    runtime = Settings(
        demo_mode=False,
        use_mock_llm=False,
        use_mock_amap=False,
        use_mock_actions=False,
        enable_llm=True,
        deepseek_api_key="test-key",
        enable_amap=True,
        amap_api_key="test-key",
    )
    monkeypatch.setattr(app_module, "settings", runtime)

    async def get_runtime():
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            return await client.get("/api/runtime")

    response = asyncio.run(get_runtime())

    assert response.status_code == 200
    assert response.json() == {
        "mode": "live",
        "llm": "deepseek",
        "amap": "amap",
        "actions": "mock_fallback",
    }


def test_zero_key_family_demo_runs_end_to_end(monkeypatch):
    planner, _, deepseek_client, amap_client = _demo_planner(monkeypatch)

    response = _post_plan(monkeypatch, planner, FAMILY_QUERY)
    payload = response.json()

    assert response.status_code == 200
    assert payload["user_intent"]["scene"] == "family"
    assert payload["user_intent"]["child_age"] == 5
    assert {"poi_search", "restaurant_search"} <= {
        task["task_type"] for task in payload["task_plan"]["tasks"]
    }
    assert payload["route"]["stops"]
    assert payload["route"]["source"] == "mock"
    assert all(stop["source"] == "mock" for stop in payload["route"]["stops"])
    assert payload["timeline"]["items"]
    assert payload["actions"]
    assert all(
        action["status"].startswith("mock_")
        for action in payload["actions"]
    )
    assert deepseek_client.calls == 0
    assert amap_client.calls == 0


def test_zero_key_friends_demo_runs_end_to_end(monkeypatch):
    planner, _, deepseek_client, amap_client = _demo_planner(monkeypatch)

    response = _post_plan(monkeypatch, planner, FRIENDS_QUERY)
    payload = response.json()

    assert response.status_code == 200
    assert payload["user_intent"]["scene"] == "friends"
    assert payload["user_intent"]["party_size"] == 4
    assert payload["user_intent"]["gender_mix"] == {
        "male": 2,
        "female": 2,
    }
    task_types = {
        task["task_type"] for task in payload["task_plan"]["tasks"]
    }
    assert {"poi_search", "restaurant_search"} <= task_types
    assert len(payload["route"]["stops"]) >= 2
    assert payload["timeline"]["items"]
    message = next(
        action
        for action in payload["actions"]
        if action["type"] == "send_message"
    )
    assert message["target"] != "自己"
    assert deepseek_client.calls == 0
    assert amap_client.calls == 0


def test_zero_key_full_day_demo_runs_end_to_end(monkeypatch):
    planner, _, deepseek_client, amap_client = _demo_planner(monkeypatch)

    response = _post_plan(monkeypatch, planner, FULL_DAY_QUERY)
    payload = response.json()

    assert response.status_code == 200
    tasks = payload["task_plan"]["tasks"]
    assert len(tasks) == 5
    assert [task["time_window"] for task in tasks] == [
        "早上",
        "中午",
        "下午",
        "晚上",
        "夜宵",
    ]
    assert len(payload["route"]["stops"]) == 3
    route_categories = {
        stop["category"] for stop in payload["route"]["stops"]
    }
    assert {"park", "billiards", "tea_house"} <= route_categories
    route_text = " ".join(
        stop["name"] for stop in payload["route"]["stops"]
    )
    assert "肯德基" not in route_text
    assert "螺蛳粉" not in route_text
    assert payload["timeline"]["items"]
    assert all(
        action["status"] in {"mock_success", "mock_failed"}
        for action in payload["actions"]
    )
    assert deepseek_client.calls == 0
    assert amap_client.calls == 0


def test_non_demo_provider_failures_still_fall_back(monkeypatch):
    calls = {"deepseek": 0, "amap": 0}

    def deepseek_handler(_request):
        calls["deepseek"] += 1
        return httpx.Response(429, json={"error": "rate limited"})

    def amap_handler(_request):
        calls["amap"] += 1
        return httpx.Response(
            429,
            json={"status": "0", "info": "CUQPS_HAS_EXCEEDED_THE_LIMIT"},
        )

    runtime = Settings(
        demo_mode=False,
        use_mock_llm=False,
        use_mock_amap=False,
        enable_llm=True,
        enable_amap=True,
        deepseek_api_key="test-key",
        amap_api_key="test-key",
    )
    planner = PlannerAgent(
        deepseek_provider=DeepSeekProvider(
            runtime_settings=runtime,
            client=httpx.Client(
                transport=httpx.MockTransport(deepseek_handler)
            ),
        ),
        amap_provider=AmapProvider(
            runtime_settings=runtime,
            client=httpx.Client(transport=httpx.MockTransport(amap_handler)),
        ),
    )

    response = _post_plan(monkeypatch, planner, FAMILY_QUERY)

    assert response.status_code == 200
    assert response.json()["route"]["source"] == "mock"
    assert calls["deepseek"] > 0
    assert calls["amap"] > 0


def test_route_plan_supports_more_than_five_offline_stops():
    origin = ResolvedLocation(
        location_id="origin",
        city="上海",
        district="徐汇区",
        address="Demo 起点",
        lat=31.1886,
        lng=121.4365,
        source="demo_default",
    )
    places = [
        {
            "id": f"place_{index}",
            "name": f"地点 {index}",
            "lat": 31.18 + index * 0.01,
            "lng": 121.43 + index * 0.01,
            "task_type": "poi_search",
            "source": "mock",
        }
        for index in range(6)
    ]
    legs = [
        RouteEstimate(distance_km=10, duration_min=45)
        for _ in places
    ]
    return_leg = RouteEstimate(distance_km=10, duration_min=45)

    route = build_ordered_route_plan(
        origin,
        places,
        legs,
        return_leg,
    )

    assert len(route.stops) == 6
    assert route.total_travel_minutes == 315
    assert all(stop.estimated_travel_minutes == 45 for stop in route.stops)


@pytest.mark.parametrize(
    ("query", "expected_scene", "expected_size"),
    [
        ("今天我们一起出去玩", "friends", 4),
        ("今天四个人一起出去玩", "friends", 4),
        ("今天两男两女一起出去玩", "friends", 4),
        ("今天和同学一起出去玩", "friends", 4),
        ("今天和老婆一起出去玩", "couple", 2),
        ("今天带老婆孩子一起出去玩", "family", 3),
    ],
)
def test_group_signals_and_family_precedence(
    query,
    expected_scene,
    expected_size,
):
    from src.core.intent_parser import parse_intent

    intent = parse_intent(query)

    assert intent.scene == expected_scene
    assert intent.party_size == expected_size
