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
