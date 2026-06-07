"""Route planned tasks to domain tools and return one uniform result per task."""

from collections.abc import Callable

from src.core.task_ranker import rank_task_candidates
from src.providers.amap_provider import AmapProvider
from src.schemas.models import (
    PlanEvent,
    PlannedTask,
    PreferenceProfile,
    ResolvedLocation,
    ToolExecutionResult,
    UserIntent,
)
from src.tools.food_order_tool import order_food
from src.tools.poi_tool import search_task_pois
from src.tools.restaurant_tool import search_restaurants


EventCallback = Callable[[PlanEvent], None]


class ToolRouter:
    """Execute tasks independently without deciding itinerary structure."""

    def __init__(
        self,
        amap_provider: AmapProvider | None = None,
    ):
        self.amap = amap_provider

    def execute(
        self,
        tasks: list[PlannedTask],
        intent: UserIntent,
        location: ResolvedLocation,
        event_callback: EventCallback | None = None,
        profile: PreferenceProfile | None = None,
    ) -> list[ToolExecutionResult]:
        results = []
        _emit(
            event_callback,
            "tool_routing",
            f"正在为 {len(tasks)} 个任务选择工具...",
            {"task_count": len(tasks)},
        )
        for task in tasks:
            _emit(
                event_callback,
                "tool_execution",
                f"正在执行：{task.description}",
                {
                    "task_id": task.task_id,
                    "tool_name": task.tool_name,
                    "search_query": task.search_query,
                },
            )
            try:
                result = self._execute_task(
                    task,
                    intent,
                    location,
                    event_callback,
                    profile,
                )
            except Exception as exc:
                result = ToolExecutionResult(
                    task_id=task.task_id,
                    tool_name=task.tool_name,
                    status="failed",
                    message=str(exc) or f"{task.description}执行失败",
                )
            results.append(result)
            _emit(
                event_callback,
                "tool_execution",
                (
                    f"{task.description}执行完成"
                    if result.status == "success"
                    else f"{task.description}执行失败"
                ),
                {
                    "task_id": task.task_id,
                    "status": result.status,
                    "candidate_count": len(result.candidates),
                },
                source=_result_source(result),
            )
        return results

    def _execute_task(
        self,
        task: PlannedTask,
        intent: UserIntent,
        location: ResolvedLocation,
        event_callback: EventCallback | None,
        profile: PreferenceProfile | None,
    ) -> ToolExecutionResult:
        if task.task_type == "food_delivery":
            _emit(
                event_callback,
                "food_order_mock",
                f"正在模拟点餐：{task.target or '餐食'}...",
                {"task_id": task.task_id, "target": task.target},
                source="mock",
            )
            action = order_food(
                task.target or "餐食",
                task.time_window,
                _origin_name(location),
            )
            return ToolExecutionResult(
                task_id=task.task_id,
                tool_name=task.tool_name,
                status="success",
                selected_result=action.model_dump(mode="python"),
                message=action.message,
            )

        if task.task_type == "restaurant_search":
            _emit(
                event_callback,
                "restaurant_search",
                f"正在搜索：{task.search_query or task.target or '餐厅'}...",
                {"task_id": task.task_id, "queries": _queries(task)},
            )
            candidates = search_restaurants(
                intent,
                location,
                _queries(task),
                self.amap,
            )
            return _search_result(task, candidates, intent, profile)

        if task.task_type in {
            "poi_search",
            "bar_visit",
            "hotel_search",
        }:
            target = task.target or "地点"
            _emit(
                event_callback,
                "task_poi_search",
                f"正在搜索：{task.search_query or target}...",
                {
                    "task_id": task.task_id,
                    "task_type": task.task_type,
                    "search_query": task.search_query,
                },
                source=(
                    "amap"
                    if self.amap is not None and self.amap.is_available
                    else "mock"
                ),
            )
            if task.task_type == "poi_search":
                _emit(
                    event_callback,
                    "activity_search",
                    f"正在搜索{target}...",
                    {"task_id": task.task_id},
                )
            candidates = search_task_pois(
                intent,
                location,
                task,
                self.amap,
            )
            result = _search_result(task, candidates, intent, profile)
            _emit(
                event_callback,
                "task_poi_search",
                f"搜索“{task.search_query or target}”找到 {len(candidates)} 个候选",
                {
                    "task_id": task.task_id,
                    "candidate_count": len(candidates),
                    "search_query": task.search_query or target,
                },
                source=_result_source(result),
            )
            if result.status == "success":
                selected = result.selected_result or {}
                reasons = selected.get("selection_reasons", [])
                reason_text = "；".join(reasons) or "任务相关性最高"
                _emit(
                    event_callback,
                    "task_poi_search",
                    f"已选择：{selected.get('name', target)}，原因：{reason_text}",
                    {
                        "task_id": task.task_id,
                        "selected_result": selected,
                        "selection_reasons": reasons,
                    },
                )
            else:
                _emit(
                    event_callback,
                    "task_poi_search",
                    f"{len(candidates)} 个{target}候选均不符合任务要求",
                    {
                        "task_id": task.task_id,
                        "candidate_count": len(candidates),
                    },
                )
            if result.rejected_candidates:
                _emit(
                    event_callback,
                    "task_poi_search",
                    (
                        f"已过滤 {len(result.rejected_candidates)} "
                        "个弱相关候选"
                    ),
                    {
                        "task_id": task.task_id,
                        "rejected_candidates": result.rejected_candidates,
                        "debug": True,
                    },
                    source=_result_source(result),
                )
            return result

        return ToolExecutionResult(
            task_id=task.task_id,
            tool_name=task.tool_name,
            status="failed",
            message=f"不支持的任务类型：{task.task_type}",
        )


def _search_result(
    task: PlannedTask,
    candidates: list[dict],
    intent: UserIntent,
    profile: PreferenceProfile | None,
) -> ToolExecutionResult:
    if not candidates:
        return ToolExecutionResult(
            task_id=task.task_id,
            tool_name=task.tool_name,
            status="failed",
            message=f"没有找到可用的{task.target or '地点'}。",
        )
    from src.services.preference_service import get_current_profile

    ranking = rank_task_candidates(
        task,
        candidates,
        intent,
        profile or get_current_profile(),
    )
    if ranking.selected_candidate is None:
        return ToolExecutionResult(
            task_id=task.task_id,
            tool_name=task.tool_name,
            status="failed",
            candidates=candidates,
            rejected_candidates=ranking.rejected_candidates,
            message="no_relevant_result",
        )
    selected = dict(ranking.selected_candidate)
    selected["task_id"] = task.task_id
    selected["task_type"] = task.task_type
    selected["route_needed"] = task.route_needed
    return ToolExecutionResult(
        task_id=task.task_id,
        tool_name=task.tool_name,
        status="success",
        selected_result=selected,
        candidates=ranking.ranked_candidates,
        rejected_candidates=ranking.rejected_candidates,
        message=f"已选择{selected.get('name', task.target or '候选地点')}",
    )


def _queries(task: PlannedTask) -> list[str]:
    return [
        item
        for item in (task.search_query or task.target or "附近餐厅").split()
        if item
    ]


def _result_source(result: ToolExecutionResult) -> str:
    sources = {
        item.get("source")
        for item in [
            *(result.candidates or []),
            *(result.rejected_candidates or []),
            *([result.selected_result] if result.selected_result else []),
        ]
    }
    if "amap" in sources:
        return "amap"
    if "mock" in sources:
        return "mock"
    return "mock"


def _origin_name(location: ResolvedLocation) -> str:
    if location.source == "demo_default":
        return "默认位置：上海徐汇"
    return location.address


def _emit(
    callback: EventCallback | None,
    stage: str,
    message: str,
    data: dict | None = None,
    source: str = "system",
) -> None:
    if callback is None:
        return
    callback(
        PlanEvent(
            type="progress",
            stage=stage,
            message=message,
            data=data or {},
            source=source,
        )
    )
