"""Explanation Generator: produces natural language explanations based on real data."""

import logging
from backend.providers.llm.base import LLMProvider

logger = logging.getLogger(__name__)


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

        return await self._llm.generate_explanation(
            user_input=user_input,
            parsed_intent=parsed_intent,
            candidates=candidates,
            scores=scores,
            final_plan=plan,
            provider_status=provider_status,
        )
