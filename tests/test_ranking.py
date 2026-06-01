"""Tests for RankingEngine."""

import pytest
from backend.agent.ranking import RankingEngine, ScoreBreakdown


def make_candidate(name, **overrides):
    """Helper to create a candidate dict with defaults."""
    base = {
        "id": name,
        "name": name,
        "type": "餐饮;中餐",
        "address": "测试地址",
        "longitude": 116.4,
        "latitude": 39.9,
        "distance_m": 2000,
        "rating": "unknown",
        "avg_price": "unknown",
        "open_time": "unknown",
        "close_time": "unknown",
        "indoor": "unknown",
        "suitable_scenes": "unknown",
        "tags": "unknown",
        "age_range": "unknown",
        "source": "test",
    }
    base.update(overrides)
    return base


class TestRankingEngine:

    def test_empty_candidates(self):
        engine = RankingEngine()
        results = engine.rank([], {})
        assert results == []

    def test_single_candidate_returns_score(self):
        engine = RankingEngine()
        c = make_candidate("测试餐厅")
        results = engine.rank([c], {})
        assert len(results) == 1
        assert isinstance(results[0], ScoreBreakdown)
        assert results[0].candidate_name == "测试餐厅"
        assert 0.0 <= results[0].final_score <= 1.0

    def test_closer_candidates_score_higher(self):
        engine = RankingEngine()
        near = make_candidate("近餐厅", distance_m=500)
        far = make_candidate("远餐厅", distance_m=10000)
        results = engine.rank([near, far], {})
        assert results[0].candidate_name == "近餐厅"
        assert results[0].distance_score > results[1].distance_score

    def test_budget_match_scores_higher(self):
        engine = RankingEngine()
        intent = {"budget_per_person": 100}
        good = make_candidate("预算匹配", avg_price=80)
        bad = make_candidate("预算超标", avg_price=300)
        results = engine.rank([good, bad], intent)
        assert results[0].candidate_name == "预算匹配"
        assert results[0].budget_score > results[1].budget_score

    def test_scene_match_scores_higher(self):
        engine = RankingEngine()
        intent = {"scene": "family"}
        family_poi = make_candidate("家庭地点", suitable_scenes=["family", "friends"])
        business_poi = make_candidate("商务地点", suitable_scenes=["business"])
        results = engine.rank([family_poi, business_poi], intent)
        assert results[0].candidate_name == "家庭地点"
        assert results[0].scene_score > results[1].scene_score

    def test_bad_weather_penalizes_outdoor(self):
        engine = RankingEngine()
        weather = {"day_weather": "大雨"}
        outdoor = make_candidate("户外活动", indoor=False)
        indoor_ = make_candidate("室内活动", indoor=True)
        results = engine.rank([outdoor, indoor_], {}, weather_data=weather)
        assert results[0].candidate_name == "室内活动"
        assert results[0].weather_score > results[1].weather_score

    def test_unknown_fields_penalty(self):
        engine = RankingEngine()
        many_unknown = make_candidate("很多未知", rating="unknown", avg_price="unknown",
                                       open_time="unknown", close_time="unknown",
                                       indoor="unknown", suitable_scenes="unknown",
                                       tags="unknown", age_range="unknown")
        # Give the candidate some known scores so the comparison is fair
        less_unknown = make_candidate("较少未知", rating=4.5, avg_price=100,
                                        open_time="10:00", close_time="22:00",
                                        indoor=True, suitable_scenes=["family"],
                                        tags=["kids"], age_range=[3, 12])
        results = engine.rank([many_unknown, less_unknown], {})
        # less_unknown should rank higher because it has fewer unknown fields
        # and its scores can be more accurately computed
        assert results[0].candidate_name == "较少未知"

    def test_no_budget_preference_gives_neutral(self):
        engine = RankingEngine()
        c = make_candidate("测试")
        results = engine.rank([c], {})
        # With no budget constraint, budget score should be neutral (~0.5)
        assert 0.4 <= results[0].budget_score <= 0.6

    def test_score_breakdown_to_dict(self):
        b = ScoreBreakdown(
            candidate_name="测试",
            candidate_id="t1",
            distance_score=0.9,
            route_time_score=0.8,
            budget_score=0.7,
            scene_score=0.6,
            weather_score=0.5,
            preference_score=0.4,
            unknown_penalty=0.1,
            unknown_fields=["avg_price"],
            weights={"distance": 0.2},
            final_score=0.65,
        )
        d = b.to_dict()
        assert d["candidate_name"] == "测试"
        assert d["distance_score"] == 0.9
        assert d["unknown_fields"] == ["avg_price"]
        assert d["final_score"] == 0.65

    def test_route_time_affects_score(self):
        engine = RankingEngine()
        intent = {}
        route_data = {
            "近餐厅": {"duration_sec": 600},   # 10 min
            "远餐厅": {"duration_sec": 3600},   # 60 min
        }
        near = make_candidate("近餐厅")
        far = make_candidate("远餐厅")
        results = engine.rank([near, far], intent, route_data=route_data)
        assert results[0].candidate_name == "近餐厅"
        assert results[0].route_time_score > results[1].route_time_score
