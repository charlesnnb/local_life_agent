# Task-Driven Planning Framework Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make LLM-planned ordered tasks drive tool execution and itinerary composition while preserving the existing API, SSE endpoint, and legacy demo fallback.

**Architecture:** Add one validated task-planning contract, one router that returns uniform tool results, and one composer that turns those results into the existing response models. `PlannerAgent` remains the only orchestration entry point and uses the fixed activity-plus-restaurant flow only when task planning cannot produce tasks.

**Tech Stack:** Python 3.11+, Pydantic 2, FastAPI, httpx, pytest, React, TypeScript, Vite

---

### Task 1: Lock the Task Planning Contract

**Files:**
- Modify: `src/schemas/models.py`
- Test: `tests/test_llm_task_planner.py`

- [ ] **Step 1: Write the failing schema and fallback tests**

Add tests that import `PlannedTask`, `TaskPlan`, and
`ToolExecutionResult`, then assert the sample query produces these ordered
types:

```python
assert [task.task_type for task in plan.tasks] == [
    "food_delivery",
    "poi_search",
    "poi_search",
    "hotel_search",
]
assert plan.tasks[0].route_needed is False
assert all(task.route_needed for task in plan.tasks[1:])
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `python -m pytest tests/test_llm_task_planner.py -q`

Expected: import or assertion failure because the new models and planner do not
exist.

- [ ] **Step 3: Add the shared models**

Define `PlannedTask`, `TaskPlan`, and `ToolExecutionResult`. Keep `UserTask` as
a compatibility subclass and type `UserIntent.tasks` as
`list[PlannedTask]`. Add `task_plan` and `planning_warnings` to
`PlanResponse`.

- [ ] **Step 4: Run the focused test**

Run: `python -m pytest tests/test_llm_task_planner.py -q`

Expected: schema imports pass; planner tests remain RED until Task 2.

### Task 2: Implement the LLM Task Planner and Rule Fallback

**Files:**
- Create: `src/core/llm_task_planner.py`
- Modify: `src/core/task_decomposer.py`
- Test: `tests/test_llm_task_planner.py`

- [ ] **Step 1: Add DeepSeek-first tests**

Use `httpx.MockTransport` to return a valid task-plan JSON object and assert:

```python
plan, used_llm, error = plan_tasks(query, intent, profile, provider)
assert used_llm is True
assert error is None
assert plan.tasks[0].tool_name == "food_order_tool"
```

Add invalid JSON coverage asserting the rule fallback returns all four sample
tasks.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_llm_task_planner.py -q`

Expected: missing planner function or wrong task decomposition.

- [ ] **Step 3: Implement strict JSON planning**

Create:

```python
def plan_tasks(
    query: str,
    intent: UserIntent,
    profile: PreferenceProfile,
    provider: DeepSeekProvider,
) -> tuple[TaskPlan, bool, str | None]:
    ...
```

Validate DeepSeek output with `TaskPlan.model_validate`. Normalize task IDs and
copy the original query into the prompt. On any provider or validation failure,
call `build_rule_task_plan`.

- [ ] **Step 4: Extend deterministic decomposition**

Recognize generic delivery foods, trampoline, fishing, bars, hotels, generic
outings, and meal intent. Generate task-specific search queries and tool names.
Preserve source order and inherited time windows.

- [ ] **Step 5: Verify GREEN**

Run: `python -m pytest tests/test_llm_task_planner.py -q`

Expected: all task planner tests pass.

### Task 3: Implement the Tool Router

**Files:**
- Create: `src/core/tool_router.py`
- Modify: `src/tools/poi_tool.py`
- Modify: `data/pois.json`
- Test: `tests/test_tool_router.py`

- [ ] **Step 1: Write routing and AMap-query tests**

Create a recording AMap provider and assert food delivery does not become a
route place, while the sample offline tasks issue searches containing
`蹦床馆`, `钓鱼`/`垂钓`, and `高档酒店`/`五星级酒店`/`酒店酒廊`.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_tool_router.py -q`

Expected: `ToolRouter` is missing.

- [ ] **Step 3: Implement router dispatch**

Expose:

```python
class ToolRouter:
    def execute(
        self,
        tasks: list[PlannedTask],
        intent: UserIntent,
        location: ResolvedLocation,
        event_callback: Callable[[PlanEvent], None] | None = None,
    ) -> list[ToolExecutionResult]:
        ...
```

Dispatch delivery, POI, hotel, bar, and restaurant tasks. Preserve every task
as one result, including failures.

- [ ] **Step 4: Make POI search task-driven**

Split `task.search_query` into ordered keywords and send each keyword to AMap.
Add local trampoline and hotel POIs so disabled/unavailable AMap still gives
deterministic task-specific candidates.

- [ ] **Step 5: Verify GREEN**

Run: `python -m pytest tests/test_tool_router.py -q`

Expected: all router tests pass.

### Task 4: Implement the Itinerary Composer

**Files:**
- Create: `src/core/itinerary_composer.py`
- Modify: `src/tools/route_tool.py`
- Modify: `src/schemas/models.py`
- Test: `tests/test_task_driven_planning.py`

- [ ] **Step 1: Write ordered composition tests**

Assert the sample result:

```python
assert "汉堡" not in " ".join(stop.name for stop in response.route.stops)
assert {"蹦床", "钓鱼", "酒店"} <= concepts_in_response
assert timeline_times == sorted(timeline_times)
assert response.planning_warnings
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_task_driven_planning.py -q`

Expected: the current planner drops trampoline/hotel and has no warnings.

- [ ] **Step 3: Compose route, timeline, actions, and warnings**

Map successful tool results by `task_id`, route only
`route_needed=True` selected places, and emit one timeline/plan entry for every
task. Mark hotel stops and timeline items as `hotel`. Add a low-energy warning
when multiple active tasks share the afternoon window.

- [ ] **Step 4: Verify GREEN at component level**

Run: `python -m pytest tests/test_task_driven_planning.py -q`

Expected: composer-level assertions pass once PlannerAgent is wired in Task 5.

### Task 5: Make Task-Driven Planning the PlannerAgent Primary Path

**Files:**
- Modify: `src/agents/planner_agent.py`
- Modify: `src/tools/message_tool.py`
- Test: `tests/test_task_driven_planning.py`
- Test: `tests/test_streaming.py`
- Test: `tests/test_demo_flow.py`

- [ ] **Step 1: Add planner and streaming assertions**

Assert the task plan is present, task-planning/tool-routing/composition events
are emitted, all four sample tasks survive, and the original family demo still
returns an activity, restaurant, reservation, message, route, and timeline.

- [ ] **Step 2: Verify RED**

Run:

```bash
python -m pytest tests/test_task_driven_planning.py tests/test_streaming.py tests/test_demo_flow.py -q
```

Expected: new task-driven assertions fail.

- [ ] **Step 3: Wire the primary pipeline**

After base intent parsing, call `plan_tasks`, assign ordered tasks to intent,
execute `ToolRouter`, and call `compose_itinerary`. Generate a task-aware
message and response. Continue into the existing fixed flow only when no
planner can produce tasks.

- [ ] **Step 4: Preserve progress compatibility**

Emit new stages:

```text
llm_task_planning_started
llm_task_planning_finished
tool_routing
tool_execution
itinerary_composing
```

Also emit existing activity, restaurant, route, timeline, food-order, and
task-POI stages where the corresponding task executes.

- [ ] **Step 5: Verify GREEN**

Run:

```bash
python -m pytest tests/test_task_driven_planning.py tests/test_streaming.py tests/test_demo_flow.py -q
```

Expected: all focused planner and compatibility tests pass.

### Task 6: Update Frontend Contracts and Warnings

**Files:**
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Timeline.tsx`

- [ ] **Step 1: Extend TypeScript models**

Add new task fields, task types, `task_plan`, `planning_warnings`, and hotel
route/timeline types.

- [ ] **Step 2: Render ordered tasks and warnings**

Show task descriptions in order and render a warning card when
`planning_warnings` is non-empty. Label hotel route stops and timeline items.

- [ ] **Step 3: Build frontend**

Run: `npm run build` in `frontend`

Expected: TypeScript and Vite build complete successfully.

### Task 7: Full Verification and Documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Run required focused suites**

```bash
python -m pytest tests/test_llm_task_planner.py -q
python -m pytest tests/test_tool_router.py -q
python -m pytest tests/test_task_driven_planning.py -q
```

- [ ] **Step 2: Run the full backend suite**

Run: `python -m pytest -q`

Expected: all tests pass.

- [ ] **Step 3: Build the frontend**

Run: `npm run build` in `frontend`

Expected: production build succeeds.

- [ ] **Step 4: Verify the sample response**

Run the planner with LLM and AMap disabled and inspect the structured result.
Confirm delivery is absent from route stops, trampoline/fishing/hotel remain
visible, task order is stable, and at least one warning explains the dense
afternoon.

- [ ] **Step 5: Update README**

Document the task-first architecture, provider fallback behavior, new tests,
and the fact that payments, real food ordering, and hotel booking remain mock
or out of scope.
