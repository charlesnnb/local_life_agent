# Task-Driven Planning Framework Correction

## Goal

Replace the fixed activity-plus-restaurant planning path with a task-first
pipeline:

```text
query -> LLM task planner -> tool router -> tool results
      -> itinerary composer -> route / timeline / actions / message
```

The existing fixed demo flow remains available only when both the LLM task
planner and its rule fallback fail to produce usable tasks.

## Core Contract

`PlannedTask` is the shared contract between planning, routing, execution, and
composition. It carries the task's time window, type, target, search query,
tool name, route requirement, and user-facing description.

`ToolExecutionResult` is the only output contract from the tool router. Search
tools return a selected result plus candidates. Action tools return their mock
execution payload as the selected result. Failed tools return a message instead
of silently dropping the task.

`TaskPlan` contains scene, mood, ordered time windows, ordered tasks, and
constraints. The validated task list is copied to `UserIntent.tasks` for API
compatibility and frontend display.

## LLM Task Planner

`src/core/llm_task_planner.py` calls DeepSeek with a strict JSON prompt. The
model may classify and split tasks, choose tools, and decide route requirements,
but it may not invent POIs or execution results.

If DeepSeek is disabled, unavailable, returns invalid JSON, or returns no usable
tasks, the rule fallback produces the same `TaskPlan` schema. The fallback
recognizes delivery, named activities, generic outings, restaurants, bars, and
hotels. It preserves clause order and inherited time windows. It is a recovery
path, not a separate orchestration path.

## Tool Router

`src/core/tool_router.py` dispatches each task independently:

- `food_delivery` -> `food_order_tool`
- `poi_search`, `bar_visit`, `hotel_search` -> task-specific POI/AMap search
- `restaurant_search` -> existing restaurant search

Every offline result keeps its `task_id` and `task_type`. Only tasks with
`route_needed=true` and a successful selected place are passed to route
composition. Food delivery is represented as an action and timeline item but
never as a route stop.

AMap queries come directly from `PlannedTask.search_query`. The local data set
provides deterministic trampoline, fishing, bar, and hotel fallbacks for tests
and offline demos.

## Itinerary Composer

`src/core/itinerary_composer.py` consumes ordered tasks and tool results. It
does not decide which tools to call.

The composer:

- preserves task order and time-window anchors;
- adds delivery actions without route stops;
- routes all successful offline tasks in order;
- includes every requested task in the plan and timeline;
- records failed tasks and schedule pressure as `planning_warnings`;
- adds a warning and alternative guidance when multiple active afternoon tasks
  make a low-energy plan too dense.

Route and timeline types are extended for hotels. Existing activity,
restaurant, and bar rendering remains compatible.

## PlannerAgent

`PlannerAgent.run` keeps the existing API and SSE callback. Its primary path is:

1. Parse base intent and load preferences.
2. Plan ordered tasks with DeepSeek or the rule fallback.
3. Resolve location.
4. Execute tasks through `ToolRouter`.
5. Compose route, timeline, plan, actions, warnings, and message.
6. Return the existing `PlanResponse` shape plus task plan metadata and
   planning warnings.

The legacy fixed path stays in place only as a final compatibility fallback
when no task plan can be produced.

## Streaming

The existing SSE endpoint remains unchanged. New progress stages cover task
planning, tool routing, tool execution, and itinerary composition. Existing
stage aliases remain emitted where needed so the original demo and UI progress
tests continue to work.

## Frontend

The frontend shows ordered task chips and a warning panel. Timeline and route
labels support hotels. Existing actions, route, preferences, and streaming
components remain in place.

## Testing

Add:

- `tests/test_llm_task_planner.py`
- `tests/test_tool_router.py`
- `tests/test_task_driven_planning.py`

The tests cover DeepSeek preference, rule fallback, task-specific AMap calls,
delivery route exclusion, ordered timeline composition, conflict warnings,
task preservation, streaming stages, and legacy demo compatibility.

