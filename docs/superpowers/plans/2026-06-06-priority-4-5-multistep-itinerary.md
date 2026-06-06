# Priority 4.5 Multi-step Itinerary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add ordered multi-stage planning for food delivery, offline activities, and bar visits without regressing the existing activity-plus-restaurant flow.

**Architecture:** Extend the current Pydantic response contracts, add a deterministic task decomposer, and route only meaningful multi-stage requests through a focused itinerary builder inside the existing `PlannerAgent.run(...)`. Reuse current POI, route, provider fallback, callback, and response infrastructure; keep the current single-stage branch unchanged.

**Tech Stack:** Python 3.12, Pydantic, FastAPI, pytest, existing DeepSeek/AMap providers, React/Vite frontend.

---

## File Structure

- Create `src/core/task_decomposer.py`: deterministic clause and task extraction.
- Create `src/tools/food_order_tool.py`: Mock food-order action.
- Create `src/core/itinerary_builder.py`: multi-stage plan, route, timeline, actions, and message composition.
- Create `tests/test_multistep_itinerary.py`: Priority 4.5 acceptance and regression tests.
- Modify `src/schemas/models.py`: task, route, timeline, action, and event contracts.
- Modify `src/core/intent_parser.py`: expose all ordered time windows.
- Modify `src/core/llm_intent_parser.py`: keep tasks deterministic after LLM parsing.
- Modify `src/tools/poi_tool.py`: task-specific AMap search and deterministic fishing/bar fallback.
- Modify `src/tools/route_tool.py`: generic ordered offline-stop route assembly.
- Modify `src/tools/message_tool.py`: scene-aware targets and multi-step personal notes.
- Modify `src/agents/executor_agent.py`: reuse the scene-aware target for the old flow.
- Modify `src/agents/planner_agent.py`: branch to multi-step execution after intent decomposition.
- Modify `src/core/final_composer.py`: support multi-step place/action validation.
- Modify `README.md`: document Priority 4.5 and the new response behavior.

### Task 1: Ordered Task Schema And Decomposer

**Files:**
- Create: `tests/test_multistep_itinerary.py`
- Create: `src/core/task_decomposer.py`
- Modify: `src/schemas/models.py`
- Modify: `src/core/intent_parser.py`
- Modify: `src/core/llm_intent_parser.py`

- [ ] **Step 1: Write failing decomposer tests**

Add tests that call the public parser/decomposer APIs:

```python
from src.core.intent_parser import parse_intent
from src.core.task_decomposer import decompose_tasks


QUERY = (
    "今天工作完特别累，中午给我点个麦当劳，下午出去钓鱼，"
    "找个可以钓鱼的地方，晚上去酒吧"
)


def test_decomposer_preserves_ordered_multistage_tasks():
    intent = parse_intent(QUERY)
    tasks = decompose_tasks(QUERY, intent)

    assert [task.task_type for task in tasks] == [
        "food_order",
        "activity_search",
        "bar_visit",
    ]
    assert [task.time_window for task in tasks] == ["中午", "下午", "晚上"]
    assert tasks[0].target == "麦当劳"
    assert tasks[1].target == "钓鱼"
    assert tasks[2].target == "酒吧"


def test_parser_exposes_all_time_windows_and_tasks():
    intent = parse_intent(QUERY)

    assert intent.time_windows == ["中午", "下午", "晚上"]
    assert [task.task_type for task in intent.tasks] == [
        "food_order",
        "activity_search",
        "bar_visit",
    ]


def test_order_verb_keeps_food_brand_offline_route_semantics_out():
    intent = parse_intent("中午叫一份肯德基外卖")

    assert len(intent.tasks) == 1
    assert intent.tasks[0].task_type == "food_order"
    assert intent.tasks[0].target == "肯德基"
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
python -m pytest tests/test_multistep_itinerary.py -q
```

Expected: collection fails because `src.core.task_decomposer` and `UserTask` do not exist.

- [ ] **Step 3: Add task contracts**

In `src/schemas/models.py`, add:

```python
TaskType = Literal[
    "food_order",
    "activity_search",
    "restaurant_visit",
    "bar_visit",
    "route_stop",
    "message",
    "unknown",
]


class UserTask(BaseModel):
    task_id: str
    time_window: str
    task_type: TaskType
    target: str | None = None
    description: str
    priority: int = 0
```

Add to `UserIntent`:

```python
tasks: list[UserTask] = Field(default_factory=list)
time_windows: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Implement deterministic decomposition**

Create `src/core/task_decomposer.py` with:

```python
import re

from src.schemas.models import UserIntent, UserTask


TIME_WINDOWS = ("早上", "上午", "中午", "下午", "傍晚", "晚上", "周末")
ORDER_WORDS = ("点", "订", "外卖", "叫一份", "叫个", "来一份")
FOOD_BRANDS = ("麦当劳", "肯德基", "汉堡王", "必胜客")
ACTIVITIES = ("钓鱼", "打球", "看展", "citywalk", "逛街")
BAR_WORDS = ("酒吧", "清吧", "小酒馆")


def decompose_tasks(query: str, intent: UserIntent) -> list[UserTask]:
    clauses = [part.strip() for part in re.split(r"[，,。；;]", query) if part.strip()]
    tasks: list[UserTask] = []
    active_window = _first_window(query) or intent.time_window
    for clause in clauses:
        active_window = _first_window(clause) or active_window
        task = _task_from_clause(clause, active_window, len(tasks))
        if task and not _duplicates_previous(task, tasks):
            tasks.append(task)
    return tasks
```

Implement `_task_from_clause` so order words plus a known brand produce
`food_order`, activity words produce `activity_search`, and bar words produce
`bar_visit`. Use IDs `task_1`, `task_2`, and so on; set `priority` to source
order. Merge duplicate fishing clauses by task type, target, and time window.

- [ ] **Step 5: Attach deterministic tasks to both parser paths**

In `parse_intent`, first construct `UserIntent`, then import and call
`decompose_tasks`, assigning:

```python
intent.tasks = decompose_tasks(query, intent)
intent.time_windows = list(dict.fromkeys(
    task.time_window for task in intent.tasks if task.time_window
))
return intent
```

In `parse_intent_with_llm`, after Pydantic validation, overwrite LLM-provided
`tasks` and `time_windows` with the rule parser baseline so an LLM cannot change
task order or execution semantics.

- [ ] **Step 6: Run focused tests and verify GREEN**

Run:

```bash
python -m pytest tests/test_multistep_itinerary.py -q
python -m pytest tests/test_intent_parser.py tests/test_deepseek_fallback.py -q
```

Expected: new decomposition tests and existing parser/provider tests pass.

### Task 2: Food Order And Ordered Offline Itinerary Building

**Files:**
- Modify: `tests/test_multistep_itinerary.py`
- Create: `src/tools/food_order_tool.py`
- Create: `src/core/itinerary_builder.py`
- Modify: `src/schemas/models.py`
- Modify: `src/tools/poi_tool.py`
- Modify: `src/tools/route_tool.py`
- Modify: `data/pois.json`

- [ ] **Step 1: Write failing tool and builder tests**

Add:

```python
from src.core.itinerary_builder import build_multistep_itinerary
from src.services.location_service import resolve_location
from src.tools.food_order_tool import order_food


def test_food_order_returns_mock_action_without_route_stop():
    action = order_food("麦当劳", "中午", "默认位置：上海徐汇")

    assert action.type == "food_order"
    assert action.status == "mock_success"
    assert action.target == "麦当劳"
    assert action.details["estimated_delivery_minutes"] == 30


def test_multistep_builder_keeps_only_offline_tasks_in_route():
    intent = parse_intent(QUERY)
    result = build_multistep_itinerary(
        intent=intent,
        location=resolve_location(intent),
        selected_places=[
            {"task_id": "task_2", "task_type": "activity_search",
             "id": "mock_fishing_001", "name": "长风公园钓鱼池",
             "lat": 31.2244, "lng": 121.3957, "source": "mock"},
            {"task_id": "task_3", "task_type": "bar_visit",
             "id": "mock_bar_001", "name": "梧桐里清吧",
             "lat": 31.2110, "lng": 121.4380, "source": "mock"},
        ],
    )

    assert [stop.type for stop in result.route.stops] == ["activity", "bar"]
    assert all("麦当劳" not in stop.name for stop in result.route.stops)
    assert any(item.type == "food_order" for item in result.timeline.items)
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
python -m pytest tests/test_multistep_itinerary.py -q
```

Expected: imports fail because the food-order tool and itinerary builder do not
exist.

- [ ] **Step 3: Extend route, timeline, and action enums**

In `src/schemas/models.py`:

```python
class RouteStop(BaseModel):
    type: Literal["activity", "restaurant", "bar"]
    ...


class TimelineItem(BaseModel):
    type: Literal[
        "departure", "activity", "transfer", "restaurant", "bar",
        "food_order", "delivery", "break", "return", "arrival",
    ]
    ...


class ActionResult(BaseModel):
    type: Literal["reservation", "send_message", "food_order"]
    ...
```

Add a small container used internally:

```python
class MultiStepItinerary(BaseModel):
    plan: ActivityPlan
    route: RoutePlan
    timeline: Timeline
    actions: list[ActionResult]
```

- [ ] **Step 4: Implement the Mock food-order tool**

Create `src/tools/food_order_tool.py`:

```python
from src.schemas.models import ActionResult


def order_food(
    brand: str,
    time_window: str,
    location: str,
) -> ActionResult:
    minutes = 30
    return ActionResult(
        type="food_order",
        target=brand,
        status="mock_success",
        message=f"已模拟为你下单{brand}，预计 {minutes} 分钟送达",
        details={
            "tool_name": "food_order_tool",
            "action": "order_food",
            "brand": brand,
            "time_window": time_window,
            "location": location,
            "estimated_delivery_minutes": minutes,
        },
    )
```

- [ ] **Step 5: Add deterministic fishing and bar fallback POIs**

Add two `solo`-compatible entries to `data/pois.json`:

```json
{
  "poi_id": "poi_011",
  "name": "长风公园钓鱼池",
  "type": "钓鱼",
  "district": "普陀区",
  "lat": 31.2244,
  "lng": 121.3957,
  "tags": ["outdoor", "fishing", "relaxing"],
  "suitable_scenes": ["solo", "friends"],
  "age_range": [12, 99],
  "open_time": "08:00",
  "close_time": "18:00",
  "avg_duration_min": 120,
  "rating": 4.4,
  "price": 80,
  "indoor": false
}
```

and a `poi_012` clear-bar entry open through the evening. Update
`MOCK_WAIT_MINUTES` for both.

Add `search_task_pois(intent, location, task, amap_provider)` to
`src/tools/poi_tool.py`. It searches AMap with:

```python
{
    "钓鱼": ["钓鱼", "钓鱼场", "垂钓"],
    "酒吧": ["酒吧", "清吧", "小酒馆"],
}
```

The Mock path filters by tags/type and returns deterministic matching entries.

- [ ] **Step 6: Implement generic route assembly**

Add `build_ordered_route_plan(origin, places, legs, return_leg)` to
`src/tools/route_tool.py`. For each place, create a `RouteStop` whose type is
`bar` for `bar_visit`, otherwise `activity`. Preserve place order, merge
polylines, and compute total travel as all outbound legs plus return.

- [ ] **Step 7: Implement the multi-step itinerary builder**

Create `src/core/itinerary_builder.py` with:

```python
TIME_ANCHORS = {
    "早上": 8 * 60,
    "上午": 9 * 60 + 30,
    "中午": 12 * 60,
    "下午": 14 * 60 + 30,
    "傍晚": 18 * 60,
    "晚上": 19 * 60,
}
```

Expose:

```python
def build_multistep_itinerary(
    intent: UserIntent,
    location: ResolvedLocation,
    selected_places: list[dict],
    route_legs: list[RouteEstimate] | None = None,
    return_leg: RouteEstimate | None = None,
) -> MultiStepItinerary:
```

For `food_order`, create a 12:00 order item and 12:30 delivery item and call
`order_food`. For offline tasks, create transfer, arrival, activity/bar, and
optional break items at the task anchor. Build `PlanStep` entries from the same
schedule. Use `build_ordered_route_plan` for offline places only. Create an
empty-return-safe route with the resolved origin if no offline task exists.

- [ ] **Step 8: Run focused tests and verify GREEN**

Run:

```bash
python -m pytest tests/test_multistep_itinerary.py -q
python -m pytest tests/test_route_timeline.py -q
```

Expected: tool/builder tests pass and old route/timeline tests remain green.

### Task 3: Planner, Messaging, And Streaming Integration

**Files:**
- Modify: `tests/test_multistep_itinerary.py`
- Modify: `src/agents/planner_agent.py`
- Modify: `src/tools/message_tool.py`
- Modify: `src/agents/executor_agent.py`
- Modify: `src/core/final_composer.py`
- Modify: `src/schemas/models.py`

- [ ] **Step 1: Write failing end-to-end acceptance tests**

Add:

```python
from src.agents.planner_agent import PlannerAgent
from src.providers.amap_provider import AmapProvider
from src.providers.deepseek_provider import DeepSeekProvider


def _planner():
    return PlannerAgent(
        deepseek_provider=DeepSeekProvider(enabled=False),
        amap_provider=AmapProvider(enabled=False),
    )


def test_planner_returns_ordered_multistep_response():
    result = _planner().run(QUERY)

    assert [task.task_type for task in result.user_intent.tasks] == [
        "food_order", "activity_search", "bar_visit"
    ]
    timeline_text = " ".join(
        f"{item.time} {item.title} {item.description}"
        for item in result.timeline.items
    )
    assert timeline_text.index("麦当劳") < timeline_text.index("钓鱼")
    assert timeline_text.index("钓鱼") < timeline_text.index("酒吧")
    assert any(stop.type == "activity" for stop in result.route.stops)
    assert any(stop.type == "bar" for stop in result.route.stops)
    assert all("麦当劳" not in stop.name for stop in result.route.stops)
    assert any(action.type == "food_order" for action in result.actions)


def test_solo_multistep_message_is_a_personal_note():
    result = _planner().run(QUERY)
    message = next(
        action for action in result.actions if action.type == "send_message"
    )

    assert message.target == "自己"
    assert "老婆" not in (message.message or "")
    assert "家人" not in (message.message or "")
    assert "晚上去麦当劳吃晚餐" not in result.model_dump_json()


def test_multistep_run_emits_task_specific_progress():
    events = []
    _planner().run(QUERY, event_callback=events.append)
    stages = {event.stage for event in events}

    assert {
        "task_decomposition",
        "food_order_mock",
        "task_poi_search",
        "multistep_itinerary_building",
    } <= stages
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
python -m pytest tests/test_multistep_itinerary.py -q
```

Expected: planner still returns an activity plus restaurant and event schema
rejects new progress stages.

- [ ] **Step 3: Add progress stages**

Extend `PlanEvent.stage` with:

```python
"task_decomposition",
"food_order_mock",
"task_poi_search",
"multistep_itinerary_building",
```

- [ ] **Step 4: Add scene-aware message helpers**

In `src/tools/message_tool.py`, add:

```python
def message_target(scene: str) -> str:
    return {
        "family": "老婆/家人",
        "friends": "朋友",
        "couple": "同行人",
        "solo": "自己",
    }[scene]
```

Add `build_multistep_message(intent, plan)` that summarizes food order,
activity, and bar steps without claiming real payment or delivery. Update
`ExecutorAgent` to call `message_target(intent.scene)` in the old flow.

- [ ] **Step 5: Add the planner multi-step branch**

Immediately after intent parsing in `PlannerAgent.run`, emit task decomposition
events and use:

```python
if _is_multistep_intent(intent):
    return self._run_multistep(
        intent=intent,
        requested_location=requested_location,
        emit=emit,
        profile=profile,
    )
```

`_is_multistep_intent` returns true when there are at least two recognized
action tasks and either multiple time windows or multiple task types.

`_run_multistep` must:

1. Resolve the origin through the existing service.
2. Execute food orders and emit `food_order_mock`.
3. Search each offline task with `search_task_pois` and emit
   `task_poi_search`.
4. Choose the first deterministic candidate for each task.
5. Estimate ordered legs with the existing `estimate_route`.
6. Build route, timeline, plan, and actions through
   `build_multistep_itinerary`.
7. Add a `send_message` action targeting `message_target(intent.scene)`.
8. Build a `FinalComposition` and `natural_language` from the settled
   multi-step artifacts.
9. Emit `completed` and return the normal `PlanResponse`.

Do not call restaurant search, reservation, or the old `build_plan` path in
this branch.

- [ ] **Step 6: Make final copy validation action-agnostic**

Update `src/core/final_composer.py` so fallback route text says “按时间顺序安排”
for plans without a restaurant. Derive required places from all plan steps with
a place, not only `活动/晚餐`, and only require old start/dinner times when those
steps exist. Keep payment and reservation hallucination checks.

- [ ] **Step 7: Run focused integration tests and verify GREEN**

Run:

```bash
python -m pytest tests/test_multistep_itinerary.py -q
python -m pytest tests/test_demo_flow.py tests/test_streaming.py -q
```

Expected: all Priority 4.5 tests pass and the existing demo/streaming flow is
unchanged.

### Task 4: Documentation And Full Verification

**Files:**
- Modify: `README.md`
- Verify: all Python and frontend tests

- [ ] **Step 1: Document Priority 4.5**

Add a README section describing:

```text
自然语言
→ intent_parser
→ task_decomposer
→ ordered tasks
→ task-specific tools
→ itinerary_builder
→ route + timeline + actions + message
```

State that food delivery is Mock-only and excluded from route stops, while
offline activities and bar visits enter both route and timeline.

- [ ] **Step 2: Run required focused regression tests**

Run:

```bash
python -m pytest tests/test_multistep_itinerary.py -q
python -m pytest tests/test_intent_parser.py -q
python -m pytest tests/test_demo_flow.py -q
python -m pytest tests/test_route_timeline.py -q
python -m pytest tests/test_streaming.py -q
```

Expected: all pass.

- [ ] **Step 3: Run the full backend suite**

Run:

```bash
python -m pytest -q
```

Expected: all tests pass with no collection errors or warnings caused by the
new code.

- [ ] **Step 4: Build the frontend**

Run:

```bash
npm run build
```

Working directory: `frontend`

Expected: Vite production build succeeds.

- [ ] **Step 5: Inspect the final diff**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors. Confirm unrelated user changes remain present
and were not reverted.
