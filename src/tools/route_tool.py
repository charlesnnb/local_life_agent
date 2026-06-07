"""Reasonable mock route estimates with a hard upper bound for Demo stability."""

import math

from src.config.settings import load_json
from src.providers.amap_provider import AmapProvider
from src.schemas.models import (
    ResolvedLocation,
    RouteEstimate,
    RouteOrigin,
    RoutePlan,
    RouteStop,
)


def estimate_route(
    origin_id: str,
    destination_id: str,
    origin: ResolvedLocation | dict,
    destination: dict,
    amap_provider: AmapProvider | None = None,
    mode: str = "driving",
) -> RouteEstimate:
    """Use a valid AMap route first, then bounded local estimates."""
    origin_lat, origin_lng = _coordinates(origin)
    dest_lat, dest_lng = _coordinates(destination)
    if (
        amap_provider
        and amap_provider.is_available
        and None not in (origin_lat, origin_lng, dest_lat, dest_lng)
    ):
        result = amap_provider.route_duration(
            (float(origin_lat), float(origin_lng)),
            (float(dest_lat), float(dest_lng)),
            mode=mode,
        )
        if result and 1 <= result["duration_minutes"] <= 180:
            distance_meters = max(0, int(result["distance_meters"]))
            return RouteEstimate(
                distance_km=round(distance_meters / 1000, 1),
                distance_meters=distance_meters,
                duration_min=_bounded_minutes(result["duration_minutes"]),
                transport=mode,
                mode=mode,
                source="amap",
                polyline=result.get("polyline") or [],
            )

    for route in load_json("travel_times.json").get("travel_times", []):
        if route.get("from") == origin_id and route.get("to") == destination_id:
            distance_km = float(route.get("distance_km", 3.0))
            return RouteEstimate(
                distance_km=distance_km,
                distance_meters=round(distance_km * 1000),
                duration_min=_bounded_minutes(route.get("taxi_time_min", 15)),
                mode=mode,
                source="mock_json",
            )

    if None not in (origin_lat, origin_lng, dest_lat, dest_lng):
        distance = _haversine_km(origin_lat, origin_lng, dest_lat, dest_lng)
        duration = round(distance / 0.35 + 5)
        return RouteEstimate(
            distance_km=round(min(distance, 12.0), 1),
            distance_meters=round(min(distance, 12.0) * 1000),
            duration_min=_bounded_minutes(duration),
            mode=mode,
            source="mock_coordinate_estimate",
        )

    return RouteEstimate(
        distance_km=3.0,
        distance_meters=3000,
        duration_min=15,
        mode=mode,
        source="mock_default",
    )


def build_route_plan(
    origin: ResolvedLocation,
    activity: dict,
    restaurant: dict,
    home_to_activity: RouteEstimate,
    activity_to_restaurant: RouteEstimate,
    restaurant_to_home: RouteEstimate,
) -> RoutePlan:
    """Assemble selected stops and route estimates into a frontend-ready route."""
    activity_lat, activity_lng = _required_coordinates(activity, origin)
    restaurant_lat, restaurant_lng = _required_coordinates(restaurant, origin)
    total_travel_minutes = sum(
        _bounded_minutes(route.duration_min)
        for route in (
            home_to_activity,
            activity_to_restaurant,
            restaurant_to_home,
        )
    )

    return RoutePlan(
        origin=RouteOrigin(
            name=_origin_name(origin),
            lat=origin.lat,
            lng=origin.lng,
        ),
        stops=[
            RouteStop(
                type="activity",
                label="活动",
                name=activity.get("name", "活动地点"),
                lat=activity_lat,
                lng=activity_lng,
                estimated_travel_minutes=_bounded_minutes(
                    home_to_activity.duration_min
                ),
                distance_km=home_to_activity.distance_km,
                source=activity.get("source", "mock"),
            ),
            RouteStop(
                type="restaurant",
                label="餐厅",
                name=restaurant.get("name", "餐厅"),
                lat=restaurant_lat,
                lng=restaurant_lng,
                estimated_travel_minutes=_bounded_minutes(
                    activity_to_restaurant.duration_min
                ),
                distance_km=activity_to_restaurant.distance_km,
                source=restaurant.get("source", "mock"),
            ),
        ],
        return_to_origin_minutes=_bounded_minutes(
            restaurant_to_home.duration_min
        ),
        total_travel_minutes=total_travel_minutes,
        transport=home_to_activity.mode,
        source=_route_source(
            home_to_activity,
            activity_to_restaurant,
            restaurant_to_home,
        ),
        polyline=_merge_polylines(
            home_to_activity,
            activity_to_restaurant,
            restaurant_to_home,
        ),
    )


def build_ordered_route_plan(
    origin: ResolvedLocation,
    places: list[dict],
    legs: list[RouteEstimate],
    return_leg: RouteEstimate,
) -> RoutePlan:
    """Assemble an ordered route containing only offline task places."""
    if len(places) != len(legs):
        raise ValueError("每个线下地点都必须有一段到达路线。")

    stops = []
    for place, leg in zip(places, legs, strict=True):
        lat, lng = _required_coordinates(place, origin)
        stops.append(
            RouteStop(
                type=_route_stop_type(place.get("task_type")),
                category=place.get("task_category", "unknown"),
                label=place.get("route_label", "活动"),
                name=place.get("name", "活动地点"),
                lat=lat,
                lng=lng,
                estimated_travel_minutes=_bounded_minutes(
                    leg.duration_min
                ),
                distance_km=leg.distance_km,
                source=place.get("source", "mock"),
            )
        )

    routes = [*legs, return_leg]
    return RoutePlan(
        origin=RouteOrigin(
            name=_origin_name(origin),
            lat=origin.lat,
            lng=origin.lng,
        ),
        stops=stops,
        return_to_origin_minutes=_bounded_minutes(return_leg.duration_min),
        total_travel_minutes=sum(
            _bounded_minutes(route.duration_min) for route in routes
        ),
        transport=legs[0].mode if legs else return_leg.mode,
        source=_route_source(*routes),
        polyline=_merge_polylines(*routes),
    )


def _route_stop_type(task_type: str | None) -> str:
    return {
        "restaurant_search": "restaurant",
        "restaurant_visit": "restaurant",
        "bar_visit": "bar",
        "hotel_search": "hotel",
    }.get(task_type, "activity")


def _coordinates(item: ResolvedLocation | dict) -> tuple[float | None, float | None]:
    if isinstance(item, ResolvedLocation):
        return item.lat, item.lng
    return (
        item.get("lat") if item.get("lat") is not None else item.get("latitude"),
        item.get("lng") if item.get("lng") is not None else item.get("longitude"),
    )


def _required_coordinates(
    item: dict,
    fallback: ResolvedLocation,
) -> tuple[float, float]:
    lat, lng = _coordinates(item)
    return (
        float(lat if lat is not None else fallback.lat),
        float(lng if lng is not None else fallback.lng),
    )


def _origin_name(origin: ResolvedLocation) -> str:
    if origin.source == "demo_default":
        return "默认位置：上海徐汇"
    return origin.address


def _route_source(*routes: RouteEstimate) -> str:
    sources = {route.source for route in routes}
    if sources == {"amap"}:
        return "amap"
    if "amap" in sources:
        return "mixed"
    return "mock"


def _merge_polylines(*routes: RouteEstimate) -> list[list[float]]:
    points: list[list[float]] = []
    for route in routes:
        points.extend(route.polyline)
    return points


def _bounded_minutes(value: int | float) -> int:
    return max(5, min(int(value), 45))


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371.0
    lat_delta = math.radians(lat2 - lat1)
    lng_delta = math.radians(lng2 - lng1)
    a = (
        math.sin(lat_delta / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(lng_delta / 2) ** 2
    )
    return radius * 2 * math.asin(math.sqrt(a))
