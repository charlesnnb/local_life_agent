"""Tests for AMap and Mock AMap providers."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from backend.providers.amap.mock_provider import (
    MockPOIProvider,
    MockRouteProvider,
    MockWeatherProvider,
)
from backend.providers.amap.amap_provider import (
    AmapPOIProvider,
    AmapRouteProvider,
    AmapWeatherProvider,
)


def _make_mock_response(json_data: dict) -> MagicMock:
    """Create a mock httpx.Response that returns json_data from .json()."""
    resp = MagicMock(spec=httpx.Response)
    resp.raise_for_status = MagicMock()
    resp.json.return_value = json_data
    return resp


def _make_async_get(mock_response: MagicMock) -> AsyncMock:
    """Create an AsyncMock that returns the mock_response when awaited."""
    m = AsyncMock()
    m.return_value = mock_response
    return m


# ── Mock Provider Tests ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mock_poi_provider_returns_data():
    provider = MockPOIProvider()
    results = await provider.search_pois(city="海淀区")
    assert isinstance(results, list)
    assert len(results) > 0
    for r in results:
        assert "id" in r
        assert "name" in r
        assert "source" in r
        assert r["source"] == "mock_json"


@pytest.mark.asyncio
async def test_mock_poi_provider_unknown_fields():
    """Mock POI results should have 'unknown' for fields not in JSON."""
    provider = MockPOIProvider()
    results = await provider.search_pois()
    for r in results:
        assert r.get("booking_supported") == "unknown"
        assert r.get("longitude") is None or r.get("longitude") is None


@pytest.mark.asyncio
async def test_mock_geocode():
    provider = MockPOIProvider()
    result = await provider.geocode("朝阳区望京")
    assert result is not None
    assert "formatted_address" in result


@pytest.mark.asyncio
async def test_mock_route_provider():
    provider = MockRouteProvider()
    result = await provider.plan_route("home_u_001", "poi_001")
    assert result["distance_m"] > 0
    assert result["duration_sec"] > 0
    assert result["source"] in ("mock_json", "mock_fallback")


@pytest.mark.asyncio
async def test_mock_weather_provider():
    provider = MockWeatherProvider()
    result = await provider.get_weather("北京")
    assert result["day_weather"] == "sunny"
    assert result["source"] == "mock"


# ── Real AMap Provider Tests (with mocked HTTP) ──────────────────────


@pytest.fixture
def amap_poi():
    return AmapPOIProvider(api_key="test-key")


@pytest.fixture
def amap_route():
    return AmapRouteProvider(api_key="test-key")


@pytest.fixture
def amap_weather():
    return AmapWeatherProvider(api_key="test-key")


@pytest.mark.asyncio
async def test_amap_poi_search_normalizes_fields(amap_poi):
    """POI results must have unknown for fields AMap doesn't provide."""
    mock_data = {
        "status": "1",
        "count": "2",
        "pois": [
            {"id": "B0FFFAB6J2", "name": "测试餐厅", "type": "餐饮服务;中餐厅",
             "address": "北京市朝阳区测试路1号", "location": "116.397428,39.90923",
             "tel": "010-12345678", "distance": "500"},
            {"id": "B0FFFAB6J3", "name": "测试公园", "type": "公园",
             "address": "北京市海淀区测试路2号", "location": "116.310316,39.983074",
             "tel": "", "distance": "1200"},
        ],
    }

    with patch("httpx.AsyncClient.get", _make_async_get(_make_mock_response(mock_data))):
        results = await amap_poi.search_pois(keyword="餐厅", city="北京")

    assert len(results) == 2
    assert results[0]["name"] == "测试餐厅"
    assert results[0]["longitude"] == 116.397428
    assert results[0]["latitude"] == 39.90923
    assert results[0]["rating"] == "unknown"
    assert results[0]["avg_price"] == "unknown"
    assert results[0]["open_time"] == "unknown"
    assert results[0]["source"] == "amap"


@pytest.mark.asyncio
async def test_amap_poi_search_handles_api_error(amap_poi):
    """API errors should raise, not silently return empty."""
    mock_get = AsyncMock()
    mock_get.side_effect = Exception("Connection refused")
    with patch("httpx.AsyncClient.get", mock_get):
        with pytest.raises(Exception):
            await amap_poi.search_pois(keyword="测试")


@pytest.mark.asyncio
async def test_amap_poi_search_returns_empty_on_api_failure_status(amap_poi):
    """Non-1 status should return empty list."""
    with patch("httpx.AsyncClient.get", _make_async_get(_make_mock_response({"status": "0", "info": "INVALID_KEY"}))):
        results = await amap_poi.search_pois(keyword="测试")
    assert results == []


@pytest.mark.asyncio
async def test_amap_geocode_returns_coordinates(amap_poi):
    mock_data = {
        "status": "1", "count": "1",
        "geocodes": [{"formatted_address": "北京市朝阳区望京", "location": "116.480491,39.996441", "adcode": "110105"}],
    }
    with patch("httpx.AsyncClient.get", _make_async_get(_make_mock_response(mock_data))):
        result = await amap_poi.geocode("朝阳区望京", city="北京")
    assert result["longitude"] == 116.480491
    assert result["latitude"] == 39.996441
    assert result["adcode"] == "110105"


@pytest.mark.asyncio
async def test_amap_geocode_no_results(amap_poi):
    with patch("httpx.AsyncClient.get", _make_async_get(_make_mock_response({"status": "1", "count": "0", "geocodes": []}))):
        result = await amap_poi.geocode("不存在的地址")
    assert result is None


@pytest.mark.asyncio
async def test_amap_route_planning(amap_route):
    mock_data = {"status": "1", "route": {"paths": [{"distance": "8500", "duration": "1200"}]}}
    with patch("httpx.AsyncClient.get", _make_async_get(_make_mock_response(mock_data))):
        result = await amap_route.plan_route(
            origin="116.397428,39.90923", destination="116.480491,39.996441")
    assert result["distance_m"] == 8500
    assert result["duration_sec"] == 1200
    assert result["source"] == "amap"


@pytest.mark.asyncio
async def test_amap_weather(amap_weather):
    mock_data = {
        "status": "1",
        "forecasts": [{"city": "北京市", "casts": [{
            "date": "2026-06-01", "dayweather": "晴", "nightweather": "多云",
            "daytemp": "28", "nighttemp": "18", "daywind": "北", "nightwind": "北", "daypower": "3"}]}],
    }
    with patch("httpx.AsyncClient.get", _make_async_get(_make_mock_response(mock_data))):
        result = await amap_weather.get_weather("北京")
    assert result["day_weather"] == "晴"
    assert result["day_temp"] == "28"
    assert result["source"] == "amap"


@pytest.mark.asyncio
async def test_amap_weather_failure_returns_unknown(amap_weather):
    with patch("httpx.AsyncClient.get", _make_async_get(_make_mock_response({"status": "0", "info": "INVALID_KEY"}))):
        result = await amap_weather.get_weather("北京")
    assert result["weather"] == "unknown"
    assert result["source"] == "amap"


@pytest.mark.asyncio
async def test_amap_poi_unknown_fields_exhaustive(amap_poi):
    """Verify all unknown fields are explicitly set."""
    mock_data = {"status": "1", "pois": [{"id": "1", "name": "X", "type": "", "address": "", "location": ""}]}
    with patch("httpx.AsyncClient.get", _make_async_get(_make_mock_response(mock_data))):
        results = await amap_poi.search_pois(keyword="test")
    r = results[0]
    assert r["rating"] == "unknown"
    assert r["avg_price"] == "unknown"
    assert r["open_time"] == "unknown"
    assert r["booking_supported"] == "unknown"
    assert r["has_low_fat_meal"] == "unknown"
    assert r["has_kids_meal"] == "unknown"
