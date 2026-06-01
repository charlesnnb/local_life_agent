"""DeepSeek LLM Provider — real API calls to DeepSeek for intent parsing and explanation."""

import json
import logging
import httpx
from typing import Any

from backend.providers.llm.base import LLMProvider, LLMProviderInfo
from backend.agent.intent_schema import ParsedIntent

logger = logging.getLogger(__name__)

DEEPSEEK_CHAT_URL = "https://api.deepseek.com/v1/chat/completions"
DEFAULT_MODEL = "deepseek-chat"
REQUEST_TIMEOUT = 30.0

INTENT_SYSTEM_PROMPT = """你是一个本地生活规划助手的意图解析模块。你的任务是从用户自然语言输入中提取结构化信息。

规则：
1. 只提取用户明确提到的信息，未提及的字段设为 null。
2. 不要编造任何信息 — 用户没说城市就不要猜城市，没说预算就不要编预算。
3. 如果你不确定某个字段的值，宁可设为 null。
4. 将所有未提及的字段名放入 missing_fields 列表。

输出必须是严格的 JSON 格式，不要包含 markdown 代码块标记或其他文字。

字段说明：
- city: 城市名，如 "北京"、"上海"
- area: 区域名，如 "朝阳区"、"浦东新区"
- date_or_time: 日期或时间描述，如 "周六下午"、"6月15日"、"下午2点"
- party_size: 参与人数（整数）
- budget_per_person: 人均预算（数字，单位元）
- scene: 场景类型，可选值: "family"（家庭）, "friends"（朋友）, "couple"（情侣）, "solo"（单人）, "business"（商务）
- cuisine_preferences: 偏好菜系，如 ["川菜", "日料"]
- dislikes_or_restrictions: 忌口或限制，如 ["不吃辣", "素食"]
- activity_after_meal: 饭后活动偏好，如 "逛街"、"看电影"
- transport_preference: 交通偏好，可选值: "driving"（开车）, "taxi"（打车）, "transit"（公共交通）, "walking"（步行）
- indoor_preference: 是否偏好室内，true/false/null
- raw_user_input: 用户原始输入（原样返回）
- confidence: 解析置信度 (0.0-1.0)
- missing_fields: 用户未提及的字段名列表"""


class DeepSeekProvider(LLMProvider):
    """Real DeepSeek LLM provider for intent parsing and explanation."""

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self._api_key = api_key
        self._model = model
        self._info = LLMProviderInfo(name="deepseek", mode="real", model=model)

    @property
    def info(self) -> LLMProviderInfo:
        return self._info

    async def parse_intent(self, user_input: str) -> dict:
        """Call DeepSeek to parse user intent into structured constraints."""
        messages = [
            {"role": "system", "content": INTENT_SYSTEM_PROMPT},
            {"role": "user", "content": user_input},
        ]

        try:
            raw = await self._call_chat(messages, temperature=0.1)
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            # Validate through Pydantic
            result = ParsedIntent(**parsed)
            # Compute missing_fields from actual None values
            result.missing_fields = self._compute_missing_fields(result)
            result.raw_user_input = user_input
            return result.model_dump()
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"DeepSeek intent parsing failed: {e}")
            raise

    async def generate_explanation(
        self,
        user_input: str,
        parsed_intent: dict,
        candidates: list[dict],
        scores: list[dict],
        final_plan: dict,
        provider_status: dict,
    ) -> str:
        """Generate explanation based on real data. Must not invent facts."""
        # Build a data-only prompt — the LLM explains but doesn't invent
        context = {
            "user_input": user_input,
            "parsed_intent": parsed_intent,
            "candidates": candidates,
            "scores": scores,
            "final_plan": final_plan,
            "provider_status": provider_status,
        }

        system = (
            "你是一个本地生活规划助手。请根据提供的真实数据生成推荐方案的解释。\n"
            "规则：\n"
            "1. 只能使用下面提供的数据，不要编造任何评分、价格、距离、营业时间等信息。\n"
            "2. 如果某些数据标记为 unknown，请明确告知用户该信息暂时未知。\n"
            "3. 如果数据来自模拟数据（provider_status 显示 mock），请如实说明。\n"
            "4. 解释应该自然、有帮助，让用户理解为什么推荐这个方案。"
        )

        user_msg = json.dumps(context, ensure_ascii=False, indent=2)

        try:
            result = await self._call_chat(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.7,
                max_tokens=2000,
            )
            return result.strip()
        except Exception as e:
            logger.error(f"DeepSeek explanation generation failed: {e}")
            return f"抱歉，自动生成解释时出错。请查看下方方案详情。\n错误: {str(e)}"

    async def _call_chat(
        self,
        messages: list[dict],
        temperature: float = 0.1,
        max_tokens: int = 2000,
    ) -> str:
        """Make a chat completion call to DeepSeek API."""
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.post(
                DEEPSEEK_CHAT_URL, json=payload, headers=headers
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return content

    @staticmethod
    def _compute_missing_fields(parsed: ParsedIntent) -> list[str]:
        """Compute which fields the user didn't provide."""
        # Fields that are always considered "user-provided" if non-null
        user_fields = [
            "city", "area", "date_or_time", "party_size", "budget_per_person",
            "scene", "cuisine_preferences", "dislikes_or_restrictions",
            "activity_after_meal", "transport_preference", "indoor_preference",
        ]
        missing = []
        for f in user_fields:
            val = getattr(parsed, f, None)
            if val is None or (isinstance(val, list) and len(val) == 0):
                missing.append(f)
        return missing
