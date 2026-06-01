"""AMap provider factory — creates real or mock AMap providers."""

import logging
from backend.config.settings import get_settings, ProviderMode
from backend.providers.amap.amap_provider import (
    AmapPOIProvider,
    AmapRouteProvider,
    AmapWeatherProvider,
)
from backend.providers.amap.mock_provider import (
    MockPOIProvider,
    MockRouteProvider,
    MockWeatherProvider,
)

logger = logging.getLogger(__name__)


def create_poi_provider():
    settings = get_settings()
    if settings.provider_status.poi == ProviderMode.REAL:
        if not settings.amap_api_key:
            raise RuntimeError("POI provider is REAL but AMAP_API_KEY is missing")
        logger.info("POI provider: AMap (real)")
        return AmapPOIProvider(api_key=settings.amap_api_key)
    logger.info("POI provider: mock")
    return MockPOIProvider()


def create_route_provider():
    settings = get_settings()
    if settings.provider_status.route == ProviderMode.REAL:
        if not settings.amap_api_key:
            raise RuntimeError("Route provider is REAL but AMAP_API_KEY is missing")
        logger.info("Route provider: AMap (real)")
        return AmapRouteProvider(api_key=settings.amap_api_key)
    logger.info("Route provider: mock")
    return MockRouteProvider()


def create_weather_provider():
    settings = get_settings()
    if settings.provider_status.weather == ProviderMode.REAL:
        if not settings.amap_api_key:
            raise RuntimeError("Weather provider is REAL but AMAP_API_KEY is missing")
        logger.info("Weather provider: AMap (real)")
        return AmapWeatherProvider(api_key=settings.amap_api_key)
    logger.info("Weather provider: mock")
    return MockWeatherProvider()
