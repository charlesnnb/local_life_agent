"""Deterministic ordered-task extraction for task-planner fallback."""

import re

from src.schemas.models import PlannedTask, UserIntent, UserTask


TIME_WINDOWS = ("早上", "上午", "中午", "下午", "傍晚", "晚上", "周末")
ORDER_WORDS = ("叫一份", "来一份", "叫个", "外卖", "点", "订")
FOOD_BRANDS = ("麦当劳", "肯德基", "汉堡王", "必胜客")
ACTIVITIES = ("钓鱼", "打球", "看展", "citywalk", "逛街")
BAR_WORDS = ("小酒馆", "清吧", "酒吧")
DELIVERY_TARGETS = (
    "麦当劳",
    "肯德基",
    "汉堡王",
    "必胜客",
    "汉堡",
    "披萨",
    "炸鸡",
    "咖啡",
    "奶茶",
    "午饭",
    "晚饭",
)
PLANNED_ACTIVITIES = (
    ("蹦床", "蹦床馆"),
    ("钓鱼", "钓鱼场 垂钓"),
    ("打球", "体育馆 球场"),
    ("看展", "展览 美术馆"),
    ("citywalk", "城市漫步 街区"),
    ("逛街", "商场 购物中心"),
)
HOTEL_WORDS = ("五星级酒店", "高档酒店", "酒店酒廊", "酒店")
RESTAURANT_WORDS = ("餐厅", "吃饭", "用餐", "晚餐", "午餐")


def decompose_tasks(query: str, intent: UserIntent) -> list[UserTask]:
    """Split a query into actionable tasks while preserving source order."""
    clauses = [
        part.strip()
        for part in re.split(r"[，,。；;]", query)
        if part.strip()
    ]
    tasks: list[UserTask] = []
    active_window = _first_window(query) or intent.time_window

    for clause in clauses:
        active_window = _first_window(clause) or active_window
        task = _task_from_clause(clause, active_window, len(tasks))
        if task is not None and not _duplicates_previous(task, tasks):
            tasks.append(task)

    return tasks


def decompose_planned_tasks(
    query: str,
    intent: UserIntent,
) -> list[PlannedTask]:
    """Create tool-ready tasks without selecting or inventing any place."""
    clauses = [
        part.strip()
        for part in re.split(r"[，,。；;]", query)
        if part.strip()
    ]
    tasks: list[PlannedTask] = []
    active_window = _first_window(query) or _period_only(intent.time_window)

    for clause in clauses:
        active_window = _first_window(clause) or active_window
        tasks.extend(
            _planned_tasks_from_clause(clause, active_window, len(tasks))
        )

    if not tasks and any(
        phrase in query for phrase in ("出去玩", "出去逛", "安排一下")
    ):
        tasks.append(_generic_activity_task(intent, active_window, len(tasks)))

    if (
        tasks
        and not any(task.task_type == "restaurant_search" for task in tasks)
        and _should_infer_meal(query, intent)
    ):
        meal_window = "晚上" if "下午" in active_window else active_window
        tasks.append(
            _planned_task(
                len(tasks),
                meal_window,
                "restaurant_search",
                "清淡餐厅" if intent.diet_preferences else "餐厅",
                "清淡 健康 餐厅" if intent.diet_preferences else "附近餐厅",
                "restaurant_tool",
                True,
                f"{meal_window}找一家合适的餐厅",
            )
        )

    return _deduplicate_planned_tasks(tasks)


def _task_from_clause(
    clause: str,
    time_window: str,
    task_index: int,
) -> UserTask | None:
    brand = _first_match(clause, FOOD_BRANDS)
    if brand and any(word in clause for word in ORDER_WORDS):
        return _task(
            task_index,
            time_window,
            "food_order",
            brand,
            clause,
        )

    activity = _first_match(clause.lower(), ACTIVITIES)
    if activity:
        target = "citywalk" if activity == "citywalk" else activity
        return _task(
            task_index,
            time_window,
            "activity_search",
            target,
            clause,
        )

    bar = _first_match(clause, BAR_WORDS)
    if bar:
        return _task(
            task_index,
            time_window,
            "bar_visit",
            "酒吧",
            clause,
        )
    return None


def _planned_tasks_from_clause(
    clause: str,
    time_window: str,
    start_index: int,
) -> list[PlannedTask]:
    tasks: list[PlannedTask] = []
    delivery = _first_match(clause, DELIVERY_TARGETS)
    if delivery and any(word in clause for word in ORDER_WORDS):
        tasks.append(
            _planned_task(
                start_index + len(tasks),
                time_window,
                "food_delivery",
                delivery,
                f"{delivery} 外卖",
                "food_order_tool",
                False,
                f"{time_window}点一份{delivery}",
            )
        )

    for target, search_query in PLANNED_ACTIVITIES:
        if target.lower() not in clause.lower():
            continue
        tasks.append(
            _planned_task(
                start_index + len(tasks),
                time_window,
                "poi_search",
                target,
                search_query,
                "amap_poi_tool",
                True,
                f"{time_window}找一个可以{target}的地方",
            )
        )

    hotel = _first_match(clause, HOTEL_WORDS)
    if hotel:
        tasks.append(
            _planned_task(
                start_index + len(tasks),
                time_window,
                "hotel_search",
                hotel,
                "高档酒店 五星级酒店 酒店酒廊",
                "amap_poi_tool",
                True,
                f"{time_window}去{hotel}放松",
            )
        )

    bar = _first_match(clause, BAR_WORDS)
    if bar:
        tasks.append(
            _planned_task(
                start_index + len(tasks),
                time_window,
                "bar_visit",
                "酒吧",
                "酒吧 清吧 小酒馆",
                "amap_poi_tool",
                True,
                f"{time_window}去酒吧放松",
            )
        )

    if (
        not tasks
        and any(word in clause for word in RESTAURANT_WORDS)
        and not any(word in clause for word in ORDER_WORDS)
    ):
        tasks.append(
            _planned_task(
                start_index,
                time_window,
                "restaurant_search",
                "餐厅",
                "附近餐厅",
                "restaurant_tool",
                True,
                f"{time_window}找一家餐厅用餐",
            )
        )

    if (
        not tasks
        and any(phrase in clause for phrase in ("出去玩", "出去逛"))
    ):
        tasks.append(
            _planned_task(
                start_index,
                time_window,
                "poi_search",
                "休闲活动",
                "休闲活动",
                "amap_poi_tool",
                True,
                f"{time_window}找一个适合放松的活动",
            )
        )
    return tasks


def _generic_activity_task(
    intent: UserIntent,
    time_window: str,
    index: int,
) -> PlannedTask:
    target = "亲子活动" if intent.scene == "family" else "休闲活动"
    query = "亲子乐园 室内活动" if intent.scene == "family" else "休闲活动"
    return _planned_task(
        index,
        time_window,
        "poi_search",
        target,
        query,
        "amap_poi_tool",
        True,
        f"{time_window}找一个{target}",
    )


def _planned_task(
    index: int,
    time_window: str,
    task_type: str,
    target: str,
    search_query: str,
    tool_name: str,
    route_needed: bool,
    description: str,
) -> PlannedTask:
    return PlannedTask(
        task_id=f"task_{index + 1}",
        time_window=time_window or "未指定",
        task_type=task_type,
        target=target,
        search_query=search_query,
        tool_name=tool_name,
        route_needed=route_needed,
        description=description,
        priority=index,
    )


def _task(
    index: int,
    time_window: str,
    task_type: str,
    target: str,
    description: str,
) -> UserTask:
    return UserTask(
        task_id=f"task_{index + 1}",
        time_window=time_window,
        task_type=task_type,
        target=target,
        description=description,
        priority=index,
    )


def _first_window(text: str) -> str | None:
    matches = [
        (text.find(window), window)
        for window in TIME_WINDOWS
        if window in text
    ]
    return min(matches)[1] if matches else None


def _first_match(text: str, candidates: tuple[str, ...]) -> str | None:
    matches = [
        (text.find(candidate), candidate)
        for candidate in candidates
        if candidate in text
    ]
    return min(matches)[1] if matches else None


def _period_only(value: str) -> str:
    return _first_window(value) or value or "未指定"


def _should_infer_meal(query: str, intent: UserIntent) -> bool:
    return bool(
        intent.scene in {"family", "friends", "couple"}
        and (
            intent.diet_preferences
            or any(word in query for word in ("半天", "几个小时"))
        )
    )


def _deduplicate_planned_tasks(
    tasks: list[PlannedTask],
) -> list[PlannedTask]:
    unique: list[PlannedTask] = []
    seen: set[tuple[str, str | None, str]] = set()
    for task in tasks:
        key = (task.task_type, task.target, task.time_window)
        if key in seen:
            continue
        seen.add(key)
        unique.append(
            task.model_copy(
                update={
                    "task_id": f"task_{len(unique) + 1}",
                    "priority": len(unique),
                }
            )
        )
    return unique


def _duplicates_previous(task: UserTask, tasks: list[UserTask]) -> bool:
    return any(
        previous.task_type == task.task_type
        and previous.target == task.target
        and previous.time_window == task.time_window
        for previous in tasks
    )
