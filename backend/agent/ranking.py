"""Ranking Engine: scores and ranks candidates based on real provider data.

Input: ParsedIntent + real POI/route/weather data from providers.
Output: Ranked candidates with full score breakdown.

LLM is NOT allowed to directly decide ranking. All scores are computed
deterministically from provider data and user constraints.
"""

import math
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ScoreBreakdown:
    """Detailed breakdown of how a candidate was scored."""
    candidate_name: str = ""
    candidate_id: str = ""

    # Individual scores (0.0 to 1.0)
    distance_score: float = 0.0
    route_time_score: float = 0.0
    budget_score: float = 0.0
    scene_score: float = 0.0
    weather_score: float = 0.0
    preference_score: float = 0.0

    # Penalties for unknown data
    unknown_penalty: float = 0.0
    unknown_fields: list[str] = field(default_factory=list)

    # Weights used
    weights: dict = field(default_factory=dict)

    # Final weighted score
    final_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "candidate_name": self.candidate_name,
            "candidate_id": self.candidate_id,
            "distance_score": round(self.distance_score, 4),
            "route_time_score": round(self.route_time_score, 4),
            "budget_score": round(self.budget_score, 4),
            "scene_score": round(self.scene_score, 4),
            "weather_score": round(self.weather_score, 4),
            "preference_score": round(self.preference_score, 4),
            "unknown_penalty": round(self.unknown_penalty, 4),
            "unknown_fields": self.unknown_fields,
            "weights": self.weights,
            "final_score": round(self.final_score, 4),
        }


class RankingEngine:
    """Ranks candidates using a weighted scoring model.

    All scores are computed from provider data — no LLM decision-making.
    Unknown fields (e.g., rating, price from AMap) get neutral scores
    with a small unknown_penalty rather than being guessed.
    """

    # Default weights
    DEFAULT_WEIGHTS = {
        "distance": 0.20,
        "route_time": 0.15,
        "budget": 0.15,
        "scene": 0.15,
        "weather": 0.10,
        "preference": 0.15,
        "unknown_penalty_max": 0.10,  # max penalty for all unknown fields
    }

    def __init__(self, weights: dict | None = None):
        self.weights = {**self.DEFAULT_WEIGHTS, **(weights or {})}

    def rank(
        self,
        candidates: list[dict],
        parsed_intent: dict,
        route_data: dict[str, dict] | None = None,
        weather_data: dict | None = None,
    ) -> list[ScoreBreakdown]:
        """Rank candidates and return sorted score breakdowns.

        Args:
            candidates: List of POI/restaurant dicts from provider.
            parsed_intent: ParsedIntent dict from LLM/mock parser.
            route_data: {candidate_id: route_info} dict from route provider.
            weather_data: Weather dict from weather provider.

        Returns:
            Sorted list of ScoreBreakdown (highest final_score first).
        """
        if not candidates:
            return []

        results = []
        for c in candidates:
            cid = c.get("id", c.get("poi_id", c.get("restaurant_id", "")))
            route = (route_data or {}).get(cid, {})
            breakdown = self._score_one(c, parsed_intent, route, weather_data)
            results.append(breakdown)

        results.sort(key=lambda r: r.final_score, reverse=True)
        return results

    def _score_one(
        self,
        candidate: dict,
        intent: dict,
        route: dict | None,
        weather: dict | None,
    ) -> ScoreBreakdown:
        cid = candidate.get("id", candidate.get("poi_id", ""))
        name = candidate.get("name", "unknown")
        b = ScoreBreakdown(candidate_name=name, candidate_id=cid, weights=self.weights)

        # Collect unknown fields
        unknown = []
        for f in ["rating", "avg_price", "open_time", "close_time", "indoor",
                   "suitable_scenes", "tags", "age_range"]:
            val = candidate.get(f)
            if val is None or val == "unknown":
                unknown.append(f)
        b.unknown_fields = unknown

        # 1. Distance score
        b.distance_score = self._distance_score(candidate, intent)

        # 2. Route time score
        b.route_time_score = self._route_time_score(route)

        # 3. Budget score
        b.budget_score = self._budget_score(candidate, intent)

        # 4. Scene score
        b.scene_score = self._scene_score(candidate, intent)

        # 5. Weather score
        b.weather_score = self._weather_score(candidate, weather)

        # 6. Preference score (cuisine, indoor/outdoor, etc.)
        b.preference_score = self._preference_score(candidate, intent)

        # Unknown penalty: proportional to number of unknown fields
        unknown_ratio = len(unknown) / max(len(self._all_known_fields()), 1)
        b.unknown_penalty = unknown_ratio * self.weights["unknown_penalty_max"]

        # Compute final weighted score
        b.final_score = (
            self.weights["distance"] * b.distance_score
            + self.weights["route_time"] * b.route_time_score
            + self.weights["budget"] * b.budget_score
            + self.weights["scene"] * b.scene_score
            + self.weights["weather"] * b.weather_score
            + self.weights["preference"] * b.preference_score
            - b.unknown_penalty
        )
        b.final_score = max(0.0, min(1.0, b.final_score))

        return b

    def _distance_score(self, candidate: dict, intent: dict) -> float:
        dist_m = candidate.get("distance_m")
        if dist_m is None or dist_m == "unknown":
            return 0.5  # neutral — no distance info
        dist_km = dist_m / 1000.0
        # Prefer closer: score = 1.0 at 0km, dropping to 0 at 15km+
        if dist_km <= 1:
            return 1.0
        if dist_km <= 5:
            return 1.0 - (dist_km - 1) * 0.1
        if dist_km <= 15:
            return 0.6 - (dist_km - 5) * 0.06
        return 0.0

    def _route_time_score(self, route: dict | None) -> float:
        if not route:
            return 0.5  # neutral — no route data
        duration_sec = route.get("duration_sec")
        if duration_sec is None or duration_sec == "unknown":
            return 0.5
        mins = duration_sec / 60.0
        if mins <= 15:
            return 1.0
        if mins <= 30:
            return 1.0 - (mins - 15) * 0.02
        if mins <= 60:
            return 0.7 - (mins - 30) * 0.015
        return max(0.0, 0.25 - (mins - 60) * 0.005)

    def _budget_score(self, candidate: dict, intent: dict) -> float:
        budget = intent.get("budget_per_person")
        if budget is None:
            return 0.5  # neutral — no budget constraint
        price = candidate.get("avg_price")
        if price is None or price == "unknown":
            return 0.5  # neutral — no price info
        try:
            price = float(price)
        except (ValueError, TypeError):
            return 0.5
        # Score how well the price matches the budget
        ratio = price / budget if budget > 0 else 1.0
        if 0.5 <= ratio <= 1.0:
            return 1.0  # under budget is good
        if 1.0 < ratio <= 1.5:
            return 1.0 - (ratio - 1.0) * 1.0  # slightly over
        if 0.25 <= ratio < 0.5:
            return ratio / 0.5  # too cheap
        return max(0.0, 0.5 - (ratio - 1.5) * 0.5)

    def _scene_score(self, candidate: dict, intent: dict) -> float:
        scene = intent.get("scene")
        if scene is None:
            return 0.5  # neutral — no scene preference
        suitable = candidate.get("suitable_scenes", [])
        if suitable == "unknown" or suitable is None:
            return 0.5
        if isinstance(suitable, list):
            return 1.0 if scene in suitable else 0.3
        return 0.5

    def _weather_score(self, candidate: dict, weather: dict | None) -> float:
        if not weather:
            return 0.5  # neutral
        weather_text = weather.get("day_weather", "").lower()
        if weather_text in ("unknown", ""):
            return 0.5
        # Penalize outdoor activities in bad weather
        indoor = candidate.get("indoor")
        is_indoor = indoor is True or indoor == "true"
        bad_weather = any(w in weather_text for w in ["雨", "雪", "霾", "沙尘", "大风"])
        if bad_weather and not is_indoor:
            return 0.2
        if bad_weather and is_indoor:
            return 1.0  # indoor is good in bad weather
        return 1.0  # good weather

    def _preference_score(self, candidate: dict, intent: dict) -> float:
        score = 0.5  # baseline neutral

        # Cuisine preference match
        cuisines = intent.get("cuisine_preferences") or []
        if cuisines:
            tags = candidate.get("tags", [])
            name = candidate.get("name", "")
            ctype = candidate.get("type", "")
            search_text = f"{name} {ctype} {' '.join(tags if isinstance(tags, list) else [])}"
            matches = sum(1 for c in cuisines if c in search_text)
            if matches > 0:
                score += 0.3 * (matches / len(cuisines))

        # Indoor preference match
        indoor_pref = intent.get("indoor_preference")
        if indoor_pref is not None:
            indoor = candidate.get("indoor")
            if indoor is not None and indoor != "unknown":
                if bool(indoor_pref) == bool(indoor):
                    score += 0.15
                else:
                    score -= 0.1

        # Transport preference — no direct impact on candidate scoring,
        # but distance sensitivity could be adjusted later.

        return max(0.0, min(1.0, score))

    @staticmethod
    def _all_known_fields() -> list[str]:
        return ["rating", "avg_price", "open_time", "close_time", "indoor",
                "suitable_scenes", "tags", "age_range"]
