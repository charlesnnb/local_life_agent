"""Tests for DeepSeek and Mock LLM providers."""

import pytest
from backend.providers.llm.mock_provider import MockLLMProvider
from backend.agent.intent_schema import ParsedIntent


@pytest.fixture
def mock_provider():
    return MockLLMProvider()


@pytest.mark.asyncio
async def test_mock_provider_parses_family(mock_provider):
    result = await mock_provider.parse_intent("带孩子去公园玩，3个人")
    parsed = ParsedIntent(**result)
    assert parsed.scene == "family"
    assert parsed.party_size == 3
    assert parsed.confidence == 0.3
    assert "city" in parsed.missing_fields


@pytest.mark.asyncio
async def test_mock_provider_parses_friends(mock_provider):
    result = await mock_provider.parse_intent("和朋友们聚会，5个人吃火锅")
    parsed = ParsedIntent(**result)
    assert parsed.scene == "friends"
    assert parsed.party_size == 5
    assert parsed.cuisine_preferences == ["火锅"]


@pytest.mark.asyncio
async def test_mock_provider_parses_city(mock_provider):
    result = await mock_provider.parse_intent("去北京朝阳区找个地方吃饭")
    parsed = ParsedIntent(**result)
    assert parsed.city == "北京"


@pytest.mark.asyncio
async def test_mock_provider_parses_budget(mock_provider):
    result = await mock_provider.parse_intent("人均200左右，找个安静的餐厅")
    parsed = ParsedIntent(**result)
    assert parsed.budget_per_person == 200.0


@pytest.mark.asyncio
async def test_mock_provider_unknown_fields_set_null(mock_provider):
    result = await mock_provider.parse_intent("随便找个地方吃饭")
    parsed = ParsedIntent(**result)
    assert parsed.scene is None
    assert parsed.party_size is None
    assert parsed.budget_per_person is None
    assert parsed.city is None
    assert len(parsed.missing_fields) > 5


@pytest.mark.asyncio
async def test_mock_provider_raw_input_preserved(mock_provider):
    result = await mock_provider.parse_intent("我想带老婆去吃川菜")
    assert result["raw_user_input"] == "我想带老婆去吃川菜"


@pytest.mark.asyncio
async def test_mock_provider_explanation_mentions_mock(mock_provider):
    intent = {"scene": "family", "missing_fields": ["city", "budget_per_person"]}
    explanation = await mock_provider.generate_explanation(
        user_input="test",
        parsed_intent=intent,
        candidates=[{"name": "测试餐厅"}],
        scores=[],
        final_plan={},
        provider_status={"llm": "mock"},
    )
    assert "Mock" in explanation
    assert "city" in explanation


@pytest.mark.asyncio
async def test_mock_provider_passes_pydantic_validation(mock_provider):
    """Every mock result must pass Pydantic schema validation."""
    test_inputs = [
        "带孩子去玩",
        "和朋友们聚会吃火锅5个人",
        "找个人均200的川菜馆",
        "随便吃点",
        "",  # empty input
        "明天下午想去朝阳大悦城逛逛然后吃饭",
    ]
    for inp in test_inputs:
        result = await mock_provider.parse_intent(inp)
        # Should not raise
        validated = ParsedIntent(**result)
        assert validated.raw_user_input == inp
        assert 0.0 <= validated.confidence <= 1.0
