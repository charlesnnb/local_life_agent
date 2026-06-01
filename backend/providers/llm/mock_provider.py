"""Mock LLM provider — rule-based fallback for test/development modes."""

import json
import logging
from backend.providers.llm.base import LLMProvider, LLMProviderInfo
from backend.agent.intent_schema import ParsedIntent

logger = logging.getLogger(__name__)

# Mock responses for test mode — hardcoded but clearly labeled as mock
MOCK_PARSE_RESPONSES = {
    "default": {
        "city": None,
        "area": None,
        "date_or_time": None,
        "party_size": None,
        "budget_per_person": None,
        "scene": None,
        "cuisine_preferences": None,
        "dislikes_or_restrictions": None,
        "activity_after_meal": None,
        "transport_preference": None,
        "indoor_preference": None,
        "confidence": 0.1,
        "missing_fields": [
            "city", "area", "date_or_time", "party_size", "budget_per_person",
            "scene", "cuisine_preferences", "dislikes_or_restrictions",
            "activity_after_meal", "transport_preference", "indoor_preference",
        ],
    }
}


class MockLLMProvider(LLMProvider):
    """Rule-based mock LLM provider. Used in test mode or as fallback in development.

    Uses lightweight keyword matching for basic intent parsing.
    All results are clearly marked with low confidence and mock mode.
    """

    def __init__(self):
        self._info = LLMProviderInfo(name="mock", mode="mock", model=None)

    @property
    def info(self) -> LLMProviderInfo:
        return self._info

    async def parse_intent(self, user_input: str) -> dict:
        """Parse intent using rule-based keyword matching.

        This is intentionally limited — it doesn't try to fake real LLM quality.
        """
        result = self._rule_parse(user_input)
        result["raw_user_input"] = user_input
        result["confidence"] = 0.3  # low confidence for mock
        # Validate via Pydantic
        parsed = ParsedIntent(**result)
        parsed.missing_fields = self._compute_missing_fields(parsed)
        return parsed.model_dump()

    async def generate_explanation(
        self,
        user_input: str,
        parsed_intent: dict,
        candidates: list[dict],
        scores: list[dict],
        final_plan: dict,
        provider_status: dict,
    ) -> str:
        """Generate a simple template-based explanation. Clearly marked as mock."""
        parts = ["[Mock 模式 — 以下解释由规则模板生成，非真实 LLM]\n"]

        scene = parsed_intent.get("scene")
        if scene == "family":
            parts.append("根据您的需求，为您推荐一个适合家庭的休闲方案。")
        elif scene == "friends":
            parts.append("根据您的需求，为您推荐一个适合朋友聚会的方案。")
        else:
            parts.append("根据您的需求，为您推荐一个本地休闲方案。")

        # Mention candidates from real data
        poi_names = [c.get("name", "未知地点") for c in candidates[:3]]
        if poi_names:
            parts.append(f"可选地点包括：{'、'.join(poi_names)}。")

        # Mention unknown fields
        missing = parsed_intent.get("missing_fields", [])
        if missing:
            parts.append(f"注意：以下信息未提供，可能影响推荐准确性：{', '.join(missing)}。")

        parts.append("\n如需更准确的推荐，请提供更多偏好信息（人数、预算、菜系偏好等）。")
        return "\n".join(parts)

    def _rule_parse(self, user_input: str) -> dict:
        """Basic rule-based keyword matching. Deliberately limited."""
        result = dict(MOCK_PARSE_RESPONSES["default"])

        # Scene detection
        family_keywords = ["老婆", "孩子", "家庭", "小孩", "宝宝", "女儿", "儿子", "家人", "亲子"]
        friends_keywords = ["朋友", "哥们", "闺蜜", "聚会", "组队", "群"]
        couple_keywords = ["女朋友", "男朋友", "约会", "情侣", "二人世界", "老婆", "老公"]

        if any(kw in user_input for kw in family_keywords):
            result["scene"] = "family"
        elif any(kw in user_input for kw in couple_keywords):
            result["scene"] = "couple"
        elif any(kw in user_input for kw in friends_keywords):
            result["scene"] = "friends"

        # Party size
        import re
        match = re.search(r"(\d+)\s*个?\s*人", user_input)
        if match:
            result["party_size"] = int(match.group(1))

        # City detection
        cities = ["北京", "上海", "广州", "深圳", "杭州", "成都", "南京", "武汉", "西安", "重庆"]
        for city in cities:
            if city in user_input:
                result["city"] = city
                break

        # Budget
        budget_match = re.search(r"人均\s*(\d+)", user_input)
        if budget_match:
            result["budget_per_person"] = float(budget_match.group(1))

        # Transport
        if "开车" in user_input:
            result["transport_preference"] = "driving"
        elif "打车" in user_input:
            result["transport_preference"] = "taxi"
        elif "地铁" in user_input or "公交" in user_input:
            result["transport_preference"] = "transit"

        # Indoor/outdoor
        if "室内" in user_input:
            result["indoor_preference"] = True
        elif "户外" in user_input or "室外" in user_input:
            result["indoor_preference"] = False

        ## Cuisine preferences
        cuisines = ["川菜", "粤菜", "日料", "韩餐", "火锅", "烧烤", "西餐", "东南亚菜", "湘菜"]
        found = [c for c in cuisines if c in user_input]
        if found:
            result["cuisine_preferences"] = found

        return result

    @staticmethod
    def _compute_missing_fields(parsed: ParsedIntent) -> list[str]:
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
