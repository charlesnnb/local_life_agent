# Architecture and Data Boundaries

## Main Flow

```text
Natural language
→ intent parsing
→ ordered task planning
→ tool routing
→ POI / restaurant / food tools
→ itinerary composition
→ route + timeline + actions
→ exception detection and consent-based replan
```

`POST /api/plan` and `POST /api/plan/stream` both call
`PlannerAgent.run(...)`. Streaming is an observation layer, not a second
orchestrator.

## Responsibilities

- `src/agents/`: one planning entry point and the existing action executor
- `src/core/`: intent, task, ranking, itinerary, exception, and replan logic
- `src/providers/`: DeepSeek, AMap, and Mock commerce protocol boundaries
- `src/tools/`: POI, route, food, reservation, weather, and message capabilities
- `src/schemas/`: validated API and internal contracts
- `frontend/src/pages/`: planner and preference pages
- `frontend/src/components/`: reusable presentation components

## Provider Strategy

DeepSeek understands and structures tasks. Deterministic code validates all
structured output and owns facts, ordering, routes, time constraints, and
actions. DeepSeek failures fall back to rule parsing and rule task planning.

AMap supplies geocoding, place identity, and route estimates. AMap errors,
timeouts, rate limits, empty results, or invalid responses fall back to local
JSON candidates and offline route estimates.

Mock Local Commerce adds fields that AMap does not guarantee, including waiting
time, price, child suitability, dietary suitability, and reservation
availability.

## Runtime Modes

- Demo blocks external providers before any network request.
- Hybrid enables DeepSeek and AMap with short timeouts and keeps actions Mock.
- Live enables the same real data providers. Until a real action provider is
  implemented, action execution is explicitly labelled Mock fallback.

The startup command sets the authoritative `RUN_MODE`; the web page cannot
switch modes.

## Exception Consent

Restaurant full, activity unavailable, and schedule conflict use one proposal
contract and one frontend card. Detection never silently replaces the current
plan. The user must accept an option before route, timeline, actions, and share
message are updated.

## Persistence

The current preference profile is process memory only and resets when the
backend restarts. `localStorage` records that the questionnaire was completed;
`sessionStorage` records “稍后再说” only for the current browser session.

