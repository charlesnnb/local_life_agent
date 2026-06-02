"""Orchestrator V2: complete Agent pipeline with real providers + execution.

Flow:
1. Parse intent → LLM provider (DeepSeek or mock)
2. Merge user profile → enrich constraints from data/*.json
3. Search POIs + Restaurants → POI provider (AMap or mock)
4. Get weather → Weather provider (AMap or mock)
5. Get routes → Route provider (AMap or mock)
6. Rank candidates → RankingEngine (deterministic)
7. Build plan → PlanGenerator
8. Feasibility check → FeasibilityV2 (real data + mock fallback)
9. Build action plan → ActionPlannerV2
10. Generate share message → ShareMessageV2
11. Execute actions → ExecutorV2 (mock tools)
12. Generate explanation → ExplanationGenerator (LLM)
13. Return complete response with tool_calls, completed/fallback actions
"""

import logging
import traceback
import asyncio
from backend.config.settings import get_settings
from backend.data_loader import load_all, get_user, get_family_profile, get_friend_group
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
from backend.agent.feasibility_v2 import check_plan_feasibility_v2, _poi_needs_ticket
from backend.agent.action_planner_v2 import build_action_plan_v2
from backend.agent.executor_v2 import execute_actions_v2
from backend.agent.share_message_v2 import generate_share_message_v2
from backend.agent.location_resolver import resolve_origin_location
from backend.agent.orchestrator_shared import (
    infer_scene, get_activity_keywords, get_cuisine_keywords,
    merge_profile, mock_poi_fallback, mock_restaurant_fallback, build_fallback_plan,
    filter_pois_by_distance,
)

logger = logging.getLogger(__name__)


async def run_agent_v2(
    user_id: str,
    query: str,
    location: dict | None = None,
    demo_scenario: str = "normal",
) -> dict:
    """Main entry point: run the complete Local Life Planning Agent pipeline (v2).

    Full pipeline: intent → location → profile → search → weather → routes → rank →
    plan → feasibility → action_plan → share_message → execute → explain → respond.

    Args:
        user_id: User identifier.
        query: Natural language query.
        location: Optional location dict from frontend (browser geolocation or manual).
        demo_scenario: Demo scenario override (normal, restaurant_full, rainy_weather, etc.).
    """
    settings = get_settings()
    provider_status = settings.provider_status.to_dict()
    demo_scenario = demo_scenario or "normal"

    # Ensure mock data is loaded (for fallback tools)
    load_all()

    trace = []
    trace.append({"phase": "init", "message": f"Agent started, mode={settings.app_mode.value}, scenario={demo_scenario}"})

    # ── Step 1: Parse Intent ──────────────────────────────────────────
    trace.append({"phase": "intent_parsing", "message": "Parsing user intent..."})
    try:
        llm = create_llm_provider()
        parsed_intent = await asyncio.wait_for(llm.parse_intent(query), timeout=15.0)
        trace.append({
            "phase": "intent_parsing",
            "message": f"Parsed: scene={parsed_intent.get('scene')}, "
                       f"confidence={parsed_intent.get('confidence')}, "
                       f"missing_fields={parsed_intent.get('missing_fields')}",
        })
    except (asyncio.TimeoutError, Exception) as e:
        logger.warning(f"Intent parsing failed, using rule fallback: {e}")
        trace.append({"phase": "intent_parsing", "message": f"API超时/失败，使用规则兜底: {str(e)[:60]}"})
        from backend.providers.llm.mock_provider import MockLLMProvider
        parsed_intent = await MockLLMProvider().parse_intent(query)

    scene = infer_scene(query, parsed_intent)
    if parsed_intent.get("scene") is None:
        trace.append({"phase": "intent_parsing", "message": f"LLM未返回场景，根据关键词推断: {scene}"})

    # ── Step 1b: Resolve Origin Location ──────────────────────────────
    trace.append({"phase": "location_resolve", "message": "Resolving origin location..."})
    origin_location = resolve_origin_location(user_id, location, parsed_intent)
    for msg in origin_location.get("trace", []):
        trace.append({"phase": "location_resolve", "message": msg})

    # ── Step 2: Merge User Profile ────────────────────────────────────
    trace.append({"phase": "profile_merge", "message": "Merging user profile..."})
    constraints = merge_profile(user_id, parsed_intent, scene)
    constraints["origin_location"] = origin_location
    profile_detail = f"已结合用户画像: scene={scene}, party_size={constraints.get('party_size')}"
    if constraints.get("child_age"):
        profile_detail += f", child_age={constraints['child_age']}"
    trace.append({"phase": "profile_merge", "message": profile_detail})

    # ── Step 3: Search POIs & Restaurants ─────────────────────────────
    trace.append({"phase": "candidate_retrieval", "message": "Searching POIs..."})
    poi_provider = create_poi_provider()

    city = parsed_intent.get("city") or ""
    # If no city from parser, try origin_location (for query_extracted without geocode)
    if not city and origin_location:
        city = origin_location.get("address", "").rstrip("市区县")
    if not city:
        city = "北京"
    area = parsed_intent.get("area") or ""
    search_location = f"{city}{area}" if area else city

    cuisine_keywords = get_cuisine_keywords(parsed_intent, query)
    activity_keywords = get_activity_keywords(scene, query)

    geocode_result = None
    poi_results = []
    rest_results = []
    # AMap free tier QPS is ~5 for most APIs, ~1-2 for driving direction.
    # Space out calls to stay under limits.
    _amap_delay = 0.5  # seconds between AMap API calls
    try:
        geocode_result = await asyncio.wait_for(poi_provider.geocode(search_location), timeout=15.0)
        await asyncio.sleep(_amap_delay)
    except Exception:
        geocode_result = None
    try:
        poi_kw = "|".join(activity_keywords) if activity_keywords else None
        rest_kw = "|".join(cuisine_keywords) if cuisine_keywords else "餐厅"
        trace.append({
            "phase": "candidate_retrieval",
            "message": f"搜索关键词: POI={poi_kw or '(类型搜索)'}, 餐厅={rest_kw}, 城市={city}",
        })
        poi_results = await asyncio.wait_for(poi_provider.search_pois(
            keyword=poi_kw, city=city, poi_type=ACTIVITY_TYPES), timeout=15.0)
        await asyncio.sleep(_amap_delay)
        rest_results = await asyncio.wait_for(poi_provider.search_pois(
            keyword=rest_kw, city=city, poi_type=RESTAURANT_TYPES), timeout=15.0)
        await asyncio.sleep(_amap_delay)
        # Show found POI names in trace for debugging
        poi_names = [p.get("name", "?") for p in poi_results[:5]]
        trace.append({
            "phase": "candidate_retrieval",
            "message": f"找到 {len(poi_results)} 个POI: {', '.join(poi_names)}",
        })
        # Try without keywords if too few results
        if len(poi_results) < 3 and poi_kw:
            trace.append({
                "phase": "candidate_retrieval",
                "message": f"关键词搜索仅{len(poi_results)}个结果，尝试纯类型搜索(无关键词)...",
            })
            await asyncio.sleep(_amap_delay)
            poi_results = await asyncio.wait_for(poi_provider.search_pois(
                keyword=None, city=city, poi_type=ACTIVITY_TYPES), timeout=15.0)
            poi_names2 = [p.get("name", "?") for p in poi_results[:5]]
            trace.append({
                "phase": "candidate_retrieval",
                "message": f"纯类型搜索: {len(poi_results)} 个POI: {', '.join(poi_names2)}",
            })
        # Filter out results from wrong cities (AMap city filter is not strict)
        if origin_location:
            poi_results = filter_pois_by_distance(poi_results, origin_location, max_km=80)
            rest_results = filter_pois_by_distance(rest_results, origin_location, max_km=80)
            trace.append({
                "phase": "candidate_retrieval",
                "message": f"距离过滤后: {len(poi_results)} 个POI, {len(rest_results)} 个餐厅",
            })
    except (asyncio.TimeoutError, Exception) as e:
        logger.warning(f"POI search failed: {e}")
        trace.append({"phase": "candidate_retrieval", "message": f"API超时: {str(e)[:60]}"})

    # Fallback: if no POI results, broaden search
    if not poi_results:
        trace.append({"phase": "candidate_retrieval", "message": "POI search returned 0 results, broadening..."})
        try:
            await asyncio.sleep(_amap_delay)
            poi_results = await asyncio.wait_for(poi_provider.search_pois(
                keyword="景点|公园|博物馆|商场|景区|旅游",
                city=city, poi_type=ACTIVITY_TYPES), timeout=15.0)
            await asyncio.sleep(_amap_delay)
            trace.append({"phase": "candidate_retrieval", "message": f"Broadened POI search: {len(poi_results)} results"})
            if origin_location:
                poi_results = filter_pois_by_distance(poi_results, origin_location, max_km=80)
        except Exception:
            pass

    if not poi_results:
        trace.append({"phase": "candidate_retrieval", "message": "Using mock POI fallback"})
        poi_results = mock_poi_fallback(city, scene, query)

    if not rest_results:
        trace.append({"phase": "candidate_retrieval", "message": "Using mock restaurant fallback"})
        rest_results = mock_restaurant_fallback(city, scene)

    # ── Step 4: Get Weather ───────────────────────────────────────────
    trace.append({"phase": "weather", "message": "Fetching weather..."})
    weather_data = None
    try:
        await asyncio.sleep(_amap_delay)
        weather_provider = create_weather_provider()
        weather_data = await asyncio.wait_for(weather_provider.get_weather(city), timeout=10.0)
        trace.append({
            "phase": "weather",
            "message": f"Weather: {weather_data.get('day_weather')} {weather_data.get('day_temp')}°C",
        })
    except (asyncio.TimeoutError, Exception) as e:
        logger.warning(f"Weather fetch failed: {e}")
        trace.append({"phase": "weather", "message": f"天气查询失败: {str(e)[:60]}"})

    # ── Step 5: Get Routes ────────────────────────────────────────────
    trace.append({"phase": "routes", "message": "Computing routes..."})
    route_data = {}
    if geocode_result and geocode_result.get("longitude"):
        origin_coords = f"{geocode_result['longitude']},{geocode_result['latitude']}"
        route_provider = create_route_provider()

        for idx, candidate in enumerate((poi_results + rest_results)[:5]):
            cid = candidate.get("id", "")
            lon = candidate.get("longitude")
            lat = candidate.get("latitude")
            if lon and lat:
                try:
                    route = await asyncio.wait_for(route_provider.plan_route(
                        origin=origin_coords,
                        destination=f"{lon},{lat}",
                        origin_coords=origin_coords,
                        dest_coords=f"{lon},{lat}",
                    ), timeout=10.0)
                    route_data[cid] = route
                    if idx > 0:
                        await asyncio.sleep(0.5)  # avoid QPS limit
                except Exception as e:
                    logger.warning(f"Route for {cid} failed: {e}")

        trace.append({
            "phase": "routes",
            "message": f"Computed routes for {len(route_data)} candidates",
        })

    # ── Step 6: Rank Candidates ──────────────────────────────────────
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
                   f"(score={poi_rankings[0].final_score if poi_rankings else 0:.2f}), "
                   f"Top restaurant: {rest_rankings[0].candidate_name if rest_rankings else 'none'} "
                   f"(score={rest_rankings[0].final_score if rest_rankings else 0:.2f})",
    })

    # ── Step 7: Build Plan ────────────────────────────────────────────
    trace.append({"phase": "plan_building", "message": "Building itinerary..."})
    if not poi_results and not rest_results:
        trace.append({"phase": "plan_building", "message": "No candidates, generating fallback plan"})
        plan = build_fallback_plan(parsed_intent, constraints, weather_data)
    else:
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

    top_poi = plan.get("top_poi")
    top_restaurant = plan.get("top_restaurant")

    # ── Demo Scenario Overrides ──────────────────────────────────────
    top_poi, top_restaurant, weather_data = _apply_demo_scenario_overrides(
        demo_scenario, top_poi, top_restaurant, weather_data,
        poi_results, rest_results, plan, trace,
    )

    # ── Step 8: Feasibility Check ─────────────────────────────────────
    trace.append({"phase": "feasibility_check", "message": "Checking feasibility..."})
    feasibility_result = {"feasible": True, "reasons": [], "warnings": [], "fallback_used": []}

    if top_poi or top_restaurant:
        try:
            feasibility_result = check_plan_feasibility_v2(
                plan_candidate={"poi": top_poi, "restaurant": top_restaurant},
                constraints=constraints,
                provider_context={
                    "route_data": route_data,
                    "weather_data": weather_data,
                    "geocode_result": geocode_result,
                    "demo_scenario": demo_scenario,
                },
            )
            for reason in feasibility_result.get("reasons", []):
                trace.append({"phase": "feasibility_check", "message": f"FAIL: {reason}"})
            for warning in feasibility_result.get("warnings", []):
                trace.append({"phase": "feasibility_check", "message": f"WARN: {warning}"})
            for fb in feasibility_result.get("fallback_used", []):
                trace.append({"phase": "feasibility_check", "message": f"FALLBACK: {fb}"})
            if feasibility_result["feasible"]:
                trace.append({"phase": "feasibility_check", "message": "Plan is feasible"})
        except Exception as e:
            logger.error(f"Feasibility check failed: {e}")
            trace.append({"phase": "feasibility_check", "message": f"ERROR: {str(e)}"})

    # If plan is infeasible, try next-ranked candidates (up to 3 attempts)
    if not feasibility_result["feasible"]:
        trace.append({"phase": "feasibility_fallback", "message": "Primary plan infeasible, trying alternatives..."})
        max_attempts = max(len(poi_rankings), len(rest_rankings))
        if max_attempts == 0:
            max_attempts = 1  # at least try once even if rankings are empty
        for attempt in range(min(3, max_attempts)):
            alt_poi_idx = min(attempt + 1, max(len(poi_rankings) - 1, 0)) if len(poi_rankings) > 1 else 0
            alt_rest_idx = min(attempt + 1, max(len(rest_rankings) - 1, 0)) if len(rest_rankings) > 1 else 0

            alt_poi = poi_results[alt_poi_idx] if poi_results and alt_poi_idx < len(poi_results) else None
            alt_rest = rest_results[alt_rest_idx] if rest_results and alt_rest_idx < len(rest_results) else None

            if alt_poi == top_poi and alt_rest == top_restaurant:
                continue

            alt_feasibility = check_plan_feasibility_v2(
                plan_candidate={"poi": alt_poi, "restaurant": alt_rest},
                constraints=constraints,
                provider_context={
                    "route_data": route_data,
                    "weather_data": weather_data,
                    "geocode_result": geocode_result,
                },
            )
            if alt_feasibility["feasible"]:
                trace.append({
                    "phase": "feasibility_fallback",
                    "message": f"Switched to alt plan: POI={alt_poi.get('name') if alt_poi else 'none'}, "
                               f"Restaurant={alt_rest.get('name') if alt_rest else 'none'}",
                })
                # Rebuild plan with alt candidates
                top_poi = alt_poi
                top_restaurant = alt_rest
                plan["top_poi"] = alt_poi
                plan["top_restaurant"] = alt_rest
                plan["top_poi_score"] = poi_rankings[alt_poi_idx].to_dict() if alt_poi_idx < len(poi_rankings) else None
                plan["top_restaurant_score"] = rest_rankings[alt_rest_idx].to_dict() if alt_rest_idx < len(rest_rankings) else None
                feasibility_result = alt_feasibility
                break
        if not feasibility_result["feasible"]:
            trace.append({"phase": "feasibility_fallback", "message": "All alternatives infeasible, proceeding with best effort"})

    # ── Step 9: Build Action Plan ─────────────────────────────────────
    trace.append({"phase": "action_planning", "message": "Building action plan..."})
    needs_ticket = _poi_needs_ticket(
        top_poi.get("type", "") if top_poi else "",
        top_poi.get("name", "") if top_poi else "",
    )

    action_plan = build_action_plan_v2(
        selected_poi=top_poi,
        selected_restaurant=top_restaurant,
        constraints=constraints,
        needs_ticket=needs_ticket,
    )
    trace.append({
        "phase": "action_planning",
        "message": f"Generated {len(action_plan)} actions "
                   f"({sum(1 for a in action_plan if a['required'])} required, "
                   f"{sum(1 for a in action_plan if not a['required'])} optional)",
    })

    # ── Step 10: Generate Share Message ───────────────────────────────
    trace.append({"phase": "share_message", "message": "Generating share message..."})
    try:
        share_message = generate_share_message_v2(
            scene=scene,
            selected_poi=top_poi,
            selected_restaurant=top_restaurant,
            completed_actions=[],  # Will be updated after execution
            constraints=constraints,
        )
        trace.append({"phase": "share_message", "message": "Share message generated"})
    except Exception as e:
        logger.error(f"Share message generation failed: {e}")
        share_message = f"今天的计划已安排好，{scene}出行方案已确认。"

    # ── Step 11: Execute Actions ──────────────────────────────────────
    trace.append({"phase": "execution", "message": "Executing tool calls..."})
    try:
        exec_result = execute_actions_v2(
            user_id=user_id,
            action_plan=action_plan,
            constraints=constraints,
            share_message=share_message,
            selected_poi=top_poi,
            selected_restaurant=top_restaurant,
        )
        tool_calls = exec_result.get("tool_calls", [])
        completed_actions = exec_result.get("completed_actions", [])
        fallback_actions = exec_result.get("fallback_actions", [])

        for tc in tool_calls:
            status = "OK" if tc.get("success") else "FAIL"
            trace.append({
                "phase": "execution",
                "message": f"Tool {tc.get('tool_name')}: {status} - {tc.get('message', '')}",
            })
        # Demo: restaurant_full — inject fallback if none occurred naturally
        if demo_scenario == "restaurant_full" and not fallback_actions:
            fallback_actions.append({
                "type": "restaurant_reservation",
                "reason": "17:00 餐厅无位（Demo模拟）",
                "action": "已自动切换时间至 17:30",
                "result": "17:30 预约成功",
            })
            trace.append({
                "phase": "execution",
                "message": "Demo: 餐厅无位fallback — 17:00→17:30 预约成功",
            })

        # Demo: optional_service_fail — override extra service result
        if demo_scenario == "optional_service_fail":
            tool_calls = _filter_optional_service_tool_calls(tool_calls)
            completed_actions = [ca for ca in completed_actions if ca.get("type") != "extra_service_order"]
            already_has = any("extra_service_skipped" in str(fb.get("type", "")) for fb in fallback_actions)
            if not already_has:
                fallback_actions.append({
                    "type": "extra_service_skipped",
                    "reason": "蛋糕/咖啡服务暂不可用（Demo模拟）",
                    "action": "已跳过额外服务",
                    "result": "不影响主行程",
                })
            trace.append({
                "phase": "execution",
                "message": "Demo: 可选服务(蛋糕/咖啡)下单失败，已跳过",
            })

        for fb in fallback_actions:
            trace.append({
                "phase": "execution",
                "message": f"Fallback: {fb.get('reason', '')} → {fb.get('action', '')}",
            })
    except Exception as e:
        logger.error(f"Execution failed: {e}")
        trace.append({"phase": "execution", "message": f"ERROR: {str(e)}"})
        tool_calls = []
        completed_actions = []
        fallback_actions = [{"type": "execution_error", "reason": str(e), "action": "execution failed", "result": "partial"}]

    # Regenerate share message with actual completed actions
    try:
        share_message = generate_share_message_v2(
            scene=scene,
            selected_poi=top_poi,
            selected_restaurant=top_restaurant,
            completed_actions=completed_actions,
            constraints=constraints,
        )
    except Exception:
        pass  # Keep the pre-execution share_message

    # ── Step 12: Generate Explanation ─────────────────────────────────
    trace.append({"phase": "explanation", "message": "Generating explanation..."})
    try:
        explainer = ExplanationGenerator(llm)
        explanation = await asyncio.wait_for(explainer.generate(
            user_input=query,
            parsed_intent=parsed_intent,
            plan=plan,
            provider_status=provider_status,
        ), timeout=15.0)
        trace.append({"phase": "explanation", "message": "Explanation generated"})
    except Exception as e:
        logger.error(f"Explanation generation failed: {e}")
        explanation = f"抱歉，自动生成解释时出错。\n\n以下是系统基于真实数据生成的推荐方案。\n错误: {str(e)}"

    # ── Step 13: Assemble Response ────────────────────────────────────
    status = "success"
    if fallback_actions:
        has_required_fallback = any(
            "reservation_fallback" in str(fb) or "ticket_order_fallback" in str(fb)
            for fb in fallback_actions
        )
        if has_required_fallback:
            status = "partial"

    # Compute total time from itinerary
    total_time_min = 0
    for item in plan.get("itinerary", []):
        if item.get("type") in ("travel", "return"):
            total_time_min += 20  # estimate
        elif item.get("type") == "activity":
            total_time_min += 90  # estimate
        elif item.get("type") == "meal":
            total_time_min += 60  # estimate

    return {
        "status": status,
        "version": "v2",
        "scene": scene,
        "summary": explanation,
        "user_input": query,
        "constraints": constraints,
        "origin_location": origin_location,
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
            "poi": top_poi,
            "restaurant": top_restaurant,
            "poi_score": plan.get("top_poi_score"),
            "restaurant_score": plan.get("top_restaurant_score"),
        },
        "weather": weather_data,
        "planning_trace": trace,
        "tool_calls": tool_calls,
        "completed_actions": completed_actions,
        "fallback_actions": fallback_actions,
        "share_message": share_message,
        "explanation": explanation,
        "plan_score": plan.get("top_poi_score", {}).get("final_score", 0) if plan.get("top_poi_score") else 0,
        "total_time_min": total_time_min,
        "debug": {
            "feasibility": feasibility_result,
            "action_plan": action_plan,
            "needs_ticket": needs_ticket,
        },
    }


def _error_response(query: str, error_phase: str, error_msg: str,
                    trace: list, provider_status: dict) -> dict:
    """Build error response with all required fields (no missing keys)."""
    return {
        "status": "failed",
        "version": "v2",
        "scene": None,
        "summary": f"Agent执行出错 ({error_phase}): {error_msg}",
        "user_input": query,
        "constraints": {},
        "origin_location": {},
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
        "explanation": f"Agent执行出错 ({error_phase}): {error_msg}",
        "plan_score": 0,
        "total_time_min": 0,
        "debug": {"error_phase": error_phase, "error": error_msg},
    }


def _apply_demo_scenario_overrides(
    demo_scenario: str,
    top_poi: dict | None,
    top_restaurant: dict | None,
    weather_data: dict | None,
    poi_results: list,
    rest_results: list,
    plan: dict,
    trace: list,
) -> tuple:
    """Apply demo scenario overrides to selected candidates and data."""
    if demo_scenario == "normal":
        return top_poi, top_restaurant, weather_data

    # rainy_weather: force weather to rain
    if demo_scenario == "rainy_weather":
        if weather_data is None:
            weather_data = {}
        weather_data = dict(weather_data)
        weather_data["day_weather"] = "中雨"
        weather_data["night_weather"] = "小雨"
        if "day_temp" not in weather_data:
            weather_data["day_temp"] = "22"
        trace.append({
            "phase": "demo_scenario",
            "message": "Demo: 强制雨天，优先室内活动",
        })

    # route_too_far: force switch to second POI
    if demo_scenario == "route_too_far" and len(poi_results) > 1:
        old_name = top_poi.get("name", "") if top_poi else ""
        top_poi = poi_results[1]
        plan["top_poi"] = top_poi
        trace.append({
            "phase": "demo_scenario",
            "message": f"Demo: {old_name} 距离过远，自动切换到 {top_poi.get('name', '')}",
        })

    # ticket_sold_out: force switch to second POI
    if demo_scenario == "ticket_sold_out" and len(poi_results) > 1:
        old_name = top_poi.get("name", "") if top_poi else ""
        top_poi = poi_results[1]
        plan["top_poi"] = top_poi
        trace.append({
            "phase": "demo_scenario",
            "message": f"Demo: {old_name} 门票售罄，自动切换到 {top_poi.get('name', '')}",
        })

    return top_poi, top_restaurant, weather_data


def _filter_optional_service_tool_calls(tool_calls: list) -> list:
    """Mark extra service tool calls as failed for demo scenarios."""
    result = []
    for tc in tool_calls:
        if tc.get("tool_name") == "create_flower_or_cake_order":
            tc = dict(tc)
            tc["success"] = False
            tc["message"] = "蛋糕/咖啡服务暂不可用（Demo模拟）"
        result.append(tc)
    return result
