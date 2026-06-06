"""Resolve a safe origin without guessing a city from a full street address."""

from src.config.settings import settings
from src.providers.amap_provider import AmapProvider
from src.schemas.models import LocationInput, ResolvedLocation, UserIntent


CITY_CENTERS = {
    "上海": ("徐汇区", 31.1886, 121.4365),
    "北京": ("朝阳区", 39.9219, 116.4436),
    "广州": ("天河区", 23.1291, 113.3612),
    "深圳": ("南山区", 22.5333, 113.9304),
    "杭州": ("西湖区", 30.2741, 120.1551),
}


def resolve_location(
    intent: UserIntent,
    requested_location: LocationInput | None = None,
    amap_provider: AmapProvider | None = None,
) -> ResolvedLocation:
    """Use explicit coordinates first, a recognized query city second, then Demo default."""
    if (
        requested_location
        and requested_location.lat is not None
        and requested_location.lng is not None
    ):
        return ResolvedLocation(
            location_id="request_origin",
            city=intent.city or settings.default_city,
            district=settings.default_district,
            address=requested_location.address or "用户提供的位置",
            lat=requested_location.lat,
            lng=requested_location.lng,
            source="request",
        )

    if requested_location and requested_location.address and amap_provider:
        geocoded = amap_provider.geocode(requested_location.address)
        if geocoded:
            return ResolvedLocation(
                location_id="amap_request_origin",
                city=geocoded.get("city") or intent.city or settings.default_city,
                district=geocoded.get("district") or "",
                address=geocoded["formatted_address"],
                lat=geocoded["lat"],
                lng=geocoded["lng"],
                source="request",
            )

    if intent.city in CITY_CENTERS:
        district, lat, lng = CITY_CENTERS[intent.city]
        return ResolvedLocation(
            location_id=f"mock_home_{intent.city}",
            city=intent.city,
            district=district,
            address=f"{intent.city}{district}（Mock 城市中心）",
            lat=lat,
            lng=lng,
            source="query",
        )

    return ResolvedLocation(
        location_id="home_u_001",
        city=settings.default_city,
        district=settings.default_district,
        address=settings.default_address,
        lat=settings.default_lat,
        lng=settings.default_lng,
        source="demo_default",
    )
