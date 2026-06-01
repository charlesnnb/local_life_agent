"""LLM provider factory — creates the correct provider based on app mode and settings."""

import logging
from backend.config.settings import get_settings, AppMode, ProviderMode
from backend.providers.llm.base import LLMProvider
from backend.providers.llm.deepseek_provider import DeepSeekProvider
from backend.providers.llm.mock_provider import MockLLMProvider

logger = logging.getLogger(__name__)


def create_llm_provider() -> LLMProvider:
    """Create the appropriate LLM provider based on current app settings.

    - test mode: always mock
    - demo mode: always real (DeepSeek), key already validated at startup
    - development mode: real if key available, mock if not
    """
    settings = get_settings()
    status = settings.provider_status.llm

    if status == ProviderMode.MOCK:
        logger.info("LLM provider: mock (mode=%s)", settings.app_mode.value)
        return MockLLMProvider()

    if status == ProviderMode.REAL:
        if not settings.deepseek_api_key:
            raise RuntimeError("LLM provider is REAL but DEEPSEEK_API_KEY is missing")
        logger.info("LLM provider: DeepSeek (mode=%s, model=%s)", settings.app_mode.value, "deepseek-chat")
        return DeepSeekProvider(api_key=settings.deepseek_api_key)

    raise RuntimeError(f"Unexpected LLM provider status: {status}")
