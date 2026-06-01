"""LLM provider interfaces and base classes."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class LLMProviderInfo:
    """Metadata about an LLM provider instance."""
    name: str  # "deepseek", "mock"
    mode: str  # "real", "mock", "fallback"
    model: str | None = None


class LLMProvider(ABC):
    """Abstract interface for LLM-based text processing.

    The LLM is responsible for:
    - Intent parsing: natural language → structured constraints
    - Explanation generation: data + scores → natural language explanation

    It is NOT allowed to invent facts about locations, ratings, prices,
    operating hours, or route details. Those must come from real API providers.
    """

    @abstractmethod
    async def parse_intent(self, user_input: str) -> dict:
        """Parse natural language user input into structured constraints.

        Returns a dict matching IntentParseResult schema.
        """
        ...

    @abstractmethod
    async def generate_explanation(
        self,
        user_input: str,
        parsed_intent: dict,
        candidates: list[dict],
        scores: list[dict],
        final_plan: dict,
        provider_status: dict,
    ) -> str:
        """Generate a natural-language explanation of the recommended plan.

        Must be based on the provided data, not invent facts.
        """
        ...

    @property
    @abstractmethod
    def info(self) -> LLMProviderInfo:
        ...
