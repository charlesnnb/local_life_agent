"""Structured inputs and outputs for the Local Life Agent MVP."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class LocationInput(BaseModel):
    lat: float | None = None
    lng: float | None = None
    address: str | None = None


class PlanRequest(BaseModel):
    query: str = Field(min_length=1)
    location: LocationInput | None = None


class UserPreference(BaseModel):
    activity_types: list[str] = Field(
        default_factory=lambda: ["亲子乐园", "展览"]
    )
    max_travel_minutes: int = Field(default=30, ge=15, le=45)
    dining_preferences: list[str] = Field(
        default_factory=lambda: ["清淡健康", "亲子友好"]
    )
    activity_intensity: Literal["light", "medium", "high"] = "light"
    budget_level: Literal["low", "medium", "high"] = "medium"
    prefer_indoor: bool = False
    prefer_low_wait: bool = True


class PreferenceWeights(BaseModel):
    distance_weight: float = Field(ge=0, le=1)
    activity_match_weight: float = Field(ge=0, le=1)
    child_friendly_weight: float = Field(ge=0, le=1)
    diet_match_weight: float = Field(ge=0, le=1)
    popularity_weight: float = Field(ge=0, le=1)
    budget_weight: float = Field(ge=0, le=1)
    indoor_weight: float = Field(ge=0, le=1)
    low_wait_weight: float = Field(ge=0, le=1)


class PreferenceProfile(BaseModel):
    preference: UserPreference
    weights: PreferenceWeights


class PreferenceSetup(BaseModel):
    options: dict[str, list[Any]]
    preference: UserPreference
    weights: PreferenceWeights


TaskType = Literal[
    "food_delivery",
    "poi_search",
    "restaurant_search",
    "hotel_search",
    "food_order",
    "activity_search",
    "restaurant_visit",
    "bar_visit",
    "route_stop",
    "message",
    "unknown",
]


class PlannedTask(BaseModel):
    task_id: str
    time_window: str
    task_type: TaskType
    target: str | None = None
    search_query: str | None = None
    tool_name: str = "unknown_tool"
    route_needed: bool = False
    description: str
    priority: int = 0
    companions: list[str] = Field(default_factory=list)
    child_age: int | None = None
    constraints: list[str] = Field(default_factory=list)


class UserTask(PlannedTask):
    """Backward-compatible name for the original multi-step task model."""


class TaskPlan(BaseModel):
    scene: str
    mood: str | None = None
    time_windows: list[str] = Field(default_factory=list)
    tasks: list[PlannedTask] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)


class ToolExecutionResult(BaseModel):
    task_id: str
    tool_name: str
    status: Literal["success", "failed"]
    selected_result: dict[str, Any] | None = None
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    rejected_candidates: list[dict[str, Any]] = Field(default_factory=list)
    message: str | None = None


class UserIntent(BaseModel):
    raw_query: str
    scene: Literal["family", "friends", "couple", "solo"]
    time_window: str
    time_windows: list[str] = Field(default_factory=list)
    tasks: list[PlannedTask] = Field(default_factory=list)
    duration_hours: list[float] = Field(min_length=2, max_length=2)
    companions: list[str]
    party_size: int
    child_age: int | None = None
    gender_mix: dict[str, int] | None = None
    distance_preference: Literal["nearby", "normal", "flexible"] = "normal"
    activity_preferences: list[str] = Field(default_factory=list)
    diet_preferences: list[str] = Field(default_factory=list)
    budget_preference: Literal["not_expensive", "normal", "flexible"] = "normal"
    avoid: list[str] = Field(default_factory=list)
    weather_constraint: Literal["rain", "snow", "hot", "cold"] | None = None
    city: str | None = None
    public_reasoning: str | None = None

    @property
    def max_distance_km(self) -> float:
        """Translate the semantic distance preference for the current mock tools."""
        return {
            "nearby": 8.0,
            "normal": 12.0,
            "flexible": 20.0,
        }[self.distance_preference]

    @property
    def duration_label(self) -> str:
        """Return a concise display label for the parsed duration range."""
        start, end = self.duration_hours
        if start == end:
            return f"{start:g}小时"
        return f"{start:g}-{end:g}小时"


class ResolvedLocation(BaseModel):
    location_id: str
    city: str
    district: str
    address: str
    lat: float
    lng: float
    source: Literal["request", "query", "demo_default"]


class RouteEstimate(BaseModel):
    distance_km: float
    duration_min: int = Field(ge=5, le=45)
    transport: str = "taxi"
    distance_meters: int = Field(default=0, ge=0)
    mode: str = "driving"
    source: str = "mock"
    polyline: list[list[float]] = Field(default_factory=list)


class RouteOrigin(BaseModel):
    name: str
    lat: float
    lng: float


class RouteStop(BaseModel):
    type: Literal["activity", "restaurant", "bar", "hotel"]
    category: str = "unknown"
    label: str = "活动"
    name: str
    lat: float
    lng: float
    estimated_travel_minutes: int = Field(ge=5, le=45)
    distance_km: float
    source: str = "mock"


class RoutePlan(BaseModel):
    origin: RouteOrigin
    stops: list[RouteStop]
    return_to_origin_minutes: int = Field(ge=0, le=45)
    total_travel_minutes: int = Field(ge=0, le=480)
    transport: str = "taxi"
    source: str = "mock"
    polyline: list[list[float]] = Field(default_factory=list)


class TimelineItem(BaseModel):
    time: str
    type: Literal[
        "departure",
        "activity",
        "transfer",
        "restaurant",
        "bar",
        "hotel",
        "food_order",
        "delivery",
        "break",
        "free_time",
        "return",
        "arrival",
    ]
    title: str
    description: str


class Timeline(BaseModel):
    items: list[TimelineItem]
    total_duration_minutes: int


class PlanStep(BaseModel):
    time: str
    action: str
    description: str
    place: str | None = None
    reason: str | None = None
    source: str | None = None


class ActivityPlan(BaseModel):
    summary: str
    steps: list[PlanStep]
    reasons: list[str]


class ActionResult(BaseModel):
    type: Literal["reservation", "send_message", "food_order"]
    target: str
    status: Literal["mock_success", "mock_failed"]
    message: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class MultiStepItinerary(BaseModel):
    plan: ActivityPlan
    route: RoutePlan
    timeline: Timeline
    actions: list[ActionResult]
    warnings: list[str] = Field(default_factory=list)


class PlanEvent(BaseModel):
    type: Literal["progress", "result", "error"]
    stage: Literal[
        "intent_parsing",
        "intent_parsed",
        "task_decomposition",
        "llm_task_planning_started",
        "llm_task_planning_finished",
        "tool_routing",
        "tool_execution",
        "itinerary_composing",
        "food_order_mock",
        "task_poi_search",
        "multistep_itinerary_building",
        "activity_search",
        "restaurant_search",
        "route_planning",
        "timeline_building",
        "reservation_mock",
        "message_generation",
        "llm_intent_started",
        "llm_intent_finished",
        "query_planning_started",
        "query_planning_finished",
        "amap_poi_search_started",
        "amap_poi_search_finished",
        "amap_restaurant_search_started",
        "amap_restaurant_search_finished",
        "amap_route_started",
        "amap_route_finished",
        "decision_explanation_started",
        "decision_explanation_finished",
        "final_composer_started",
        "final_composer_finished",
        "api_fallback_triggered",
        "exception_detected",
        "replan_search",
        "replan_pending",
        "completed",
        "failed",
    ]
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
    source: Literal["system", "deepseek", "amap", "mock"] = "system"


class QueryPlan(BaseModel):
    poi_queries: list[str] = Field(min_length=1, max_length=8)
    restaurant_queries: list[str] = Field(min_length=1, max_length=8)
    route_mode: Literal["driving", "walking"] = "driving"
    max_travel_minutes: int = Field(default=30, ge=5, le=60)
    public_reasoning: str


class RejectedReason(BaseModel):
    name: str
    reason: str


class DecisionExplanation(BaseModel):
    selected_reasons: list[str] = Field(default_factory=list)
    rejected_reasons: list[RejectedReason] = Field(default_factory=list)
    preference_explanation: list[str] = Field(default_factory=list)
    public_reasoning: str


class FinalComposition(BaseModel):
    summary: str
    timeline_explanation: str
    share_message: str


class RuntimeMode(BaseModel):
    mode: Literal["demo", "hybrid", "live"]
    llm: Literal["mock", "deepseek"]
    amap: Literal["mock", "amap"]
    actions: Literal["mock", "mock_fallback", "live"]


class PlanException(BaseModel):
    exception_id: str
    exception_type: str
    source_task_id: str | None = None
    severity: str
    title: str
    message: str
    impact: dict[str, Any] = Field(default_factory=dict)
    status: str = "detected"


class ReplanOption(BaseModel):
    option_id: str
    title: str
    description: str
    changes: list[str] = Field(default_factory=list)
    estimated_delay_minutes: int = 0
    estimated_saved_minutes: int = 0
    replacement_place: dict[str, Any] | None = None
    operation: Literal[
        "replace_restaurant",
        "replace_activity",
        "adjust_reservation",
        "keep_original",
    ]
    original_plan: dict[str, Any] = Field(default_factory=dict)
    proposed_plan: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReplanProposal(BaseModel):
    proposal_id: str
    exception: PlanException
    options: list[ReplanOption] = Field(default_factory=list)
    requires_consent: bool = True
    status: Literal["pending", "accepted", "kept"] = "pending"
    selected_option_id: str | None = None


class PlanResponse(BaseModel):
    user_intent: UserIntent
    task_plan: TaskPlan | None = None
    plan: ActivityPlan
    route: RoutePlan
    timeline: Timeline
    actions: list[ActionResult]
    preference_explanation: list[str] = Field(default_factory=list)
    decision_explanation: DecisionExplanation | None = None
    composition: FinalComposition | None = None
    planning_warnings: list[str] = Field(default_factory=list)
    exceptions: list[PlanException] = Field(default_factory=list)
    replan_proposals: list[ReplanProposal] = Field(default_factory=list)
    natural_language: str


class ReplanConfirmRequest(BaseModel):
    current_plan: PlanResponse
    proposal_id: str
    option_id: str
