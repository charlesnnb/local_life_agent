"""AMap normalization, failure fallback, and route safety coverage."""

import asyncio

import httpx

import src.app as app_module
from src.agents.planner_agent import PlannerAgent
from src.core.intent_parser import parse_intent
from src.providers.amap_provider import AmapProvider
from src.providers.deepseek_provider import DeepSeekProvider
from src.services.location_service import resolve_location
from src.tools.poi_tool import search_pois
from src.tools.route_tool import estimate_route


QUERY = "今天下午想带老婆孩子出去玩几个小时，别太远，孩子5岁，老婆最近在减肥"


def _amap_with_handler(handler) -> AmapProvider:
    return AmapProvider(
        api_key="test-key",
        enabled=True,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_enable_amap_false_keeps_mock_flow_working():
    result = PlannerAgent(
        deepseek_provider=DeepSeekProvider(enabled=False),
        amap_provider=AmapProvider(enabled=False),
    ).run(QUERY)

    assert result.route.source == "mock"
    assert all(stop.source == "mock" for stop in result.route.stops)


def test_enable_amap_true_without_key_is_unavailable():
    provider = AmapProvider(api_key="", enabled=True)

    assert provider.is_available is False
    assert provider.unavailable_reason == "缺少 AMAP_API_KEY"


def test_amap_search_http_error_falls_back_to_mock_candidates():
    def handler(_request):
        return httpx.Response(503, json={"status": "0", "info": "busy"})

    provider = _amap_with_handler(handler)
    intent = parse_intent(QUERY)
    location = resolve_location(intent)
    candidates = search_pois(
        intent,
        location,
        ["亲子乐园"],
        provider,
    )

    assert candidates
    assert all(item["source"] == "mock" for item in candidates)
    assert provider.last_error


def test_amap_normalizes_real_place_response():
    def handler(request):
        assert request.url.path == "/v3/place/around"
        return httpx.Response(
            200,
            json={
                "status": "1",
                "pois": [
                    {
                        "id": "B001",
                        "name": "真实亲子馆",
                        "address": "上海市徐汇区测试路",
                        "location": "121.4400,31.1900",
                        "type": "科教文化服务",
                        "typecode": "140000",
                        "distance": "1800",
                        "biz_ext": {"rating": "4.6", "cost": "88"},
                    }
                ],
            },
        )

    results = _amap_with_handler(handler).search_poi(
        "亲子馆",
        city="上海",
        location=(31.19, 121.43),
    )

    assert results[0]["name"] == "真实亲子馆"
    assert results[0]["lat"] == 31.19
    assert results[0]["lng"] == 121.44
    assert results[0]["source"] == "amap"


def test_amap_geocode_and_route_keep_normalized_coordinates():
    def handler(request):
        if request.url.path == "/v3/geocode/geo":
            return httpx.Response(
                200,
                json={
                    "status": "1",
                    "geocodes": [{
                        "formatted_address": "上海市徐汇区测试路1号",
                        "city": "上海市",
                        "district": "徐汇区",
                        "location": "121.4300,31.1900",
                    }],
                },
            )
        return httpx.Response(
            200,
            json={
                "status": "1",
                "route": {
                    "paths": [{
                        "duration": "1080",
                        "distance": "3200",
                        "steps": [
                            {"polyline": "121.4300,31.1900;121.4400,31.2000"}
                        ],
                    }]
                },
            },
        )

    provider = _amap_with_handler(handler)
    geocode = provider.geocode("上海市徐汇区测试路1号")
    route = provider.route_duration(
        (31.19, 121.43),
        (31.20, 121.44),
    )

    assert geocode and geocode["lat"] == 31.19
    assert geocode["lng"] == 121.43
    assert route and route["duration_minutes"] == 18
    assert route["distance_meters"] == 3200
    assert route["polyline"] == [[31.19, 121.43], [31.2, 121.44]]


def test_amap_overlong_route_falls_back_to_bounded_mock():
    class OverlongAmap:
        enabled = True
        is_available = True
        last_error = None

        def route_duration(self, *_args, **_kwargs):
            return {
                "duration_minutes": 181,
                "distance_meters": 100000,
                "mode": "driving",
                "source": "amap",
                "polyline": [],
            }

    intent = parse_intent(QUERY)
    location = resolve_location(intent)
    route = estimate_route(
        location.location_id,
        "unknown",
        location,
        {"lat": 39.9, "lng": 116.4},
        OverlongAmap(),
    )

    assert route.source.startswith("mock")
    assert 5 <= route.duration_min <= 45
    assert route.duration_min != 1778


def test_plan_endpoint_survives_amap_failure(monkeypatch):
    def handler(_request):
        return httpx.Response(500, json={"status": "0", "info": "failed"})

    monkeypatch.setattr(
        app_module,
        "planner",
        PlannerAgent(
            deepseek_provider=DeepSeekProvider(enabled=False),
            amap_provider=_amap_with_handler(handler),
        ),
    )

    async def post_plan():
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            return await client.post("/api/plan", json={"query": QUERY})

    response = asyncio.run(post_plan())

    assert response.status_code == 200
    assert response.json()["route"]["source"] == "mock"
