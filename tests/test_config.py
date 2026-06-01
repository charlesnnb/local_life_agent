"""Tests for config/settings module."""

import os
import pytest
from backend.config.settings import (
    load_settings,
    reset_settings,
    get_settings,
    AppMode,
    ProviderMode,
    ConfigError,
    Settings,
    ProviderStatus,
)


@pytest.fixture(autouse=True)
def clear_settings():
    reset_settings()
    yield
    reset_settings()


@pytest.fixture
def clean_env(monkeypatch):
    for var in ["APP_MODE", "DEEPSEEK_API_KEY", "AMAP_API_KEY", "HOST", "PORT"]:
        monkeypatch.delenv(var, raising=False)


def test_default_mode_is_development(clean_env):
    settings = load_settings()
    assert settings.app_mode == AppMode.DEVELOPMENT
    assert settings.is_development is True


def test_development_mode_without_keys_uses_mock(clean_env, monkeypatch):
    monkeypatch.setenv("APP_MODE", "development")
    settings = load_settings()
    assert settings.provider_status.llm == ProviderMode.MOCK
    assert settings.provider_status.poi == ProviderMode.MOCK
    assert settings.provider_status.route == ProviderMode.MOCK
    assert settings.provider_status.weather == ProviderMode.MOCK


def test_development_mode_with_keys_uses_real(clean_env, monkeypatch):
    monkeypatch.setenv("APP_MODE", "development")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-deepseek")
    monkeypatch.setenv("AMAP_API_KEY", "test-amap-key")
    settings = load_settings()
    assert settings.provider_status.llm == ProviderMode.REAL
    assert settings.provider_status.poi == ProviderMode.REAL
    assert settings.provider_status.route == ProviderMode.REAL
    assert settings.provider_status.weather == ProviderMode.REAL
    # Booking is always mock
    assert settings.provider_status.booking == ProviderMode.MOCK


def test_demo_mode_requires_both_keys(clean_env, monkeypatch):
    monkeypatch.setenv("APP_MODE", "demo")
    with pytest.raises(ConfigError, match="DEEPSEEK_API_KEY"):
        load_settings()

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    with pytest.raises(ConfigError, match="AMAP_API_KEY"):
        load_settings()


def test_demo_mode_with_both_keys_succeeds(clean_env, monkeypatch):
    monkeypatch.setenv("APP_MODE", "demo")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-deepseek")
    monkeypatch.setenv("AMAP_API_KEY", "test-amap-key")
    settings = load_settings()
    assert settings.app_mode == AppMode.DEMO
    assert settings.provider_status.llm == ProviderMode.REAL
    assert settings.provider_status.poi == ProviderMode.REAL
    assert settings.provider_status.route == ProviderMode.REAL
    assert settings.provider_status.weather == ProviderMode.REAL


def test_test_mode_forces_all_mock(clean_env, monkeypatch):
    monkeypatch.setenv("APP_MODE", "test")
    # Even with keys set, should still be mock
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("AMAP_API_KEY", "test-key")
    settings = load_settings()
    assert settings.app_mode == AppMode.TEST
    assert settings.provider_status.llm == ProviderMode.MOCK
    assert settings.provider_status.poi == ProviderMode.MOCK
    assert settings.provider_status.route == ProviderMode.MOCK
    assert settings.provider_status.weather == ProviderMode.MOCK


def test_invalid_app_mode_raises(clean_env, monkeypatch):
    monkeypatch.setenv("APP_MODE", "invalid_mode")
    with pytest.raises(ConfigError, match="Invalid APP_MODE"):
        load_settings()


def test_provider_status_to_dict():
    ps = ProviderStatus(
        llm=ProviderMode.REAL,
        poi=ProviderMode.MOCK,
        route=ProviderMode.FALLBACK,
        weather=ProviderMode.MOCK,
        booking=ProviderMode.MOCK,
    )
    d = ps.to_dict()
    assert d == {
        "llm": "real",
        "poi": "mock",
        "route": "fallback",
        "weather": "mock",
        "booking": "mock",
    }


def test_get_settings_caches(clean_env, monkeypatch):
    monkeypatch.setenv("APP_MODE", "test")
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2


def test_settings_api_keys_read(clean_env, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-my-key")
    monkeypatch.setenv("AMAP_API_KEY", "amap-my-key")
    settings = load_settings()
    assert settings.deepseek_api_key == "sk-my-key"
    assert settings.amap_api_key == "amap-my-key"


def test_empty_string_keys_treated_as_none(clean_env, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    monkeypatch.setenv("AMAP_API_KEY", "   ")
    settings = load_settings()
    assert settings.deepseek_api_key is None
    assert settings.amap_api_key is None
