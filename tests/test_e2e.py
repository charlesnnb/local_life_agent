"""End-to-end smoke test for the v2 orchestrator.

Tests the full pipeline in test mode (all mock providers).
"""

import os
import pytest
from backend.config.settings import reset_settings, get_settings


@pytest.fixture(autouse=True)
def set_test_mode(monkeypatch):
    monkeypatch.setenv("APP_MODE", "test")
    reset_settings()
    yield
    reset_settings()


@pytest.mark.asyncio
async def test_e2e_v2_mock_mode():
    """Full pipeline smoke test — test mode with mock providers."""
    from backend.agent.orchestrator_v2 import run_agent_v2

    result = await run_agent_v2(
        user_id="u_001",
        query="带孩子去公园玩，3个人，想吃川菜",
    )

    # Basic response structure
    assert result["status"] == "success"
    assert result["user_input"] == "带孩子去公园玩，3个人，想吃川菜"

    # Parsed intent
    parsed = result["parsed_intent"]
    assert parsed is not None
    assert parsed.get("scene") is not None  # should detect "family"
    assert parsed.get("party_size") == 3

    # Provider status
    assert result["provider_status"]["llm"] == "mock"
    assert result["provider_status"]["poi"] == "mock"

    # Rankings
    rankings = result["rankings"]
    assert "poi_rankings" in rankings
    assert "restaurant_rankings" in rankings

    # Itinerary
    assert len(result["itinerary"]) > 0

    # Summary (explanation)
    assert len(result["summary"]) > 0

    # Trace
    assert len(result["planning_trace"]) > 0

    # Candidate data
    assert "pois" in result["candidates"]


@pytest.mark.asyncio
async def test_e2e_v2_no_results_handling():
    """Test handling when no candidates are found."""
    from backend.agent.orchestrator_v2 import run_agent_v2

    # Use a query unlikely to match anything with mock data
    result = await run_agent_v2(
        user_id="u_001",
        query="找个地方",
    )

    assert result["status"] == "success"
    # May have empty candidates but shouldn't crash
    assert isinstance(result["candidates"]["pois"], list)
    assert isinstance(result["candidates"]["restaurants"], list)


@pytest.mark.asyncio
async def test_e2e_v2_unknown_fields_present():
    """Verify that unknown fields are properly surfaced in the response."""
    from backend.agent.orchestrator_v2 import run_agent_v2

    result = await run_agent_v2(
        user_id="u_001",
        query="北京找个地方吃饭",
    )

    # Check that poi_rankings include unknown_fields info
    poi_rankings = result["rankings"]["poi_rankings"]
    if poi_rankings:
        assert "unknown_fields" in poi_rankings[0]
        assert "unknown_penalty" in poi_rankings[0]

    # Check parsed intent missing_fields
    assert "missing_fields" in result["parsed_intent"]
