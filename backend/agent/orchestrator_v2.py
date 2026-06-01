"""New Orchestrator (v2): wires the full pipeline with real provider abstraction.

Flow:
1. Parse intent → LLM provider (DeepSeek or mock)
2. Search POIs + Restaurants → POI provider (AMap or mock)
3. Geocode user's area → POI provider
4. Get weather → Weather provider (AMap or mock)
5. Get routes → Route provider (AMap or mock)
6. Rank candidates → RankingEngine (deterministic, no LLM)
7. Build plan → PlanGenerator
8. Generate explanation → ExplanationGenerator (LLM-based but data-grounded)
9. Return complete response with all metadata
"""

import logging
import traceback
from backend.config.settings import get_settings
from backend.providers.llm.factory import create_llm_provider
from backend.providers.amap.factory import (
    create_poi_provider,
    create_route_provider,
    create_weather_provider,
)
from backend.providers.amap.amap_provider import RESTAURANT_TYPES, ACTIVITY_TYPES
from backend.agent.ranking import RankingEngine
from backend.agent.plan_generator import build_plan
from backend.agent.explanation import ExplanationGenerator

logger = logging.getLogger(__name__)


async def run_agent_v2(user_id: str, query: str) -> dict:
    """Main entry point: run the complete Local Life Planning Agent pipeline (v2).

    Uses provider abstraction: real APIs in demo/development mode, mock in test mode.
    """
    settings = get_settings()
    provider_status = settings.provider_status.to_dict()

    trace = []
    trace.append({"phase": "init", "message": f"Agent v2 started, mode={settings.app_mode.value}"})

    # ── Step 1: Parse Intent ──────────────────────────────────────────
    trace.append({"phase": "intent_parsing", "message": "Parsing user intent..."})
    try:
        llm = create_llm_provider()
        parsed_intent = await llm.parse_intent(query)
        trace.append({
            "phase": "intent_parsing",
            "message": f"Parsed: scene={parsed_intent.get('scene')}, "
                       f"confidence={parsed_intent.get('confidence')}, "
                       f"missing_fields={parsed_intent.get('missing_fields')}",
        })
    except Exception as e:
        logger.error(f"Intent parsing failed: {e}")
        trace.append({"phase": "intent_parsing", "message": f"ERROR: {str(e)}"})
        return _error_response(query, "intent_parsing_failed", str(e), trace, provider_status)

    # ── Step 2: Search POIs ──────────────────────────────────────────
    trace.append({"phase": "candidate_retrieval", "message": "Searching POIs..."})
    poi_provider = create_poi_provider()

    city = parsed_intent.get("city") or "北京"
    area = parsed_intent.get("area") or ""
    search_location = f"{city}{area}" if area else city

    # Extract keywords from intent
    cuisine_keywords = parsed_intent.get("cuisine_preferences") or []
    scene = parsed_intent.get("scene")
    activity_keywords = _scene_to_activity_keywords(scene)

    try:
        # Geocode the area to get coordinates
        geocode_result = await poi_provider.geocode(search_location)

        # Search for activity venues
        poi_results = await poi_provider.search_pois(
            keyword=" ".join(activity_keywords) if activity_keywords else None,
            city=city,
            poi_type=ACTIVITY_TYPES,
        )

        # Search for restaurants
        rest_results = await poi_provider.search_pois(
            keyword=" ".join(cuisine_keywords) if cuisine_keywords else "餐厅",
            city=city,
            poi_type=RESTAURANT_TYPES,
        )

        trace.append({
            "phase": "candidate_retrieval",
            "message": f"Found {len(poi_results)} POIs, {len(rest_results)} restaurants",
        })
    except Exception as e:
        logger.error(f"POI search failed: {e}")
        trace.append({"phase": "candidate_retrieval", "message": f"ERROR: {str(e)}"})
        poi_results = []
        rest_results = []

    # ── Step 3: Get Weather ──────────────────────────────────────────
    trace.append({"phase": "weather", "message": "Fetching weather..."})
    weather_data = None
    try:
        weather_provider = create_weather_provider()
        weather_data = await weather_provider.get_weather(city)
        trace.append({
            "phase": "weather",
            "message": f"Weather: {weather_data.get('day_weather')} "
                       f"{weather_data.get('day_temp')}°C",
        })
    except Exception as e:
        logger.error(f"Weather fetch failed: {e}")
        trace.append({"phase": "weather", "message": f"ERROR: {str(e)}"})

    # ── Step 4: Get Routes ───────────────────────────────────────────
    trace.append({"phase": "routes", "message": "Computing routes..."})
    route_data = {}
    if geocode_result and geocode_result.get("longitude"):
        origin_coords = f"{geocode_result['longitude']},{geocode_result['latitude']}"
        route_provider = create_route_provider()

        for candidate in (poi_results + rest_results)[:10]:  # limit to top 10 for performance
            cid = candidate.get("id", "")
            lon = candidate.get("longitude")
            lat = candidate.get("latitude")
            if lon and lat:
                try:
                    route = await route_provider.plan_route(
                        origin=origin_coords,
                        destination=f"{lon},{lat}",
                        origin_coords=origin_coords,
                        dest_coords=f"{lon},{lat}",
                    )
                    route_data[cid] = route
                except Exception as e:
                    logger.warning(f"Route for {cid} failed: {e}")

        trace.append({
            "phase": "routes",
            "message": f"Computed routes for {len(route_data)} candidates",
        })

    # ── Step 5: Rank Candidates ─────────────────────────────────────
    trace.append({"phase": "ranking", "message": "Ranking candidates..."})
    ranking_engine = RankingEngine()

    poi_rankings = ranking_engine.rank(
        candidates=poi_results,
        parsed_intent=parsed_intent,
        route_data=route_data,
        weather_data=weather_data,
    )

    rest_rankings = ranking_engine.rank(
        candidates=rest_results,
        parsed_intent=parsed_intent,
        route_data=route_data,
        weather_data=weather_data,
    )

    trace.append({
        "phase": "ranking",
        "message": f"Ranked {len(poi_rankings)} POIs, {len(rest_rankings)} restaurants. "
                   f"Top POI: {poi_rankings[0].candidate_name if poi_rankings else 'none'} "
                   f"(score={poi_rankings[0].final_score:.2f}), "
                   f"Top restaurant: {rest_rankings[0].candidate_name if rest_rankings else 'none'} "
                   f"(score={rest_rankings[0].final_score:.2f})",
    })

    # ── Step 6: Build Plan ──────────────────────────────────────────
    trace.append({"phase": "plan_building", "message": "Building itinerary..."})
    plan = build_plan(
        parsed_intent=parsed_intent,
        poi_candidates=poi_results,
        restaurant_candidates=rest_results,
        poi_rankings=poi_rankings,
        restaurant_rankings=rest_rankings,
        route_data=route_data,
        weather_data=weather_data,
    )
    trace.append({
        "phase": "plan_building",
        "message": f"Plan built: {len(plan.get('itinerary', []))} segments",
    })

    # ── Step 7: Generate Explanation ────────────────────────────────
    trace.append({"phase": "explanation", "message": "Generating explanation..."})
    try:
        explainer = ExplanationGenerator(llm)
        explanation = await explainer.generate(
            user_input=query,
            parsed_intent=parsed_intent,
            plan=plan,
            provider_status=provider_status,
        )
        trace.append({"phase": "explanation", "message": "Explanation generated"})
    except Exception as e:
        logger.error(f"Explanation generation failed: {e}")
        explanation = f"抱歉，自动生成解释时出错。\n\n以下是系统基于真实数据生成的推荐方案。\n错误: {str(e)}"

    # ── Step 8: Assemble Response ───────────────────────────────────
    return {
        "status": "success",
        "scene": parsed_intent.get("scene"),
        "summary": explanation,
        "user_input": query,
        "parsed_intent": parsed_intent,
        "provider_status": provider_status,
        "candidates": {
            "pois": poi_results[:10],
            "restaurants": rest_results[:10],
        },
        "rankings": {
            "poi_rankings": plan.get("all_poi_rankings", []),
            "restaurant_rankings": plan.get("all_restaurant_rankings", []),
        },
        "itinerary": plan.get("itinerary", []),
        "top_picks": {
            "poi": plan.get("top_poi"),
            "restaurant": plan.get("top_restaurant"),
            "poi_score": plan.get("top_poi_score"),
            "restaurant_score": plan.get("top_restaurant_score"),
        },
        "weather": weather_data,
        "planning_trace": trace,
        "tool_calls": [],
        "completed_actions": [],
        "fallback_actions": [],
        "share_message": explanation,
        "plan_score": plan.get("top_poi_score", {}).get("final_score", 0) if plan.get("top_poi_score") else 0,
        "total_time_min": 0,
    }


def _scene_to_activity_keywords(scene: str | None) -> list[str]:
    """Map scene to activity search keywords."""
    mapping = {
        "family": ["亲子", "公园", "博物馆", "游乐场", "动物园"],
        "friends": ["密室逃脱", "桌游", "KTV", "剧本杀", "运动"],
        "couple": ["电影院", "公园", "咖啡", "逛街"],
        "business": ["茶馆", "咖啡"],
        "solo": ["展览", "博物馆", "书店"],
    }
    return mapping.get(scene or "", [])


def _error_response(query: str, error_phase: str, error_msg: str,
                    trace: list, provider_status: dict) -> dict:
    return {
        "status": "failed",
        "scene": None,
        "summary": f"Agent执行出错 ({error_phase}): {error_msg}",
        "user_input": query,
        "parsed_intent": {},
        "provider_status": provider_status,
        "candidates": {"pois": [], "restaurants": []},
        "rankings": {"poi_rankings": [], "restaurant_rankings": []},
        "itinerary": [],
        "top_picks": {},
        "weather": None,
        "planning_trace": trace,
        "tool_calls": [],
        "completed_actions": [],
        "fallback_actions": [],
        "share_message": f"Error: {error_msg}",
        "plan_score": 0,
        "total_time_min": 0,
    }
