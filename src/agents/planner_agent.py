"""Single orchestration pipeline with optional DeepSeek and AMap providers."""

import logging
from collections.abc import Callable

from src.agents.executor_agent import ExecutorAgent
from src.core.decision_explainer import explain_decision
from src.core.exception_detector import detect_exceptions
from src.core.final_composer import compose_final_copy
from src.core.itinerary_composer import compose_itinerary
from src.core.itinerary_builder import build_multistep_itinerary
from src.core.llm_intent_parser import parse_intent_with_llm
from src.core.llm_task_planner import plan_tasks
from src.core.plan_builder import build_plan, build_timeline
from src.core.query_planner import build_query_plan
from src.core.ranking import rank_pois, rank_restaurants
from src.core.replan_service import build_replan_proposals
from src.providers.amap_provider import AmapProvider
from src.providers.deepseek_provider import DeepSeekProvider
from src.schemas.models import (
    FinalComposition,
    LocationInput,
    PlanEvent,
    PlanResponse,
    TaskPlan,
    UserIntent,
)
from src.services.location_service import resolve_location
from src.services.preference_service import (
    build_preference_explanation,
    get_current_profile,
)
from src.config.settings import current_demo_scenario
from src.tools.message_tool import (
    build_multistep_message,
    build_task_plan_message,
    message_target,
    send_message,
)
from src.tools.poi_tool import search_pois, search_task_pois
from src.tools.restaurant_tool import search_restaurants
from src.tools.route_tool import build_route_plan, estimate_route
from src.core.tool_router import ToolRouter
from src.tools.weather_tool import get_weather


logger = logging.getLogger(__name__)
EventCallback = Callable[[PlanEvent], None]


class PlannerAgent:
    """Coordinate one shared planning flow for JSON and SSE endpoints."""

    def __init__(
        self,
        executor: ExecutorAgent | None = None,
        deepseek_provider: DeepSeekProvider | None = None,
        amap_provider: AmapProvider | None = None,
    ):
        self.executor = executor or ExecutorAgent()
        self.deepseek = deepseek_provider or DeepSeekProvider()
        self.amap = amap_provider or AmapProvider()

    def plan(
        self,
        query: str,
        requested_location: LocationInput | None = None,
    ) -> PlanResponse:
        """Keep the original non-streaming API on the shared run pipeline."""
        return self.run(query, requested_location)

    def run(
        self,
        query: str,
        requested_location: LocationInput | None = None,
        event_callback: EventCallback | None = None,
    ) -> PlanResponse:
        """Generate one plan and optionally report provider-aware progress."""
        emit = lambda event: _emit_safely(event_callback, event)
        profile = get_current_profile()

        if getattr(self.deepseek, "demo_mode", False):
            emit(_event(
                "api_fallback_triggered",
                "Demo Mode：使用本地 Mock Planner",
                source="mock",
            ))
        if getattr(self.amap, "demo_mode", False):
            emit(_event(
                "api_fallback_triggered",
                "Demo Mode：使用本地 Mock POI",
                source="mock",
            ))
            emit(_event(
                "api_fallback_triggered",
                "Demo Mode：使用 Mock Route",
                source="mock",
            ))

        emit(_event("intent_parsing", "正在理解你的需求..."))
        if self.deepseek.is_available:
            emit(_event(
                "llm_intent_started",
                "正在用 DeepSeek 理解你的需求...",
                source="deepseek",
            ))
        intent, llm_intent_used, intent_error = parse_intent_with_llm(
            query,
            profile,
            self.deepseek,
        )
        if self.deepseek.is_available:
            if llm_intent_used:
                emit(_event(
                    "llm_intent_finished",
                    f"DeepSeek 已识别：{_format_intent_summary(intent)}",
                    source="deepseek",
                    data={"public_reasoning": intent.public_reasoning},
                ))
            else:
                _emit_fallback(
                    emit,
                    intent_error,
                    "DeepSeek 意图解析不可用，已切换规则解析。",
                )
        emit(_event(
            "intent_parsed",
            f"已识别：{_format_intent_summary(intent)}",
            data={
                "scene": intent.scene,
                "child_age": intent.child_age,
                "distance_preference": intent.distance_preference,
                "activity_preferences": intent.activity_preferences,
                "diet_preferences": intent.diet_preferences,
                "source": "deepseek" if llm_intent_used else "rule",
            },
        ))
        if self.deepseek.is_available:
            emit(_event(
                "llm_task_planning_started",
                "正在用 DeepSeek 拆解有序任务...",
                source="deepseek",
            ))
        task_plan, task_llm_used, task_error = plan_tasks(
            query,
            intent,
            profile,
            self.deepseek,
        )
        if self.deepseek.is_available:
            if task_llm_used:
                emit(_event(
                    "llm_task_planning_finished",
                    f"DeepSeek 已拆解 {len(task_plan.tasks)} 个任务",
                    source="deepseek",
                    data={
                        "tasks": [
                            task.model_dump(mode="json")
                            for task in task_plan.tasks
                        ]
                    },
                ))
            else:
                _emit_fallback(
                    emit,
                    task_error,
                    "DeepSeek 任务规划不可用，已切换规则任务规划。",
                )
        intent.tasks = task_plan.tasks
        intent.time_windows = task_plan.time_windows
        emit(_event(
            "task_decomposition",
            (
                "已识别："
                + " / ".join(task.description for task in task_plan.tasks)
                if task_plan.tasks
                else "任务规划未产生任务，切换兼容流程"
            ),
            data={
                "tasks": [
                    task.model_dump(mode="json") for task in task_plan.tasks
                ],
                "time_windows": task_plan.time_windows,
                "source": "deepseek" if task_llm_used else "rule",
            },
        ))
        if task_plan.tasks:
            return self._run_task_driven(
                intent,
                task_plan,
                profile,
                requested_location,
                emit,
            )

        if self.deepseek.enabled:
            emit(_event(
                "query_planning_started",
                "正在生成活动和餐厅搜索关键词...",
                source="deepseek",
            ))
        query_plan, query_llm_used, query_error = build_query_plan(
            intent,
            profile,
            self.deepseek,
        )
        if self.deepseek.enabled:
            if query_llm_used:
                emit(_event(
                    "query_planning_finished",
                    "搜索关键词已生成",
                    source="deepseek",
                    data={
                        "poi_queries": query_plan.poi_queries,
                        "restaurant_queries": query_plan.restaurant_queries,
                        "public_reasoning": query_plan.public_reasoning,
                    },
                ))
            else:
                _emit_fallback(
                    emit,
                    query_error,
                    "DeepSeek 搜索词规划不可用，已使用规则搜索词。",
                )

        location = resolve_location(
            intent,
            requested_location,
            self.amap if self.amap.is_available else None,
        )
        if (
            requested_location
            and requested_location.address
            and requested_location.lat is None
            and self.amap.enabled
            and location.source == "demo_default"
        ):
            _emit_fallback(
                emit,
                self.amap.last_error or self.amap.unavailable_reason,
                "高德地理编码不可用，已使用上海徐汇 Demo 默认位置。",
            )
        weather = get_weather(location)

        emit(_event(
            "activity_search",
            "正在搜索附近适合同行人的活动...",
            data={
                "location": location.address,
                "max_travel_minutes": query_plan.max_travel_minutes,
            },
        ))
        if self.amap.enabled and self.amap.is_available:
            emit(_event(
                "amap_poi_search_started",
                "正在调用高德搜索附近活动...",
                source="amap",
                data={"queries": query_plan.poi_queries},
            ))
        poi_candidates = search_pois(
            intent,
            location,
            query_plan.poi_queries,
            self.amap,
        )
        poi_uses_amap = _uses_source(poi_candidates, "amap")
        if self.amap.enabled:
            if poi_uses_amap:
                emit(_event(
                    "amap_poi_search_finished",
                    f"高德找到 {len(poi_candidates)} 个地点，已补充本地生活标签",
                    source="amap",
                    data={"candidate_count": len(poi_candidates)},
                ))
            else:
                _emit_fallback(
                    emit,
                    self.amap.last_error or self.amap.unavailable_reason,
                    "高德地点搜索暂不可用，已切换 Mock 活动数据。",
                )
        if not poi_candidates:
            raise ValueError("没有符合条件的活动地点。")
        emit(_event(
            "activity_search",
            f"找到 {len(poi_candidates)} 个候选活动",
            data={
                "candidate_count": len(poi_candidates),
                "source": "amap" if poi_uses_amap else "mock",
            },
        ))

        home_routes = {
            poi["id"]: estimate_route(
                location.location_id,
                poi["id"],
                location,
                poi,
                None,
                query_plan.route_mode,
            )
            for poi in poi_candidates
        }
        ranked_pois = rank_pois(
            poi_candidates,
            intent,
            home_routes,
            weather,
            profile.preference,
            profile.weights,
        )
        selected_poi = ranked_pois[0]

        emit(_event(
            "restaurant_search",
            "正在筛选适合饮食偏好的餐厅...",
        ))
        if self.amap.enabled and self.amap.is_available:
            emit(_event(
                "amap_restaurant_search_started",
                "正在调用高德搜索附近餐厅...",
                source="amap",
                data={"queries": query_plan.restaurant_queries},
            ))
        restaurant_candidates = search_restaurants(
            intent,
            location,
            query_plan.restaurant_queries,
            self.amap,
        )
        restaurant_uses_amap = _uses_source(
            restaurant_candidates,
            "amap",
        )
        if self.amap.enabled:
            if restaurant_uses_amap:
                emit(_event(
                    "amap_restaurant_search_finished",
                    (
                        f"高德找到 {len(restaurant_candidates)} 家餐厅，"
                        "已补充评分、排队和预约 Mock 字段"
                    ),
                    source="amap",
                    data={"candidate_count": len(restaurant_candidates)},
                ))
            else:
                _emit_fallback(
                    emit,
                    self.amap.last_error or self.amap.unavailable_reason,
                    "高德餐厅搜索暂不可用，已切换 Mock 餐厅数据。",
                )
        if not restaurant_candidates:
            raise ValueError("没有符合条件的餐厅。")
        emit(_event(
            "restaurant_search",
            f"找到 {len(restaurant_candidates)} 家候选餐厅",
            data={
                "candidate_count": len(restaurant_candidates),
                "source": "amap" if restaurant_uses_amap else "mock",
            },
        ))

        restaurant_routes = {
            restaurant["id"]: estimate_route(
                selected_poi["id"],
                restaurant["id"],
                selected_poi,
                restaurant,
                None,
                query_plan.route_mode,
            )
            for restaurant in restaurant_candidates
        }
        ranked_restaurants = rank_restaurants(
            restaurant_candidates,
            intent,
            restaurant_routes,
            profile.preference,
            profile.weights,
        )
        selected_restaurant = ranked_restaurants[0]

        emit(_event(
            "route_planning",
            "正在规划活动、餐厅和返程路线...",
        ))
        if self.amap.enabled and self.amap.is_available:
            emit(_event(
                "amap_route_started",
                "正在调用高德规划最终三段路线...",
                source="amap",
            ))
        home_routes[selected_poi["id"]] = estimate_route(
            location.location_id,
            selected_poi["id"],
            location,
            selected_poi,
            self.amap,
            query_plan.route_mode,
        )
        restaurant_routes[selected_restaurant["id"]] = estimate_route(
            selected_poi["id"],
            selected_restaurant["id"],
            selected_poi,
            selected_restaurant,
            self.amap,
            query_plan.route_mode,
        )
        return_route = estimate_route(
            selected_restaurant["id"],
            location.location_id,
            selected_restaurant,
            location,
            self.amap,
            query_plan.route_mode,
        )
        selected_routes = {
            selected_poi["id"]: home_routes[selected_poi["id"]],
            selected_restaurant["id"]: restaurant_routes[
                selected_restaurant["id"]
            ],
            "return_to_origin": return_route,
        }
        route_uses_amap = any(
            route.source == "amap" for route in selected_routes.values()
        )
        if self.amap.enabled:
            if route_uses_amap:
                emit(_event(
                    "amap_route_finished",
                    "高德路线估算完成",
                    source="amap",
                    data={
                        "durations": {
                            key: route.duration_min
                            for key, route in selected_routes.items()
                        }
                    },
                ))
            else:
                _emit_fallback(
                    emit,
                    self.amap.last_error or self.amap.unavailable_reason,
                    "高德路线接口暂不可用，已切换 Mock 路线估算。",
                )

        activity_plan = build_plan(
            intent=intent,
            location=location,
            poi=selected_poi,
            restaurant=selected_restaurant,
            home_to_poi=home_routes[selected_poi["id"]],
            poi_to_restaurant=restaurant_routes[selected_restaurant["id"]],
            restaurant_to_home=return_route,
            weather=weather,
        )
        route_plan = build_route_plan(
            origin=location,
            activity=selected_poi,
            restaurant=selected_restaurant,
            home_to_activity=home_routes[selected_poi["id"]],
            activity_to_restaurant=restaurant_routes[
                selected_restaurant["id"]
            ],
            restaurant_to_home=return_route,
        )
        emit(_event(
            "route_planning",
            f"路线已生成，预计总通勤 {route_plan.total_travel_minutes} 分钟",
            data={
                "total_travel_minutes": route_plan.total_travel_minutes,
                "source": route_plan.source,
            },
        ))

        emit(_event("timeline_building", "正在生成可执行时间线..."))
        timeline = build_timeline(
            intent=intent,
            location=location,
            poi=selected_poi,
            restaurant=selected_restaurant,
            home_to_poi=home_routes[selected_poi["id"]],
            poi_to_restaurant=restaurant_routes[selected_restaurant["id"]],
            restaurant_to_home=return_route,
        )
        emit(_event(
            "timeline_building",
            "可执行时间线已生成",
            data={"item_count": len(timeline.items)},
        ))

        if self.deepseek.enabled:
            emit(_event(
                "decision_explanation_started",
                "正在生成选择依据...",
                source="deepseek",
            ))
        decision, explanation_llm_used, explanation_error = explain_decision(
            intent,
            profile,
            ranked_pois,
            ranked_restaurants,
            selected_poi,
            selected_restaurant,
            {
                **home_routes,
                **restaurant_routes,
            },
            self.deepseek,
        )
        if self.deepseek.enabled:
            if explanation_llm_used:
                emit(_event(
                    "decision_explanation_finished",
                    "已生成可展示的选择依据",
                    source="deepseek",
                    data={"public_reasoning": decision.public_reasoning},
                ))
            else:
                _emit_fallback(
                    emit,
                    explanation_error,
                    "DeepSeek 决策解释不可用，已使用规则解释。",
                )
        activity_plan.reasons = _unique(
            activity_plan.reasons + decision.selected_reasons
        )
        preference_explanation = decision.preference_explanation

        actions = self.executor.execute(
            intent,
            activity_plan,
            selected_restaurant,
            event_callback=emit,
        )
        message_action = next(
            action for action in actions if action.type == "send_message"
        )
        fallback_share_message = message_action.message or ""

        if self.deepseek.enabled:
            emit(_event(
                "final_composer_started",
                "正在用 DeepSeek 优化最终文案...",
                source="deepseek",
            ))
        composition, composer_llm_used, composer_error = compose_final_copy(
            activity_plan,
            timeline,
            route_plan,
            actions,
            preference_explanation,
            fallback_share_message,
            self.deepseek,
        )
        if self.deepseek.enabled:
            if composer_llm_used:
                emit(_event(
                    "final_composer_finished",
                    "最终方案文案已生成",
                    source="deepseek",
                ))
            else:
                _emit_fallback(
                    emit,
                    composer_error,
                    "DeepSeek 最终文案不可用，已保留规则文案。",
                )
        activity_plan.summary = composition.summary
        message_action.message = composition.share_message

        natural_language = _format_natural_language(
            intent,
            activity_plan,
            route_plan.total_travel_minutes,
            actions,
            preference_explanation,
            composition.timeline_explanation,
        )
        response = PlanResponse(
            user_intent=intent,
            plan=activity_plan,
            route=route_plan,
            timeline=timeline,
            actions=actions,
            preference_explanation=preference_explanation,
            decision_explanation=decision,
            composition=composition,
            natural_language=natural_language,
        )
        emit(_event("completed", "方案生成完成"))
        return response

    def _run_task_driven(
        self,
        intent: UserIntent,
        task_plan: TaskPlan,
        profile,
        requested_location: LocationInput | None,
        emit: Callable[[PlanEvent], None],
    ) -> PlanResponse:
        """Execute the primary task-planner -> router -> composer pipeline."""
        location = resolve_location(
            intent,
            requested_location,
            self.amap if self.amap.is_available else None,
        )
        tool_results = ToolRouter(self.amap).execute(
            task_plan.tasks,
            intent,
            location,
            event_callback=emit,
            profile=profile,
        )

        emit(_event(
            "itinerary_composing",
            "正在合并任务结果并生成路线与时间线...",
        ))
        emit(_event(
            "multistep_itinerary_building",
            "正在按任务顺序生成行程...",
        ))
        itinerary = compose_itinerary(
            intent,
            task_plan,
            tool_results,
            location,
            self.amap,
        )
        emit(_event(
            "route_planning",
            f"路线已生成，共 {len(itinerary.route.stops)} 个线下地点",
            data={
                "route_stops": len(itinerary.route.stops),
                "total_travel_minutes": itinerary.route.total_travel_minutes,
                "source": itinerary.route.source,
            },
        ))
        emit(_event(
            "timeline_building",
            "可执行时间线已生成",
            data={"item_count": len(itinerary.timeline.items)},
        ))
        for action in itinerary.actions:
            if action.type == "reservation":
                emit(_event(
                    "reservation_mock",
                    (
                        "餐厅模拟预约失败"
                        if action.status == "mock_failed"
                        else "餐厅模拟预约方案已准备"
                    ),
                    source="mock",
                    data={
                        "target": action.target,
                        "status": action.status,
                    },
                ))

        emit(_event(
            "message_generation",
            "正在生成任务计划消息...",
        ))
        message = build_task_plan_message(
            intent,
            task_plan,
            itinerary.plan,
            itinerary.warnings,
        )
        message_action = send_message(message_target(intent.scene), message)
        actions = [*itinerary.actions, message_action]
        emit(_event(
            "message_generation",
            "任务计划消息已生成",
            data={"target": message_action.target},
        ))

        warnings_text = (
            "；".join(itinerary.warnings)
            if itinerary.warnings
            else "当前任务顺序可执行。"
        )
        composition = FinalComposition(
            summary=itinerary.plan.summary,
            timeline_explanation=(
                "路线仅包含需要到店的任务，外卖不进入路线。"
                f"{warnings_text}"
            ),
            share_message=message,
        )
        preference_explanation = [
            *build_preference_explanation(profile.preference),
            "优先遵循用户明确给出的任务顺序和时间窗口。",
            *itinerary.warnings,
        ]
        natural_language = _format_task_driven_natural_language(
            itinerary.plan,
            itinerary.route.total_travel_minutes,
            actions,
            itinerary.warnings,
        )
        response = PlanResponse(
            user_intent=intent,
            task_plan=task_plan,
            plan=itinerary.plan,
            route=itinerary.route,
            timeline=itinerary.timeline,
            actions=actions,
            preference_explanation=preference_explanation,
            decision_explanation=None,
            composition=composition,
            planning_warnings=itinerary.warnings,
            natural_language=natural_language,
        )
        _attach_exception_replans(
            response,
            tool_results,
            emit,
        )
        emit(_event(
            "itinerary_composing",
            "任务驱动行程已生成",
            data={
                "timeline_items": len(itinerary.timeline.items),
                "warning_count": len(itinerary.warnings),
            },
        ))
        emit(_event(
            "multistep_itinerary_building",
            "多阶段行程已生成",
            data={
                "timeline_items": len(itinerary.timeline.items),
                "route_stops": len(itinerary.route.stops),
            },
        ))
        emit(_event("completed", "方案生成完成"))
        return response

    def _run_multistep(
        self,
        intent: UserIntent,
        requested_location: LocationInput | None,
        emit: Callable[[PlanEvent], None],
    ) -> PlanResponse:
        """Execute ordered tasks without entering the fixed restaurant flow."""
        location = resolve_location(
            intent,
            requested_location,
            self.amap if self.amap.is_available else None,
        )
        selected_places = []
        for task in intent.tasks:
            if task.task_type == "food_order":
                emit(_event(
                    "food_order_mock",
                    f"正在模拟点餐：{task.target or '餐食'}...",
                    data={"task_id": task.task_id, "target": task.target},
                ))
                continue
            if task.task_type not in {"activity_search", "bar_visit"}:
                continue

            target = task.target or "活动"
            emit(_event(
                "task_poi_search",
                f"正在搜索{target}地点...",
                data={
                    "task_id": task.task_id,
                    "task_type": task.task_type,
                    "target": target,
                },
            ))
            candidates = search_task_pois(
                intent,
                location,
                task,
                self.amap,
            )
            if not candidates:
                raise ValueError(f"没有找到可用的{target}地点。")
            selected = dict(candidates[0])
            selected["task_id"] = task.task_id
            selected["task_type"] = task.task_type
            selected_places.append(selected)
            emit(_event(
                "task_poi_search",
                f"找到 {len(candidates)} 个{target}地点",
                data={
                    "task_id": task.task_id,
                    "candidate_count": len(candidates),
                    "selected": selected["name"],
                    "source": selected.get("source", "mock"),
                },
                source=(
                    "amap"
                    if selected.get("source") == "amap"
                    else "mock"
                ),
            ))

        route_legs = []
        previous_id = location.location_id
        previous = location
        for place in selected_places:
            leg = estimate_route(
                previous_id,
                place["id"],
                previous,
                place,
                self.amap,
            )
            route_legs.append(leg)
            previous_id = place["id"]
            previous = place
        return_leg = estimate_route(
            previous_id,
            location.location_id,
            previous,
            location.model_dump(mode="python"),
            self.amap,
        )

        emit(_event(
            "multistep_itinerary_building",
            "正在按时间顺序生成行程...",
        ))
        itinerary = build_multistep_itinerary(
            intent,
            location,
            selected_places,
            route_legs,
            return_leg,
        )
        food_action = next(
            (
                action
                for action in itinerary.actions
                if action.type == "food_order"
            ),
            None,
        )
        if food_action:
            emit(_event(
                "food_order_mock",
                f"{food_action.target}点餐已模拟完成",
                data={
                    "target": food_action.target,
                    "status": food_action.status,
                },
                source="mock",
            ))

        message = build_multistep_message(intent, itinerary.plan)
        message_action = send_message(message_target(intent.scene), message)
        actions = [*itinerary.actions, message_action]
        composition = FinalComposition(
            summary=itinerary.plan.summary,
            timeline_explanation=(
                "行程按中午点餐、下午活动、晚上酒吧的顺序安排；"
                f"线下总通勤约 {itinerary.route.total_travel_minutes} 分钟。"
            ),
            share_message=message,
        )
        preference_explanation = [
            "本次优先遵循用户明确给出的中午、下午和晚上顺序。"
        ]
        natural_language = _format_multistep_natural_language(
            itinerary.plan,
            itinerary.route.total_travel_minutes,
            actions,
        )
        response = PlanResponse(
            user_intent=intent,
            plan=itinerary.plan,
            route=itinerary.route,
            timeline=itinerary.timeline,
            actions=actions,
            preference_explanation=preference_explanation,
            decision_explanation=None,
            composition=composition,
            natural_language=natural_language,
        )
        emit(_event(
            "multistep_itinerary_building",
            "多阶段行程已生成",
            data={
                "timeline_items": len(itinerary.timeline.items),
                "route_stops": len(itinerary.route.stops),
            },
        ))
        emit(_event("completed", "方案生成完成"))
        return response


def _is_multistep_intent(intent: UserIntent) -> bool:
    actionable = [
        task
        for task in intent.tasks
        if task.task_type in {
            "food_order",
            "activity_search",
            "restaurant_visit",
            "bar_visit",
        }
    ]
    return (
        len(actionable) >= 2
        and (
            len({task.time_window for task in actionable}) >= 2
            or len({task.task_type for task in actionable}) >= 2
        )
    )


def _event(
    stage: str,
    message: str,
    source: str = "system",
    data: dict | None = None,
) -> PlanEvent:
    return PlanEvent(
        type="progress",
        stage=stage,
        message=message,
        source=source,
        data=data or {},
    )


def _emit_fallback(
    emit: Callable[[PlanEvent], None],
    reason: str | None,
    message: str,
) -> None:
    emit(_event(
        "api_fallback_triggered",
        message,
        source="mock",
        data={"reason": reason or "provider returned no usable result"},
    ))


def _emit_safely(
    event_callback: EventCallback | None,
    event: PlanEvent,
) -> None:
    if event_callback is None:
        return
    try:
        event_callback(event)
    except Exception:
        logger.warning(
            "Plan event callback failed at stage %s",
            event.stage,
            exc_info=True,
        )


def _uses_source(candidates: list[dict], source: str) -> bool:
    return bool(candidates) and all(
        item.get("source") == source for item in candidates
    )


def _attach_exception_replans(
    response: PlanResponse,
    tool_results,
    emit: Callable[[PlanEvent], None],
) -> None:
    """Attach pending consent proposals after the original plan is complete."""
    scenario = current_demo_scenario()
    exceptions = detect_exceptions(
        response,
        tool_results,
        scenario=scenario,
    )
    if not exceptions:
        return
    response.exceptions = exceptions
    for exception in exceptions:
        emit(_event(
            "exception_detected",
            f"检测到：{exception.title}",
            source="mock",
            data={
                "exception_id": exception.exception_id,
                "exception_type": exception.exception_type,
            },
        ))
        emit(_event(
            "replan_search",
            _replan_search_message(exception.exception_type),
            source="mock",
            data={"exception_id": exception.exception_id},
        ))
    response.replan_proposals = build_replan_proposals(
        response,
        exceptions,
        tool_results,
    )
    emit(_event(
        "replan_pending",
        (
            f"已生成 {sum(len(item.options) for item in response.replan_proposals)} "
            "个处理选项，等待你的确认"
        ),
        source="mock",
        data={
            "proposal_count": len(response.replan_proposals),
            "requires_consent": True,
        },
    ))


def _replan_search_message(exception_type: str) -> str:
    if exception_type == "restaurant_full":
        return "正在寻找附近低等待餐厅"
    if exception_type == "activity_unavailable":
        return "正在寻找同类别可用活动"
    return "正在生成调整预约与更换餐厅方案"


def _format_intent_summary(intent: UserIntent) -> str:
    labels = {
        "family": "家庭出行",
        "friends": "朋友聚会",
        "couple": "轻松约会",
        "solo": "个人出行",
    }
    parts = [labels[intent.scene]]
    if intent.child_age is not None:
        parts.append(f"{intent.child_age}岁孩子")
    if intent.diet_preferences:
        parts.append("减脂/清淡饮食")
    if intent.distance_preference == "nearby":
        parts.append("不想太远")
    return " / ".join(parts)


def _format_natural_language(
    intent,
    plan,
    total_travel_minutes,
    actions,
    preference_explanation,
    timeline_explanation,
) -> str:
    lines = [f"已为你生成约 {intent.duration_label}的{plan.summary}：", ""]
    for step in plan.steps:
        place = f"：{step.place}" if step.place else ""
        lines.append(f"{step.time} {step.action}{place}")

    lines.extend(["", "路线说明：", f"- {timeline_explanation}"])
    lines.extend(["", "推荐理由："])
    lines.extend(f"- {reason}" for reason in plan.reasons)
    lines.append(f"- 全程预计通勤 {total_travel_minutes} 分钟")
    lines.extend(["", "个性化调整："])
    lines.extend(f"- {item}" for item in preference_explanation)
    lines.extend(["", "已模拟完成："])
    for action in actions:
        label = "餐厅预约" if action.type == "reservation" else "发送计划消息"
        status = "成功" if action.status == "mock_success" else "失败"
        lines.append(f"- {label}：{status}")
    return "\n".join(lines)


def _format_multistep_natural_language(
    plan,
    total_travel_minutes,
    actions,
) -> str:
    lines = [plan.summary, ""]
    lines.extend(
        f"{step.time} {step.action}"
        + (f"：{step.place}" if step.place else "")
        for step in plan.steps
    )
    lines.extend([
        "",
        f"线下路线总通勤约 {total_travel_minutes} 分钟。",
        "",
        "已模拟完成：",
    ])
    labels = {
        "food_order": "外卖点餐",
        "send_message": "计划消息",
        "reservation": "餐厅预约",
    }
    for action in actions:
        status = "成功" if action.status == "mock_success" else "失败"
        lines.append(f"- {labels[action.type]}：{status}")
    return "\n".join(lines)


def _format_task_driven_natural_language(
    plan,
    total_travel_minutes,
    actions,
    warnings,
) -> str:
    lines = [plan.summary, ""]
    lines.extend(
        f"{step.time} {step.action}"
        + (f"：{step.place}" if step.place else "")
        for step in plan.steps
    )
    if warnings:
        lines.extend(["", "提醒："])
        lines.extend(f"- {warning}" for warning in warnings)
    lines.extend([
        "",
        f"线下路线总通勤约 {total_travel_minutes} 分钟。",
        "",
        "已模拟完成：",
    ])
    labels = {
        "food_order": "外卖点餐",
        "send_message": "计划消息",
        "reservation": "餐厅预约",
    }
    for action in actions:
        status = "成功" if action.status == "mock_success" else "失败"
        lines.append(f"- {labels[action.type]}：{status}")
    return "\n".join(lines)


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))
