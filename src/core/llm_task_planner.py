"""DeepSeek-first task planning with a deterministic rule fallback."""

import json

from pydantic import ValidationError

from src.core.task_decomposer import decompose_planned_tasks
from src.providers.deepseek_provider import DeepSeekProvider
from src.schemas.models import (
    PlannedTask,
    PreferenceProfile,
    TaskPlan,
    UserIntent,
)


SYSTEM_PROMPT = """你是本地生活 Agent 的任务规划器。
只返回一个 JSON object，不要 Markdown，不要输出思维链。
你只负责理解、拆分和排序任务，不负责编造 POI、路线或执行结果。
顶层字段必须是 scene, mood, time_windows, tasks, constraints。
每个 task 必须包含 task_id, time_window, task_type, target,
search_query, tool_name, route_needed, description。
task_type 只能是 food_delivery, poi_search, restaurant_search,
bar_visit, hotel_search。
food_delivery 使用 food_order_tool 且 route_needed=false。
restaurant_search 使用 restaurant_tool 且 route_needed=true。
其他线下任务使用 amap_poi_tool 且 route_needed=true。
必须保留用户表达的任务顺序和全部任务。"""


TOOL_BY_TYPE = {
    "food_delivery": ("food_order_tool", False),
    "poi_search": ("amap_poi_tool", True),
    "restaurant_search": ("restaurant_tool", True),
    "bar_visit": ("amap_poi_tool", True),
    "hotel_search": ("amap_poi_tool", True),
}


def plan_tasks(
    query: str,
    intent: UserIntent,
    profile: PreferenceProfile,
    provider: DeepSeekProvider,
) -> tuple[TaskPlan, bool, str | None]:
    """Return validated ordered tasks, preferring DeepSeek when available."""
    fallback = build_rule_task_plan(query, intent)
    if not provider.is_available:
        return fallback, False, provider.unavailable_reason

    prompt = json.dumps(
        {
            "query": query,
            "intent_profile": intent.model_dump(
                mode="json",
                exclude={"tasks", "time_windows"},
            ),
            "user_preference": profile.model_dump(mode="json"),
            "rule_fallback_hint": fallback.model_dump(mode="json"),
        },
        ensure_ascii=False,
    )
    payload = provider.chat_json(SYSTEM_PROMPT, prompt, "TaskPlan")
    if payload is None:
        return fallback, False, provider.last_error

    try:
        plan = TaskPlan.model_validate(payload)
        plan = _normalize_task_plan(plan, intent)
    except (ValidationError, ValueError) as exc:
        return fallback, False, f"DeepSeek task plan schema 校验失败: {exc}"
    if not plan.tasks:
        return fallback, False, "DeepSeek task plan 未返回可执行任务"
    return plan, True, None


def build_rule_task_plan(query: str, intent: UserIntent) -> TaskPlan:
    """Build the same task contract without selecting any concrete POI."""
    tasks = decompose_planned_tasks(query, intent)
    tired = any(word in query for word in ("累", "疲惫", "没精神"))
    constraints = {
        "energy_level": "low" if tired else "normal",
        "avoid": list(dict.fromkeys([
            *intent.avoid,
            *(["太赶", "太累"] if tired else []),
        ])),
        "preference": (
            ["放松", "顺路"] if tired else ["顺路"]
        ),
    }
    return TaskPlan(
        scene="personal" if intent.scene == "solo" else intent.scene,
        mood="tired_after_work" if tired else "normal",
        time_windows=list(dict.fromkeys(
            task.time_window for task in tasks if task.time_window
        )),
        tasks=tasks,
        constraints=constraints,
    )


def _normalize_task_plan(
    plan: TaskPlan,
    intent: UserIntent,
) -> TaskPlan:
    tasks = []
    for index, task in enumerate(plan.tasks):
        if task.task_type not in TOOL_BY_TYPE:
            raise ValueError(f"不支持的 task_type: {task.task_type}")
        tool_name, route_needed = TOOL_BY_TYPE[task.task_type]
        tasks.append(
            PlannedTask(
                task_id=f"task_{index + 1}",
                time_window=task.time_window or intent.time_window,
                task_type=task.task_type,
                target=task.target,
                search_query=task.search_query or task.target,
                tool_name=tool_name,
                route_needed=route_needed,
                description=task.description,
                priority=index,
            )
        )
    time_windows = list(dict.fromkeys(
        task.time_window for task in tasks if task.time_window
    ))
    return plan.model_copy(
        update={
            "tasks": tasks,
            "time_windows": time_windows or plan.time_windows,
        }
    )
