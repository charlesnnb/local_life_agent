"""Priority 4 coverage for profiles, weights, APIs, and ranking."""

import asyncio

import httpx
import pytest

from src.app import app
from src.core.intent_parser import parse_intent
from src.core.ranking import rank_pois, rank_restaurants
from src.schemas.models import RouteEstimate, UserPreference
from src.services.preference_service import (
    build_preference_weights,
    reset_current_preference,
)


QUERY = "今天下午想带老婆孩子出去玩几个小时，别太远，孩子5岁，老婆最近在减肥"


@pytest.fixture(autouse=True)
def reset_preferences():
    reset_current_preference()
    yield
    reset_current_preference()


async def _request(method: str, path: str, json: dict | None = None):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        return await client.request(method, path, json=json)


def test_default_preference_generates_normalized_weights():
    weights = build_preference_weights(UserPreference())

    assert abs(sum(weights.model_dump().values()) - 1.0) < 0.000001
    assert weights.distance_weight > 0
    assert weights.activity_match_weight > 0
    assert weights.diet_match_weight > 0


def test_preference_api_saves_and_returns_current_profile():
    payload = {
        "activity_types": ["Citywalk", "展览"],
        "max_travel_minutes": 15,
        "dining_preferences": ["性价比"],
        "activity_intensity": "medium",
        "budget_level": "low",
        "prefer_indoor": True,
        "prefer_low_wait": True,
    }

    saved = asyncio.run(_request("POST", "/api/preferences", payload))
    current = asyncio.run(_request("GET", "/api/preferences/current"))

    assert saved.status_code == 200
    assert current.status_code == 200
    assert current.json()["preference"] == payload
    assert abs(sum(current.json()["weights"].values()) - 1.0) < 0.000001


def test_default_preference_endpoint_includes_questionnaire_options():
    response = asyncio.run(_request("GET", "/api/preferences/default"))

    assert response.status_code == 200
    payload = response.json()
    assert "亲子乐园" in payload["options"]["activity_types"]
    assert payload["options"]["max_travel_minutes"] == [15, 30, 45]
    assert payload["preference"]
    assert payload["weights"]


def test_child_preference_promotes_child_friendly_poi():
    intent = parse_intent(QUERY)
    preference = UserPreference(
        activity_types=["亲子乐园"],
        dining_preferences=[],
    )
    weights = build_preference_weights(preference)
    candidates = [
        {
            "id": "child",
            "name": "亲子互动馆",
            "type": "亲子乐园",
            "tags": ["kids", "playground", "educational"],
            "age_range": [2, 12],
            "suitable_scenes": ["family"],
            "rating": 4.5,
            "price": 80,
            "indoor": True,
            "wait_time_min": 10,
            "avg_duration_min": 90,
        },
        {
            "id": "generic",
            "name": "普通室内空间",
            "type": "普通活动",
            "tags": ["indoor"],
            "age_range": [0, 99],
            "suitable_scenes": ["family"],
            "rating": 4.5,
            "price": 80,
            "indoor": True,
            "wait_time_min": 10,
            "avg_duration_min": 90,
        },
    ]
    routes = {
        item["id"]: RouteEstimate(distance_km=2, duration_min=15)
        for item in candidates
    }

    ranked = rank_pois(
        candidates,
        intent,
        routes,
        {"outdoor_friendly": True},
        preference,
        weights,
    )

    assert ranked[0]["id"] == "child"
    assert (
        ranked[0]["score_components"]["child_friendly"]
        > ranked[1]["score_components"]["child_friendly"]
    )


def test_citywalk_preference_promotes_citywalk_over_photo_spot():
    intent = parse_intent("今天下午和朋友出去玩，想聊天拍照")
    preference = UserPreference(
        activity_types=["Citywalk"],
        dining_preferences=[],
    )
    candidates = [
        {
            "id": "walk",
            "name": "历史街区路线",
            "type": "citywalk",
            "tags": ["outdoor", "historic", "photo_friendly"],
            "age_range": [0, 99],
            "suitable_scenes": ["friends"],
            "rating": 4.4,
            "price": 0,
            "indoor": False,
            "wait_time_min": 2,
            "avg_duration_min": 60,
        },
        {
            "id": "mall",
            "name": "商场拍照展",
            "type": "商场活动",
            "tags": ["indoor", "shopping", "photo_friendly"],
            "age_range": [0, 99],
            "suitable_scenes": ["friends"],
            "rating": 4.4,
            "price": 0,
            "indoor": True,
            "wait_time_min": 2,
            "avg_duration_min": 60,
        },
    ]
    routes = {
        item["id"]: RouteEstimate(distance_km=2, duration_min=15)
        for item in candidates
    }

    ranked = rank_pois(
        candidates,
        intent,
        routes,
        {"outdoor_friendly": True},
        preference,
        build_preference_weights(preference),
    )

    assert ranked[0]["id"] == "walk"
    assert (
        ranked[0]["score_components"]["activity_match"]
        > ranked[1]["score_components"]["activity_match"]
    )


def test_healthy_dining_preference_promotes_light_restaurant():
    intent = parse_intent(QUERY)
    preference = UserPreference(
        activity_types=[],
        dining_preferences=["清淡健康"],
    )
    weights = build_preference_weights(preference)
    candidates = [
        {
            "id": "healthy",
            "name": "轻食厨房",
            "tags": ["healthy", "light_food"],
            "suitable_scenes": ["family"],
            "avg_price": 80,
            "rating": 4.5,
            "has_low_fat_meal": True,
            "has_kids_meal": True,
            "wait_time_min": 10,
        },
        {
            "id": "hotpot",
            "name": "热闹火锅",
            "tags": ["hotpot", "spicy"],
            "suitable_scenes": ["family"],
            "avg_price": 80,
            "rating": 4.5,
            "has_low_fat_meal": False,
            "has_kids_meal": True,
            "wait_time_min": 10,
        },
    ]
    routes = {
        item["id"]: RouteEstimate(distance_km=2, duration_min=10)
        for item in candidates
    }

    ranked = rank_restaurants(
        candidates,
        intent,
        routes,
        preference,
        weights,
    )

    assert ranked[0]["id"] == "healthy"
    assert (
        ranked[0]["score_components"]["diet_match"]
        > ranked[1]["score_components"]["diet_match"]
    )


def test_max_travel_minutes_changes_distance_score():
    intent = parse_intent("今天下午和朋友出去玩")
    candidate = {
        "id": "poi",
        "name": "远一点的展览",
        "type": "展览",
        "tags": ["indoor", "exhibition"],
        "age_range": [0, 99],
        "suitable_scenes": ["friends"],
        "rating": 4.5,
        "price": 60,
        "indoor": True,
        "wait_time_min": 5,
        "avg_duration_min": 90,
    }
    routes = {"poi": RouteEstimate(distance_km=8, duration_min=30)}
    strict = UserPreference(max_travel_minutes=15)
    flexible = UserPreference(max_travel_minutes=45)

    strict_result = rank_pois(
        [candidate],
        intent,
        routes,
        {"outdoor_friendly": True},
        strict,
        build_preference_weights(strict),
    )[0]
    flexible_result = rank_pois(
        [candidate],
        intent,
        routes,
        {"outdoor_friendly": True},
        flexible,
        build_preference_weights(flexible),
    )[0]

    assert (
        strict_result["score_components"]["distance"]
        < flexible_result["score_components"]["distance"]
    )


def test_plan_response_contains_preference_explanation():
    preference = UserPreference(
        activity_types=["亲子乐园"],
        max_travel_minutes=15,
        dining_preferences=["清淡健康"],
        prefer_indoor=True,
        prefer_low_wait=True,
    )
    asyncio.run(
        _request(
            "POST",
            "/api/preferences",
            preference.model_dump(mode="json"),
        )
    )
    response = asyncio.run(
        _request("POST", "/api/plan", {"query": QUERY})
    )

    assert response.status_code == 200
    explanation = response.json()["preference_explanation"]
    assert explanation
    assert any("15分钟" in item for item in explanation)
    assert any("清淡健康" in item for item in explanation)
    assert any("少排队" in item for item in explanation)
