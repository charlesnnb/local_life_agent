"""Explanation Generator: produces natural language explanations based on real data."""

import re
import logging
from backend.providers.llm.base import LLMProvider

logger = logging.getLogger(__name__)


def sanitize_markdown(text: str) -> str:
    """Remove markdown formatting artifacts from LLM-generated text.

    Cleans up **bold**, ### headers, ``` code blocks, excessive newlines,
    and other markdown syntax that shouldn't appear in user-facing text.
    """
    if not text:
        return text
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # **bold** → bold
    text = re.sub(r'#{2,}\s*', '', text)              # ### headers
    text = re.sub(r'```[^`]*```', '', text)            # ``` code blocks ```
    text = re.sub(r'`([^`]+)`', r'\1', text)           # `inline code`
    text = re.sub(r'^\s*[-*]\s', '', text, flags=re.MULTILINE)  # markdown bullets
    text = re.sub(r'\n{3,}', '\n\n', text)             # collapse excessive newlines
    text = text.strip()
    return text


class ExplanationGenerator:
    """Generates human-readable plan explanations.

    In real mode: uses DeepSeek to generate natural language from real data.
    In mock mode: uses template-based generation.

    The LLM is given the real provider data and score breakdowns — it is
    NOT allowed to invent any facts about locations, ratings, prices, etc.
    """

    def __init__(self, llm_provider: LLMProvider):
        self._llm = llm_provider

    async def generate(
        self,
        user_input: str,
        parsed_intent: dict,
        plan: dict,
        provider_status: dict,
    ) -> str:
        """Generate a natural-language explanation of the plan.

        Args:
            user_input: Original user query.
            parsed_intent: Structured intent from LLM parser.
            plan: Complete plan from PlanGenerator.
            provider_status: Provider mode info (real/mock per provider).
        """
        # Extract the data the LLM can reference
        candidates = []
        if plan.get("top_poi"):
            candidates.append(plan["top_poi"])
        if plan.get("top_restaurant"):
            candidates.append(plan["top_restaurant"])

        scores = []
        if plan.get("top_poi_score"):
            scores.append(plan["top_poi_score"])
        if plan.get("top_restaurant_score"):
            scores.append(plan["top_restaurant_score"])

        result = await self._llm.generate_explanation(
            user_input=user_input,
            parsed_intent=parsed_intent,
            candidates=candidates,
            scores=scores,
            final_plan=plan,
            provider_status=provider_status,
        )
        return sanitize_markdown(result)
