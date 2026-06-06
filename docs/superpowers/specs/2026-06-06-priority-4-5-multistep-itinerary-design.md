# Priority 4.5 Multi-step Itinerary Design

## Goal

Add ordered, multi-stage planning for requests that contain multiple actions in
different time windows, while preserving the existing single activity plus
restaurant demo flow.

The acceptance query is:

```text
今天工作完特别累，中午给我点个麦当劳，下午出去钓鱼，找个可以钓鱼的地方，晚上去酒吧
```

It must produce three ordered tasks: lunch food delivery, an afternoon fishing
activity, and an evening bar visit.

## Architecture

The existing `PlannerAgent.run(...)` remains the only orchestration entry point.
After intent parsing, a rule-based task decomposer creates ordered `UserTask`
objects. The planner uses the multi-step path when the query contains at least
two actionable tasks across multiple stages. Other requests continue through
the existing activity, restaurant, route, reservation, and message flow.

The multi-step path reuses the existing location, POI, route, progress-event,
and response models where practical. It does not introduce another planner or
stream orchestrator.

## Data Model

`UserTask` contains:

- `task_id`
- `time_window`
- `task_type`
- `target`
- `description`
- `priority`

`UserIntent` gains `tasks` and `time_windows`. Task types cover food orders,
activity searches, restaurant visits, bar visits, route stops, messages, and
unknown tasks.

Route stop and timeline item type enums are extended for multi-step output.
`ActionResult` is extended to represent a mock food order. Existing serialized
fields remain compatible.

## Task Decomposition

`src/core/task_decomposer.py` applies deterministic rules to clauses in the raw
query. It recognizes explicit time windows and preserves source order.

- Order verbs such as `点`, `订`, `外卖`, and `叫一份` produce `food_order`.
- Activity terms such as `钓鱼`, `打球`, `看展`, `citywalk`, and `逛街`
  produce `activity_search`.
- `酒吧`, `清吧`, and `小酒馆` produce `bar_visit`.
- A food brand preceded by an order verb is never converted into an offline
  restaurant visit.

The decomposer runs after rule or LLM intent parsing so both provider paths
receive the same deterministic ordered tasks.

## Multi-step Execution

Food orders use a mock `food_order_tool`. The result appears in `actions` and
the timeline but never in route stops.

Activity and bar tasks use POI search with task-specific keywords. If AMap does
not return usable candidates, local mock POIs provide deterministic fallback
results. Selected offline places are connected in task order, starting from
the resolved origin and returning to the origin after the final stop.

`itinerary_builder` assigns fixed anchors for common windows and adds route
travel around those anchors. Timeline order is always based on ordered tasks:
midday, afternoon, then evening for the acceptance query. Only offline tasks
become route stops.

## Messaging

Message targets are scene-aware:

- family: `老婆/家人`
- friends: `朋友`
- couple: `同行人`
- solo: `自己`

Multi-step solo output is a personal plan note and must not claim it was sent
to a spouse or family member.

## Progress Events

The existing callback and SSE endpoints remain unchanged. The event schema is
extended with stages for task decomposition, food ordering, task-specific POI
search, and multi-step itinerary generation. No streaming-specific planner is
added.

## Error Handling

The rule decomposer is the reliable baseline and does not require an LLM.
External POI and route failures use existing fallback behavior. A missing
candidate for one offline task falls back to local mock data rather than
dropping that task from the itinerary.

The existing single-flow behavior remains the fallback for requests that do
not form a meaningful multi-stage task sequence.

## Testing

Add `tests/test_multistep_itinerary.py` before implementation. It verifies task
order, task targets, timeline order, route inclusion and exclusion, personal
messaging, and the absence of the incorrect evening McDonald's dinner.

Run focused multi-step tests first, then the existing intent, demo, route,
streaming, provider fallback, and preference tests. Finally run the full Python
suite and the frontend production build.
