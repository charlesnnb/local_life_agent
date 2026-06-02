"""Legacy V1 mock pipeline — preserved for reference and test reuse.

The production demo uses main_agent.py / the current LocalLifeAgent pipeline
(orchestrator_v2.py + stream_orchestrator.py).

This V1 pipeline is a simpler mock-only flow without provider abstraction,
real API integration, streaming, or the full 13-stage pipeline. It is NOT
used by the primary /api/plan endpoint.
"""

from backend.data_loader import load_all, get_user, get_family_profile, get_pois, get_restaurants
from backend.agent.parser import parse_intent, extract_constraints
from backend.agent.scorer import score_poi, score_restaurant
from backend.agent.planner import build_itinerary
from backend.agent.executor import execute_actions
from backend.agent.response_generator import generate_full_response
from backend.tools.poi_tools import search_poi
from backend.tools.restaurant_tools import search_restaurant, check_restaurant_availability, check_queue_time
from backend.tools.ticket_tools import check_ticket_availability
from backend.tools.travel_tools import estimate_travel_time


def run_local_life_agent(user_id: str, query: str) -> dict:
    """Main entry point: run the complete Local Life Planning Agent pipeline.

    Args:
        user_id: user identifier (e.g., 'u_001')
        query: natural language query

    Returns:
        Complete plan response dict.
    """
    # Ensure data is loaded
    load_all()

    trace = []
    trace.append({"phase": "init", "message": f"Agent启动，用户: {user_id}"})

    # Phase 1: Intent Parsing
    trace.append({"phase": "intent_parsing", "message": "解析用户意图..."})
    intent = parse_intent(query)
    scene = intent["scene"]
    trace.append({
        "phase": "intent_parsing",
        "message": f"识别场景: {scene}，意图: {intent['intent']}",
    })

    # Phase 2: Constraint Extraction
    trace.append({"phase": "constraint_extraction", "message": "提取约束条件..."})
    constraints = extract_constraints(query, user_id, scene)
    trace.append({
        "phase": "constraint_extraction",
        "message": _describe_constraints(constraints),
    })

    user = get_user(user_id)
    home_district = constraints.get("home_district", user["home_location"]["district"])
    home_id = f"home_{user_id}"

    # Phase 3: Candidate Retrieval
    trace.append({"phase": "candidate_retrieval", "message": "搜索候选POI..."})
    poi_result = search_poi(
        location=home_district,
        radius_km=constraints["max_distance_km"],
        scene=scene,
        age=constraints.get("child_age"),
        indoor_only="indoor" in str(constraints.get("preferences", [])),
    )
    trace.append({
        "phase": "candidate_retrieval",
        "message": f"找到 {len(poi_result.get('data', []))} 个POI候选",
    })

    trace.append({"phase": "candidate_retrieval", "message": "搜索候选餐厅..."})
    rest_result = search_restaurant(
        location=home_district,
        radius_km=constraints["max_distance_km"],
        scene=scene,
        has_low_fat=scene == "family",
        has_kids_meal=scene == "family",
    )
    trace.append({
        "phase": "candidate_retrieval",
        "message": f"找到 {len(rest_result.get('data', []))} 个餐厅候选",
    })

    pois = poi_result.get("data", [])
    restaurants = rest_result.get("data", [])

    # Fallback: if no results, broaden search
    if not pois:
        trace.append({
            "phase": "fallback",
            "message": "原始范围无POI结果，扩大搜索范围至15km",
        })
        poi_result = search_poi(location=home_district, radius_km=15, scene=scene)
        pois = poi_result.get("data", [])

    if not restaurants:
        trace.append({
            "phase": "fallback",
            "message": "原始范围无餐厅结果，扩大搜索范围",
        })
        rest_result = search_restaurant(location=home_district, radius_km=15, scene=scene)
        restaurants = rest_result.get("data", [])

    # Phase 4: Feasibility Check
    trace.append({"phase": "feasibility_check", "message": "检查可行性（门票、空位、交通）..."})

    poi_scores = []
    poi_travel = {}
    for poi in pois:
        # Check ticket availability
        ticket = check_ticket_availability(
            poi_id=poi["poi_id"],
            adult_count=max(1, constraints["party_size"] - (1 if constraints.get("child_age") else 0)),
            child_count=1 if constraints.get("child_age") else 0,
            preferred_time=constraints["start_time"],
        )
        ticket_data = ticket.get("data", {})

        # Estimate travel from home
        travel = estimate_travel_time(home_id, poi["poi_id"], constraints.get("transport", "taxi"))
        travel_data = travel.get("data", {})
        distance = travel_data.get("distance_km", 5)
        poi_travel[poi["poi_id"]] = travel_data

        # Filter by max distance
        if distance > constraints["max_distance_km"] * 1.5:
            trace.append({
                "phase": "feasibility_check",
                "message": f"{poi['name']} 距离 {distance:.1f}km，超过限制 {constraints['max_distance_km']}km，剔除",
            })
            poi_scores.append(-1.0)
            continue

        # Filter by child age
        child_age = constraints.get("child_age")
        if child_age is not None:
            age_min, age_max = poi.get("age_range", [0, 99])
            if child_age < age_min or child_age > age_max:
                trace.append({
                    "phase": "feasibility_check",
                    "message": f"{poi['name']} 不适合 {child_age} 岁儿童（适合 {age_min}-{age_max} 岁），剔除",
                })
                poi_scores.append(-1.0)
                continue

        s = score_poi(poi, distance, scene, constraints, ticket_data)
        poi_scores.append(s)

    rest_scores = []
    rest_travel = {}
    for r in restaurants:
        # Check availability
        meal_time = "17:00"
        avail = check_restaurant_availability(r["restaurant_id"], meal_time, constraints["party_size"])
        avail_data = avail.get("data", {})

        # Estimate travel from home
        travel = estimate_travel_time(home_id, r["restaurant_id"], constraints.get("transport", "taxi"))
        travel_data = travel.get("data", {})
        distance = travel_data.get("distance_km", 5)
        rest_travel[r["restaurant_id"]] = travel_data

        # Check queue
        queue = check_queue_time(r["restaurant_id"], meal_time)
        queue_data = queue.get("data", {})

        # Check restaurant open time
        open_t = r.get("open_time", "00:00")
        close_t = r.get("close_time", "23:59")
        if meal_time < open_t or constraints["end_time"] > close_t:
            trace.append({
                "phase": "feasibility_check",
                "message": f"{r['name']} 营业时间 {open_t}-{close_t}，与行程不匹配，降权",
            })

        s = score_restaurant(r, distance, scene, constraints, avail_data)
        rest_scores.append(s)

        if not avail_data.get("available") and not avail_data.get("remaining_tables", 0):
            suggestions = avail_data.get("suggested_slots", [])
            if suggestions:
                trace.append({
                    "phase": "feasibility_check",
                    "message": f"{r['name']} {meal_time} 无位，推荐时段: {', '.join(suggestions[:3])}",
                })

    # Phase 5: Itinerary Construction
    trace.append({"phase": "itinerary_construction", "message": "构建行程..."})
    plan = build_itinerary(
        scene=scene,
        constraints=constraints,
        pois=pois,
        restaurants=restaurants,
        poi_travel=poi_travel,
        rest_travel=rest_travel,
        poi_scores=poi_scores,
        rest_scores=rest_scores,
        home_id=home_id,
    )
    trace.append({
        "phase": "itinerary_construction",
        "message": f"行程构建完成，共 {len(plan['itinerary'])} 段，总时长 {plan['total_time_min']} 分钟",
    })

    # Phase 6: Generate share message first (needed for execution)
    selected_poi = plan.get("selected_poi")
    selected_restaurant = plan.get("selected_restaurant")

    # Phase 7: Action Execution
    trace.append({"phase": "execution", "message": "执行工具调用..."})
    share_msg = _build_share_message_preview(scene, plan, constraints, selected_poi, selected_restaurant)
    exec_result = execute_actions(
        user_id=user_id,
        scene=scene,
        itinerary=plan["itinerary"],
        selected_poi=selected_poi,
        selected_restaurant=selected_restaurant,
        constraints=constraints,
        share_message=share_msg,
    )

    for tc in exec_result["tool_calls"]:
        status = "成功" if tc["success"] else "失败"
        trace.append({
            "phase": "execution",
            "message": f"工具 {tc['tool']}: {status} - {tc.get('message', '')}",
        })

    # Phase 8: Final Response
    trace.append({"phase": "response", "message": "生成最终响应..."})

    response = generate_full_response(
        scene=scene,
        constraints=constraints,
        planning_trace=trace,
        tool_calls=exec_result["tool_calls"],
        itinerary=plan["itinerary"],
        completed_actions=exec_result["completed_actions"],
        fallback_actions=exec_result["fallback_actions"],
        selected_poi=selected_poi,
        selected_restaurant=selected_restaurant,
        plan_score=plan.get("plan_score", 0),
        total_time_min=plan.get("total_time_min", 0),
    )

    return response


def _describe_constraints(c: dict) -> str:
    parts = [
        f"场景: {c['scene']}",
        f"时间: {c['start_time']}-{c['end_time']}",
        f"人数: {c['party_size']}",
        f"最大距离: {c['max_distance_km']}km",
    ]
    if c.get("child_age"):
        parts.append(f"孩子年龄: {c['child_age']}岁")
    return "，".join(parts)


def _build_share_message_preview(scene, plan, constraints, poi, restaurant) -> str:
    """Build a preliminary share message for execution."""
    from backend.agent.response_generator import generate_share_message
    return generate_share_message(
        scene, plan["itinerary"], poi, restaurant, [], constraints
    )
