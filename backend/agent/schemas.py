"""Pydantic schemas for the Agent system."""

from pydantic import BaseModel
from typing import Optional


class PlanRequest(BaseModel):
    user_id: str
    query: str


class IntentResult(BaseModel):
    intent: str = "short_activity_planning"
    scene: str  # "family" or "friends"
    need_execution: bool = True


class Constraint(BaseModel):
    scene: str
    start_time: str
    end_time: str
    duration_min: list[int]  # [min, max]
    max_distance_km: float
    child_age: int | None = None
    party_size: int
    preferences: list[str]
    must_include: list[str]
    optional_extra: list[str]
    transport: str = "taxi"
    weather: str = "sunny"


class PoiCandidate(BaseModel):
    poi: dict
    score: float = 0.0
    travel_from_home: dict | None = None


class RestaurantCandidate(BaseModel):
    restaurant: dict
    score: float = 0.0
    availability: dict | None = None


class ItineraryItem(BaseModel):
    time_start: str
    time_end: str
    type: str  # travel / activity / meal / extra / return
    title: str
    description: str
    location_id: str | None = None


class ToolCall(BaseModel):
    tool: str
    input: dict
    output: dict | None = None
    success: bool = False
    message: str = ""


class PlanResponse(BaseModel):
    status: str  # success / partial / failed
    scene: str
    summary: str
    constraints: dict
    planning_trace: list[dict]
    tool_calls: list[dict]
    itinerary: list[dict]
    completed_actions: list[dict]
    fallback_actions: list[dict]
    share_message: str
