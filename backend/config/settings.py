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
    DEMO = "demo"           # legacy — equivalent to demo_real
    DEMO_REAL = "demo_real"  # real APIs first, mock fallback; execution always mock
    DEMO_SAFE = "demo_safe"  # all mock, guaranteed stable
    TEST = "test"            # forced all mock for automated testing


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
    execution: ProviderMode = ProviderMode.MOCK

    def to_dict(self) -> dict:
        return {
            "llm": self.llm.value,
            "poi": self.poi.value,
            "route": self.route.value,
            "weather": self.weather.value,
            "booking": self.booking.value,
            "execution": self.execution.value,
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
        return self.app_mode in (AppMode.DEMO, AppMode.DEMO_REAL)

    @property
    def is_demo_real(self) -> bool:
        return self.app_mode in (AppMode.DEMO, AppMode.DEMO_REAL)

    @property
    def is_demo_safe(self) -> bool:
        return self.app_mode == AppMode.DEMO_SAFE

    @property
    def is_test(self) -> bool:
        return self.app_mode == AppMode.TEST

    @property
    def safe_for_live_demo(self) -> bool:
        """True if this mode is guaranteed stable (no external API dependencies)."""
        return self.app_mode in (AppMode.DEMO_SAFE, AppMode.TEST)


def _read_app_mode() -> AppMode:
    raw = os.getenv("APP_MODE", "development").strip().lower()
    try:
        return AppMode(raw)
    except ValueError:
        raise ConfigError(
            f"Invalid APP_MODE '{raw}'. Must be one of: "
            f"development, demo, demo_real, demo_safe, test"
        )


def _read_api_key(env_var: str) -> str | None:
    val = os.getenv(env_var, "").strip()
    return val if val else None


def load_settings() -> Settings:
    """Load settings from environment variables.

    Raises ConfigError in demo modes when required keys are missing.
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

    # ── TEST mode: force all mock ──────────────────────────────────
    if app_mode == AppMode.TEST:
        settings.provider_status = ProviderStatus(
            llm=ProviderMode.MOCK,
            poi=ProviderMode.MOCK,
            route=ProviderMode.MOCK,
            weather=ProviderMode.MOCK,
            booking=ProviderMode.MOCK,
            execution=ProviderMode.MOCK,
        )
        return settings

    # ── DEMO_SAFE mode: all mock, guaranteed stable ────────────────
    if app_mode == AppMode.DEMO_SAFE:
        settings.provider_status = ProviderStatus(
            llm=ProviderMode.MOCK,
            poi=ProviderMode.MOCK,
            route=ProviderMode.MOCK,
            weather=ProviderMode.MOCK,
            booking=ProviderMode.MOCK,
            execution=ProviderMode.MOCK,
        )
        return settings

    # ── DEMO_REAL (and legacy DEMO) mode: real first, mock fallback ─
    if app_mode in (AppMode.DEMO, AppMode.DEMO_REAL):
        has_deepseek = bool(deepseek_key)
        has_amap = bool(amap_key)
        ps = ProviderStatus()
        ps.llm = ProviderMode.REAL if has_deepseek else ProviderMode.MOCK
        ps.poi = ProviderMode.REAL if has_amap else ProviderMode.MOCK
        ps.route = ProviderMode.REAL if has_amap else ProviderMode.MOCK
        ps.weather = ProviderMode.REAL if has_amap else ProviderMode.MOCK
        ps.booking = ProviderMode.MOCK
        ps.execution = ProviderMode.MOCK  # execution always mock
        settings.provider_status = ps

        if not has_deepseek:
            print("[WARNING] DEMO_REAL: DEEPSEEK_API_KEY missing, LLM will use mock")
        if not has_amap:
            print("[WARNING] DEMO_REAL: AMAP_API_KEY missing, POI/Route/Weather will use mock")
        return settings

    # ── Development mode: real if key available, mock as fallback ──
    ps = ProviderStatus()
    ps.llm = ProviderMode.REAL if deepseek_key else ProviderMode.MOCK
    ps.poi = ProviderMode.REAL if amap_key else ProviderMode.MOCK
    ps.route = ProviderMode.REAL if amap_key else ProviderMode.MOCK
    ps.weather = ProviderMode.REAL if amap_key else ProviderMode.MOCK
    ps.booking = ProviderMode.MOCK
    ps.execution = ProviderMode.MOCK
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


def switch_app_mode(new_mode: str) -> Settings:
    """Switch app mode at runtime without restarting the server.

    Args:
        new_mode: 'demo_real', 'demo_safe', 'development', or 'test'

    Returns:
        The new Settings object.

    Raises:
        ConfigError if the mode string is invalid.
    """
    global _settings
    try:
        target = AppMode(new_mode.strip().lower())
    except ValueError:
        raise ConfigError(
            f"Invalid APP_MODE '{new_mode}'. Must be one of: "
            f"development, demo, demo_real, demo_safe, test"
        )

    # Persist to .env file
    _write_env_mode(new_mode)

    # Rebuild settings with the new mode
    _settings = _build_settings_for_mode(target)
    return _settings


def _build_settings_for_mode(app_mode: AppMode) -> Settings:
    """Build settings for a specific app mode."""
    deepseek_key = _read_api_key("DEEPSEEK_API_KEY")
    amap_key = _read_api_key("AMAP_API_KEY")

    settings = Settings(
        app_mode=app_mode,
        deepseek_api_key=deepseek_key,
        amap_api_key=amap_key,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
    )

    # TEST mode
    if app_mode == AppMode.TEST:
        settings.provider_status = ProviderStatus(
            llm=ProviderMode.MOCK, poi=ProviderMode.MOCK,
            route=ProviderMode.MOCK, weather=ProviderMode.MOCK,
            booking=ProviderMode.MOCK, execution=ProviderMode.MOCK,
        )
        return settings

    # DEMO_SAFE mode
    if app_mode == AppMode.DEMO_SAFE:
        settings.provider_status = ProviderStatus(
            llm=ProviderMode.MOCK, poi=ProviderMode.MOCK,
            route=ProviderMode.MOCK, weather=ProviderMode.MOCK,
            booking=ProviderMode.MOCK, execution=ProviderMode.MOCK,
        )
        return settings

    # DEMO_REAL / DEMO mode
    if app_mode in (AppMode.DEMO, AppMode.DEMO_REAL):
        has_ds = bool(deepseek_key)
        has_amap = bool(amap_key)
        ps = ProviderStatus()
        ps.llm = ProviderMode.REAL if has_ds else ProviderMode.MOCK
        ps.poi = ProviderMode.REAL if has_amap else ProviderMode.MOCK
        ps.route = ProviderMode.REAL if has_amap else ProviderMode.MOCK
        ps.weather = ProviderMode.REAL if has_amap else ProviderMode.MOCK
        ps.booking = ProviderMode.MOCK
        ps.execution = ProviderMode.MOCK
        settings.provider_status = ps
        return settings

    # Development mode
    ps = ProviderStatus()
    ps.llm = ProviderMode.REAL if deepseek_key else ProviderMode.MOCK
    ps.poi = ProviderMode.REAL if amap_key else ProviderMode.MOCK
    ps.route = ProviderMode.REAL if amap_key else ProviderMode.MOCK
    ps.weather = ProviderMode.REAL if amap_key else ProviderMode.MOCK
    ps.booking = ProviderMode.MOCK
    ps.execution = ProviderMode.MOCK
    settings.provider_status = ps
    return settings


def _write_env_mode(mode: str) -> None:
    """Persist APP_MODE to .env file."""
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if not env_path.exists():
        return
    try:
        with open(env_path, "r") as f:
            lines = f.readlines()
        with open(env_path, "w") as f:
            for line in lines:
                if line.startswith("APP_MODE="):
                    f.write(f"APP_MODE={mode}\n")
                else:
                    f.write(line)
    except Exception:
        pass  # Non-critical — mode still switched in memory
