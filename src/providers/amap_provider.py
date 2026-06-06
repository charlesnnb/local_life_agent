"""HTTP client for the subset of AMap Web Service APIs used by the Demo."""

import logging
from typing import Any

import httpx

from src.config.settings import Settings, settings


logger = logging.getLogger(__name__)


class AmapProvider:
    """Expose normalized geocoding, POI search, and route results."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        enabled: bool | None = None,
        client: httpx.Client | None = None,
        runtime_settings: Settings = settings,
    ):
        self.enabled = (
            runtime_settings.enable_amap if enabled is None else enabled
        )
        self.api_key = (
            runtime_settings.amap_api_key
            if api_key is None
            else api_key.strip()
        )
        self.base_url = (
            runtime_settings.amap_base_url
            if base_url is None
            else base_url.rstrip("/")
        )
        self.timeout = timeout or runtime_settings.amap_timeout_seconds
        self._client = client
        self.last_error: str | None = None

    @property
    def is_available(self) -> bool:
        return self.enabled and bool(self.api_key)

    @property
    def unavailable_reason(self) -> str | None:
        if not self.enabled:
            return "高德 API 未启用"
        if not self.api_key:
            return "缺少 AMAP_API_KEY"
        return None

    def geocode(self, address: str) -> dict[str, Any] | None:
        body = self._get_json(
            "/v3/geocode/geo",
            {"address": address},
            "geocode",
        )
        if not body:
            return None
        geocodes = body.get("geocodes") or []
        if not geocodes:
            self.last_error = "高德未找到该地址"
            return None
        item = geocodes[0]
        coordinates = _parse_location(item.get("location"))
        if coordinates is None:
            self.last_error = "高德地理编码缺少有效坐标"
            return None
        lat, lng = coordinates
        return {
            "formatted_address": item.get("formatted_address") or address,
            "province": item.get("province") or "",
            "city": _text_value(item.get("city")),
            "district": item.get("district") or "",
            "lat": lat,
            "lng": lng,
            "source": "amap",
        }

    def search_poi(
        self,
        keywords: str,
        city: str | None = None,
        location: tuple[float, float] | None = None,
    ) -> list[dict[str, Any]]:
        return self._search_places(keywords, city, location)

    def search_restaurants(
        self,
        keywords: str,
        city: str | None = None,
        location: tuple[float, float] | None = None,
    ) -> list[dict[str, Any]]:
        return self._search_places(keywords, city, location, types="050000")

    def route_duration(
        self,
        origin: tuple[float, float],
        destination: tuple[float, float],
        mode: str = "driving",
    ) -> dict[str, Any] | None:
        path = (
            "/v3/direction/walking"
            if mode == "walking"
            else "/v3/direction/driving"
        )
        body = self._get_json(
            path,
            {
                "origin": _format_location(origin),
                "destination": _format_location(destination),
                "extensions": "all",
            },
            "route",
        )
        if not body:
            return None
        paths = (body.get("route") or {}).get("paths") or []
        if not paths:
            self.last_error = "高德路线结果为空"
            return None
        path_data = paths[0]
        try:
            duration_seconds = int(float(path_data.get("duration", 0)))
            distance_meters = int(float(path_data.get("distance", 0)))
        except (TypeError, ValueError):
            self.last_error = "高德路线时长或距离格式异常"
            return None
        if duration_seconds <= 0 or distance_meters < 0:
            self.last_error = "高德路线时长或距离无效"
            return None
        return {
            "duration_minutes": max(1, round(duration_seconds / 60)),
            "distance_meters": distance_meters,
            "mode": mode,
            "source": "amap",
            "polyline": _parse_polyline(path_data.get("steps") or []),
        }

    def _search_places(
        self,
        keywords: str,
        city: str | None,
        location: tuple[float, float] | None,
        types: str | None = None,
    ) -> list[dict[str, Any]]:
        path = "/v3/place/around" if location else "/v3/place/text"
        params: dict[str, Any] = {
            "keywords": keywords,
            "city": city or "",
            "citylimit": "true" if city else "false",
            "offset": 10,
            "page": 1,
            "extensions": "all",
        }
        if location:
            params["location"] = _format_location(location)
            params["radius"] = 15000
        if types:
            params["types"] = types
        body = self._get_json(path, params, "place search")
        if not body:
            return []
        results = []
        for item in body.get("pois") or []:
            coordinates = _parse_location(item.get("location"))
            if coordinates is None:
                continue
            lat, lng = coordinates
            biz_ext = item.get("biz_ext")
            if not isinstance(biz_ext, dict):
                biz_ext = {}
            results.append({
                "id": str(item.get("id") or ""),
                "name": str(item.get("name") or "未命名地点"),
                "address": _text_value(item.get("address")),
                "lat": lat,
                "lng": lng,
                "type": str(item.get("type") or ""),
                "typecode": str(item.get("typecode") or ""),
                "distance_meters": _safe_int(item.get("distance")),
                "rating": _safe_float(biz_ext.get("rating")),
                "cost": _safe_float(biz_ext.get("cost")),
                "source": "amap",
            })
        return results

    def _get_json(
        self,
        path: str,
        params: dict[str, Any],
        operation: str,
    ) -> dict[str, Any] | None:
        self.last_error = None
        if not self.is_available:
            self.last_error = self.unavailable_reason
            return None
        try:
            client = self._client or httpx.Client()
            response = client.get(
                f"{self.base_url}{path}",
                params={**params, "key": self.api_key},
                timeout=self.timeout,
            )
            response.raise_for_status()
            body = response.json()
            if str(body.get("status")) != "1":
                raise ValueError(
                    body.get("info") or body.get("infocode") or "unknown error"
                )
            return body
        except Exception as exc:
            self.last_error = f"高德 {operation} 调用失败: {exc}"
            logger.warning(self.last_error)
            return None


def _parse_location(value: Any) -> tuple[float, float] | None:
    if not isinstance(value, str) or "," not in value:
        return None
    try:
        lng_text, lat_text = value.split(",", 1)
        return float(lat_text), float(lng_text)
    except ValueError:
        return None


def _format_location(value: tuple[float, float]) -> str:
    lat, lng = value
    return f"{lng},{lat}"


def _parse_polyline(steps: list[dict[str, Any]]) -> list[list[float]]:
    coordinates: list[list[float]] = []
    for step in steps:
        for point in str(step.get("polyline") or "").split(";"):
            parsed = _parse_location(point)
            if parsed is not None:
                lat, lng = parsed
                coordinates.append([lat, lng])
    return coordinates


def _text_value(value: Any) -> str:
    if isinstance(value, list):
        return "".join(str(item) for item in value)
    return str(value or "")


def _safe_int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
