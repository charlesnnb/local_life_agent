"""Mock LLM provider — rule-based fallback for test/development modes."""

import json
import re
import logging
from backend.providers.llm.base import LLMProvider, LLMProviderInfo
from backend.agent.intent_schema import ParsedIntent

logger = logging.getLogger(__name__)

# All known cities for location extraction
KNOWN_CITIES = [
    "北京", "上海", "广州", "深圳", "杭州", "成都", "南京", "武汉", "西安", "重庆",
    "沧州", "沧州市", "天津", "苏州", "郑州", "长沙", "青岛", "大连", "厦门", "福州",
    "合肥", "济南", "沈阳", "哈尔滨", "昆明", "贵阳", "南宁", "海口", "拉萨",
    "乌鲁木齐", "呼和浩特", "石家庄", "太原", "兰州", "西宁", "银川", "南昌",
    "温州", "宁波", "无锡", "佛山", "东莞", "珠海",
    "湖州", "湖州市", "安吉", "安吉县", "泌阳", "泌阳县", "绍兴", "绍兴市",
    "嘉兴", "嘉兴市", "金华", "金华市", "台州", "台州市", "泉州", "泉州市",
    "漳州", "漳州市", "扬州", "扬州市", "徐州", "徐州市", "烟台", "烟台市",
    "惠州", "惠州市", "中山", "中山市", "常州", "常州市", "南通", "南通市",
    "洛阳", "洛阳市", "襄阳", "襄阳市", "宜昌", "宜昌市", "九江", "九江市",
    "赣州", "赣州市", "桂林", "桂林市", "三亚", "三亚市", "拉萨", "拉萨市",
]

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
        """Parse intent using rule-based keyword matching."""
        result = self._rule_parse(user_input)
        result["raw_user_input"] = user_input
        result["confidence"] = 0.3  # low confidence for mock
        parsed = ParsedIntent(**result)
        parsed.missing_fields = self._compute_missing_fields(parsed)
        return parsed.model_dump()

    async def generate_explanation(
        self, user_input, parsed_intent, candidates, scores, final_plan, provider_status,
    ) -> str:
        parts = ["[Mock 模式 — 以下解释由规则模板生成，非真实 LLM]\n"]
        scene = parsed_intent.get("scene")
        if scene == "family":
            parts.append("根据您的需求，为您推荐一个适合家庭的休闲方案。")
        elif scene == "friends":
            parts.append("根据您的需求，为您推荐一个适合朋友聚会的方案。")
        elif scene == "solo":
            parts.append("根据您的需求，为您推荐一个适合个人的出行方案。")
        else:
            parts.append("根据您的需求，为您推荐一个本地休闲方案。")
        poi_names = [c.get("name", "未知地点") for c in candidates[:3]]
        if poi_names:
            parts.append(f"可选地点包括：{'、'.join(poi_names)}。")
        missing = parsed_intent.get("missing_fields", [])
        if missing:
            parts.append(f"注意：以下信息未提供，可能影响推荐准确性：{', '.join(missing)}。")
        parts.append("\n如需更准确的推荐，请提供更多偏好信息（人数、预算、菜系偏好等）。")
        return "\n".join(parts)

    def _rule_parse(self, user_input: str) -> dict:
        """Keyword-based intent parsing."""
        result = dict(MOCK_PARSE_RESPONSES["default"])

        # ── Scene detection ──────────────────────────────────────
        family_kw = ["老婆", "孩子", "家庭", "小孩", "宝宝", "女儿", "儿子", "家人", "亲子"]
        friends_kw = ["朋友", "哥们", "闺蜜", "聚会", "组队", "群", "几个朋友"]
        couple_kw = ["女朋友", "男朋友", "约会", "情侣", "二人世界"]
        solo_kw = ["自己", "一个人", "独自", "solo"]

        if re.search(r"\d+\s*男\s*\d+\s*女", user_input):
            result["scene"] = "friends"

        if any(kw in user_input for kw in family_kw):
            result["scene"] = "family"
        elif any(kw in user_input for kw in couple_kw):
            result["scene"] = "couple"
        elif any(kw in user_input for kw in friends_kw):
            result["scene"] = "friends"
        elif any(kw in user_input for kw in solo_kw):
            result["scene"] = "solo"
        elif any(kw in user_input for kw in ["旅游", "景点", "酒吧"]):
            # Tourism or nightlife → solo / casual day trip
            result["scene"] = "solo"

        # ── City/area extraction from query ──────────────────────
        # Pattern: 我在XX / 当前位置XX / 从XX出发 / 我人在XX
        loc_patterns = [
            r"我在\s*([一-龥]{2,6}(?:市|区|县)?)",
            r"当前位置[是]?\s*([一-龥]{2,6}(?:市|区|县)?)",
            r"从\s*([一-龥]{2,6}(?:市|区|县)?)\s*出发",
            r"我人在\s*([一-龥]{2,6}(?:市|区|县)?)",
            r"在\s*([一-龥]{2,6}(?:市|区|县)?)\s*[,，。.?？!！\s]",
        ]
        for pat in loc_patterns:
            m = re.search(pat, user_input)
            if m:
                extracted = m.group(1)
                # Normalize: 沧州市 → 沧州 for city field
                result["city"] = extracted.rstrip("市")
                result["area"] = None
                # Store raw extracted location for location_resolver
                result["_extracted_location"] = extracted
                break

        # Also check against known city list
        if not result["city"]:
            for city in KNOWN_CITIES:
                if city in user_input:
                    result["city"] = city.rstrip("市")
                    result["_extracted_location"] = city
                    break

        # ── Time window detection ────────────────────────────────
        has_morning = any(kw in user_input for kw in ["早上", "上午", "早晨", "刚醒"])
        has_noon = any(kw in user_input for kw in ["中午", "午饭", "午餐"])
        has_evening = any(kw in user_input for kw in ["晚上", "傍晚", "晚饭", "晚餐", "酒吧"])
        has_afternoon = any(kw in user_input for kw in ["下午"])

        if has_morning:
            result["date_or_time"] = "早上"
        elif has_afternoon:
            result["date_or_time"] = "下午"
        elif has_evening:
            result["date_or_time"] = "晚上"

        # Store time slots for multi-period planning
        result["_time_slots"] = []
        if has_morning:
            result["_time_slots"].append({"period": "morning", "need": "activity"})
        if has_noon:
            result["_time_slots"].append({"period": "noon", "need": "meal"})
        if has_evening:
            result["_time_slots"].append({"period": "evening", "need": "bar" if "酒吧" in user_input else "meal"})
        if has_afternoon:
            result["_time_slots"].append({"period": "afternoon", "need": "activity"})

        # Category preferences
        if "酒吧" in user_input:
            result["activity_after_meal"] = "酒吧"
        if "旅游" in user_input or "景点" in user_input:
            if not result["cuisine_preferences"]:
                result["cuisine_preferences"] = []

        # ── Party size ───────────────────────────────────────────
        m = re.search(r"(\d+)\s*个?\s*人", user_input)
        if m:
            result["party_size"] = int(m.group(1))

        # ── Budget ───────────────────────────────────────────────
        m = re.search(r"人均\s*(\d+)", user_input)
        if m:
            result["budget_per_person"] = float(m.group(1))

        # ── Transport ────────────────────────────────────────────
        if "开车" in user_input:
            result["transport_preference"] = "driving"
        elif "打车" in user_input:
            result["transport_preference"] = "taxi"
        elif "地铁" in user_input or "公交" in user_input:
            result["transport_preference"] = "transit"

        # ── Indoor/outdoor ──────────────────────────────────────
        if "室内" in user_input:
            result["indoor_preference"] = True
        elif "户外" in user_input or "室外" in user_input:
            result["indoor_preference"] = False

        # ── Cuisine ─────────────────────────────────────────────
        cuisines = ["川菜", "粤菜", "日料", "韩餐", "火锅", "烧烤", "西餐", "东南亚菜", "湘菜", "好吃的"]
        found = [c for c in cuisines if c in user_input]
        if found:
            result["cuisine_preferences"] = [c for c in found if c != "好吃的"]

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
