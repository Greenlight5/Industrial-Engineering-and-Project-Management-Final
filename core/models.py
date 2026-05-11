from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class OperatingHoursDay(BaseModel):
    start: str
    end: str


class OperatingHours(BaseModel):
    weekdays: str = ""          # e.g. "א-ה" or "Mon-Fri"
    weekday_start: str = ""     # "08:00"
    weekday_end: str = ""       # "20:00"
    friday: Optional[OperatingHoursDay] = None
    saturday: Optional[OperatingHoursDay] = None
    raw: str = ""               # Full human-readable description


class RequirementsModel(BaseModel):
    business_name: str
    business_goal: str
    bot_language: str           # "he", "en", "ar", etc.
    operating_hours: OperatingHours
    bot_objective: str
    services: List[str]
    routing_model: str          # "dedicated" or "shared"
    greeting_message: str
    out_of_hours_message: str
    additional_notes: Optional[str] = ""


class BotFlowModel(BaseModel):
    webhook_enabled: bool = False
    language: str
    name: str
    type: str = "tilebot"
    attributes: Dict[str, Any] = Field(default_factory=lambda: {"variables": {}})
    intents: List[Dict[str, Any]]
