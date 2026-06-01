"""Base provider interfaces."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum


class ProviderType(str, Enum):
    LLM = "llm"
    POI = "poi"
    ROUTE = "route"
    WEATHER = "weather"
    BOOKING = "booking"


@dataclass
class ProviderInfo:
    """Metadata about a provider instance."""
    provider_type: ProviderType
    mode: str  # real / mock / fallback
    provider_name: str  # e.g. "deepseek", "amap", "mock"


class POIProvider(ABC):
    """Abstract interface for POI search."""

    @abstractmethod
    async def search_pois(
        self,
        keyword: str | None = None,
        city: str | None = None,
        location: str | None = None,
        radius_m: int = 5000,
        poi_type: str | None = None,
    ) -> list[dict]:
        ...

    @abstractmethod
    async def geocode(self, address: str, city: str | None = None) -> dict | None:
        ...


class RouteProvider(ABC):
    """Abstract interface for route planning."""

    @abstractmethod
    async def plan_route(
        self,
        origin: str,
        destination: str,
        origin_coords: str | None = None,
        dest_coords: str | None = None,
        transport: str = "driving",
    ) -> dict:
        ...


class WeatherProvider(ABC):
    """Abstract interface for weather queries."""

    @abstractmethod
    async def get_weather(self, city: str, adcode: str | None = None) -> dict:
        ...


class BookingProvider(ABC):
    """Abstract interface for booking/reservation.

    Currently always returns unsupported — real booking API is not available.
    """

    @abstractmethod
    async def check_availability(
        self, venue_id: str, time: str, party_size: int
    ) -> dict:
        ...

    @abstractmethod
    async def create_reservation(
        self, venue_id: str, time: str, party_size: int, note: str = ""
    ) -> dict:
        ...
