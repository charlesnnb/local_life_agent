"""Small OpenAI-compatible DeepSeek client with failure-safe responses."""

import json
import logging
from typing import Any

import httpx

from src.config.settings import Settings, settings


logger = logging.getLogger(__name__)


class DeepSeekProvider:
    """Call DeepSeek without leaking transport failures into planning."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        enabled: bool | None = None,
        client: httpx.Client | None = None,
        runtime_settings: Settings = settings,
    ):
        self.enabled = (
            runtime_settings.enable_llm if enabled is None else enabled
        )
        self.api_key = (
            runtime_settings.deepseek_api_key
            if api_key is None
            else api_key.strip()
        )
        self.base_url = (
            runtime_settings.deepseek_base_url
            if base_url is None
            else base_url.rstrip("/")
        )
        self.model = model or runtime_settings.deepseek_model
        self.timeout = timeout or runtime_settings.llm_timeout_seconds
        self._client = client
        self.last_error: str | None = None

    @property
    def is_available(self) -> bool:
        return self.enabled and bool(self.api_key)

    @property
    def unavailable_reason(self) -> str | None:
        if not self.enabled:
            return "DeepSeek 未启用"
        if not self.api_key:
            return "缺少 DEEPSEEK_API_KEY"
        return None

    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        schema_name: str,
    ) -> dict[str, Any] | None:
        """Request strict JSON and parse it with json.loads only."""
        payload = self._chat_payload(system_prompt, user_prompt)
        payload["response_format"] = {"type": "json_object"}
        content = self._request_content(payload, schema_name)
        if content is None:
            return None
        try:
            result = json.loads(content)
        except (TypeError, json.JSONDecodeError) as exc:
            self.last_error = f"{schema_name} 返回非法 JSON: {exc}"
            logger.warning(self.last_error)
            return None
        if not isinstance(result, dict):
            self.last_error = f"{schema_name} 返回值不是 JSON object"
            return None
        return result

    def chat_text(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str | None:
        """Request plain text for future non-structured use cases."""
        return self._request_content(
            self._chat_payload(system_prompt, user_prompt),
            "text",
        )

    def _chat_payload(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> dict[str, Any]:
        return {
            "model": self.model,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

    def _request_content(
        self,
        payload: dict[str, Any],
        operation: str,
    ) -> str | None:
        self.last_error = None
        if not self.is_available:
            self.last_error = self.unavailable_reason
            return None
        try:
            client = self._client or httpx.Client()
            response = client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ValueError("empty model content")
            return content.strip()
        except Exception as exc:
            self.last_error = f"DeepSeek {operation} 调用失败: {exc}"
            logger.warning(self.last_error)
            return None
