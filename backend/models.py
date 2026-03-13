from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1200)


class ChatRequest(BaseModel):
    user_id: str | None = None
    language: Literal["english", "hinglish"] = "hinglish"
    message: str = Field(min_length=1, max_length=1200)
    history: list[ChatMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str
    safety_flags: list[str] = Field(default_factory=list)
    suggested_actions: list[str] = Field(default_factory=list)
    escalate: bool = False


class CheckInRequest(BaseModel):
    mood: int = Field(ge=1, le=10)
    stressors: list[str] = Field(default_factory=list, max_length=8)
    note: str | None = Field(default=None, max_length=600)
    language: Literal["english", "hinglish"] = "hinglish"


class CheckInResponse(BaseModel):
    summary: str
    plan: list[str]
    affirmation: str
    escalate: bool = False


class SafetyRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1200)


class SafetyResponse(BaseModel):
    risk_level: Literal["low", "medium", "high"]
    triggers: list[str]
    immediate_help: bool
    guidance: str


class Resource(BaseModel):
    id: str
    name: str
    mode: str
    contact: str
    language: str
    coverage: str
    cost: str
    hours: str
    notes: str
    tags: list[str]


class ResourceResponse(BaseModel):
    resources: list[Resource]


class CounsellorBookingRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    contact: str = Field(min_length=6, max_length=120)
    preferred_mode: Literal["video", "phone", "chat", "in-person"] = "video"
    language: Literal["english", "hindi", "hinglish", "multilingual"] = "english"
    preferred_date: str = Field(min_length=8, max_length=20)
    preferred_time: str = Field(min_length=3, max_length=20)
    city: str | None = Field(default=None, max_length=80)
    concern: str | None = Field(default=None, max_length=600)


class CounsellorBookingResponse(BaseModel):
    booking_id: str
    status: Literal["confirmed", "priority-support"]
    assigned_counsellor: str
    assigned_mode: str
    scheduled_at: str
    message: str
    urgent_help_recommended: bool = False
    urgent_message: str | None = None
