"""Unified configuration and provider status for the Local Life Planning Agent.

Reads all settings from environment variables. Never hardcodes secrets or API keys.
"""

import os
import sys
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, field

# Auto-load .env from project root
def _load_dotenv():
    try:
        from dotenv import load_dotenv
        env_path = Path(__file__).resolve().parent.parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
    except ImportError:
        pass

_load_dotenv()


class AppMode(str, Enum):
    DEVELOPMENT = "development"
    DEMO = "demo"
    TEST = "test"


class ProviderMode(str, Enum):
    REAL = "real"
    MOCK = "mock"
    FALLBACK = "fallback"  # tried real, fell back to mock


@dataclass
class ProviderStatus:
    llm: ProviderMode = ProviderMode.MOCK
    poi: ProviderMode = ProviderMode.MOCK
    route: ProviderMode = ProviderMode.MOCK
    weather: ProviderMode = ProviderMode.MOCK
    booking: ProviderMode = ProviderMode.MOCK

    def to_dict(self) -> dict:
        return {
            "llm": self.llm.value,
            "poi": self.poi.value,
            "route": self.route.value,
            "weather": self.weather.value,
            "booking": self.booking.value,
        }


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid."""


@dataclass
class Settings:
    app_mode: AppMode
    deepseek_api_key: str | None
    amap_api_key: str | None
    host: str = "0.0.0.0"
    port: int = 8000
    provider_status: ProviderStatus = field(default_factory=ProviderStatus)

    @property
    def is_development(self) -> bool:
        return self.app_mode == AppMode.DEVELOPMENT

    @property
    def is_demo(self) -> bool:
        return self.app_mode == AppMode.DEMO

    @property
    def is_test(self) -> bool:
        return self.app_mode == AppMode.TEST


def _read_app_mode() -> AppMode:
    raw = os.getenv("APP_MODE", "development").strip().lower()
    try:
        return AppMode(raw)
    except ValueError:
        raise ConfigError(
            f"Invalid APP_MODE '{raw}'. Must be one of: development, demo, test"
        )


def _read_api_key(env_var: str) -> str | None:
    val = os.getenv(env_var, "").strip()
    return val if val else None


def load_settings() -> Settings:
    """Load settings from environment variables.

    Raises ConfigError in demo mode when required keys are missing.
    """
    app_mode = _read_app_mode()
    deepseek_key = _read_api_key("DEEPSEEK_API_KEY")
    amap_key = _read_api_key("AMAP_API_KEY")

    settings = Settings(
        app_mode=app_mode,
        deepseek_api_key=deepseek_key,
        amap_api_key=amap_key,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
    )

    # Determine provider modes based on app_mode and key availability
    if app_mode == AppMode.TEST:
        # Force all mock in test mode
        settings.provider_status = ProviderStatus(
            llm=ProviderMode.MOCK,
            poi=ProviderMode.MOCK,
            route=ProviderMode.MOCK,
            weather=ProviderMode.MOCK,
            booking=ProviderMode.MOCK,
        )
        return settings

    if app_mode == AppMode.DEMO:
        # Demo mode: both keys are required, no fallback
        missing = []
        if not deepseek_key:
            missing.append("DEEPSEEK_API_KEY")
        if not amap_key:
            missing.append("AMAP_API_KEY")
        if missing:
            raise ConfigError(
                f"APP_MODE=demo requires {', '.join(missing)}. "
                f"Set these environment variables or switch to APP_MODE=development for fallback mode."
            )
        settings.provider_status = ProviderStatus(
            llm=ProviderMode.REAL,
            poi=ProviderMode.REAL,
            route=ProviderMode.REAL,
            weather=ProviderMode.REAL,
            booking=ProviderMode.MOCK,  # booking always mock as per requirements
        )
        return settings

    # Development mode: real if key available, mock as fallback
    ps = ProviderStatus()
    ps.llm = ProviderMode.REAL if deepseek_key else ProviderMode.MOCK
    ps.poi = ProviderMode.REAL if amap_key else ProviderMode.MOCK
    ps.route = ProviderMode.REAL if amap_key else ProviderMode.MOCK
    ps.weather = ProviderMode.REAL if amap_key else ProviderMode.MOCK
    ps.booking = ProviderMode.MOCK  # booking always mock
    settings.provider_status = ps
    return settings


# Module-level singleton, lazy-loaded
_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings


def reset_settings() -> None:
    """Reset cached settings. Useful for testing."""
    global _settings
    _settings = None
