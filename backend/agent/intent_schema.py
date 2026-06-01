"""Pydantic schemas for structured intent parsing output.

These schemas define the output of DeepSeek LLM intent parsing.
Fields the user didn't specify MUST be null, never hardcoded defaults.
"""

from pydantic import BaseModel, Field
from typing import Optional


class ParsedIntent(BaseModel):
    """Structured extraction of user intent from natural language input.

    All optional fields should be None when the user didn't provide that info.
    No hardcoded defaults for user-supplied values.
    """

    city: Optional[str] = Field(
        default=None,
        description="City name extracted from user input, e.g. '北京', '上海'. Null if not mentioned.",
    )
    area: Optional[str] = Field(
        default=None,
        description="District/area within the city, e.g. '朝阳区', '浦东新区'. Null if not mentioned.",
    )
    date_or_time: Optional[str] = Field(
        default=None,
        description="Date or time mentioned, e.g. '周六下午', '6月15日', '下午2点'. Null if not mentioned.",
    )
    party_size: Optional[int] = Field(
        default=None,
        description="Number of people in the party. Null if not mentioned.",
    )
    budget_per_person: Optional[float] = Field(
        default=None,
        description="Budget per person in RMB. Null if not mentioned.",
    )

    scene: Optional[str] = Field(
        default=None,
        description="Scene type: 'family', 'friends', 'couple', 'solo', 'business'. Null if ambiguous.",
    )
    cuisine_preferences: Optional[list[str]] = Field(
        default=None,
        description="Preferred cuisine types, e.g. ['川菜', '日料', '火锅']. Empty list or null if not mentioned.",
    )
    dislikes_or_restrictions: Optional[list[str]] = Field(
        default=None,
        description="Dietary restrictions or dislikes, e.g. ['不吃辣', '素食']. Null if not mentioned.",
    )
    activity_after_meal: Optional[str] = Field(
        default=None,
        description="Activity preference after the meal, e.g. '逛街', '看电影', '喝咖啡'. Null if not mentioned.",
    )
    transport_preference: Optional[str] = Field(
        default=None,
        description="Transport preference: 'driving', 'taxi', 'transit', 'walking'. Null if not mentioned.",
    )
    indoor_preference: Optional[bool] = Field(
        default=None,
        description="True for indoor preference, False for outdoor, None if not specified.",
    )

    raw_user_input: str = Field(description="The original user input string.")
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score of the parsing result, 0.0 to 1.0.",
    )
    missing_fields: list[str] = Field(
        default_factory=list,
        description="List of field names that the user didn't provide (were set to null).",
    )
