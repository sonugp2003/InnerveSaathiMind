from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import Settings
from backend.models import (
    ChatRequest,
    ChatResponse,
    CounsellorBookingRequest,
    CounsellorBookingResponse,
    CheckInRequest,
    CheckInResponse,
    ResourceResponse,
    SafetyRequest,
    SafetyResponse,
)
from backend.services.genai import WellnessAssistant
from backend.services.resources import ResourceStore
from backend.services.safety import assess_text

settings = Settings()
assistant = WellnessAssistant(settings)
resource_store = ResourceStore()

COUNSELLORS = [
    {
        "name": "Dr. Ananya Rao",
        "languages": {"english", "hindi", "hinglish", "multilingual"},
        "modes": {"video", "phone", "chat"},
        "city": "Bengaluru",
    },
    {
        "name": "Dr. Kabir Sharma",
        "languages": {"english", "hindi", "multilingual"},
        "modes": {"video", "phone", "in-person"},
        "city": "Delhi",
    },
    {
        "name": "Dr. Meera Iyer",
        "languages": {"english", "hinglish"},
        "modes": {"video", "chat"},
        "city": "Mumbai",
    },
]

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

root_dir = Path(__file__).resolve().parents[1]
frontend_dir = root_dir / "frontend"
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(frontend_dir / "index.html")


@app.get("/api/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "engine": assistant.engine_name,
        "vertex_enabled": assistant.vertex_enabled,
        "gemini_enabled": assistant.gemini_api_enabled,
        "gemini_model": settings.gemini_model,
        "vertex_model": settings.vertex_model,
        "fallback_reason": assistant.error,
    }


@app.post("/api/safety-screen", response_model=SafetyResponse)
def safety_screen(request: SafetyRequest) -> SafetyResponse:
    report = assess_text(request.text)
    return SafetyResponse(**report)


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    report = assess_text(request.message)
    history = [item.model_dump() for item in request.history[-settings.max_history_messages :]]

    reply = assistant.generate_reply(
        message=request.message,
        history=history,
        language=request.language,
        safety_report=report,
    )

    risk_level = str(report["risk_level"])
    if risk_level == "high":
        suggested_actions = [
            "Call Tele-MANAS (14416) now.",
            "Call Kiran (1800-599-0019) now.",
            "Stay with a trusted person and seek immediate local help.",
        ]
    elif risk_level == "medium":
        suggested_actions = [
            "Pause and do 1 minute of slow breathing.",
            "Reach out to one trusted contact today.",
            "Consider speaking with a counselor this week.",
        ]
    else:
        suggested_actions = [
            "Continue with a small actionable step.",
            "Track your mood with daily check-ins.",
            "Use peer or professional support early, not only in crisis.",
        ]

    return ChatResponse(
        reply=reply,
        safety_flags=report["triggers"],
        suggested_actions=suggested_actions,
        escalate=bool(report["immediate_help"]),
    )


@app.post("/api/check-in", response_model=CheckInResponse)
def checkin(request: CheckInRequest) -> CheckInResponse:
    aggregate_text = " ".join(request.stressors + [request.note or ""])
    report = assess_text(aggregate_text)

    plan = assistant.generate_checkin_plan(
        mood=request.mood,
        stressors=request.stressors,
        note=request.note,
        language=request.language,
        safety_report=report,
    )

    return CheckInResponse(
        summary=plan["summary"],
        plan=plan["plan"],
        affirmation=plan["affirmation"],
        escalate=bool(report["immediate_help"]),
    )


@app.get("/api/resources", response_model=ResourceResponse)
def resources(
    q: str | None = Query(default=None),
    mode: str | None = Query(default=None),
    language: str | None = Query(default=None),
) -> ResourceResponse:
    results = resource_store.search(query=q, mode=mode, language=language)
    return ResourceResponse(resources=results)


@app.post("/api/counsellor-booking", response_model=CounsellorBookingResponse)
def counsellor_booking(request: CounsellorBookingRequest) -> CounsellorBookingResponse:
    concern_text = request.concern or ""
    report = assess_text(concern_text)

    language = request.language
    mode = request.preferred_mode

    assigned = next(
        (
            item
            for item in COUNSELLORS
            if language in item["languages"] and mode in item["modes"]
        ),
        None,
    )
    if assigned is None:
        assigned = next((item for item in COUNSELLORS if mode in item["modes"]), COUNSELLORS[0])

    booking_id = f"SM-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    scheduled_at = f"{request.preferred_date} {request.preferred_time}"

    urgent_help_recommended = bool(report["immediate_help"])
    status = "priority-support" if urgent_help_recommended else "confirmed"
    if urgent_help_recommended:
        message = (
            "Your counsellor request is marked as priority. Please contact Tele-MANAS (14416) or "
            "Kiran (1800-599-0019) now while we line up support."
        )
    else:
        message = (
            f"Your session is booked with {assigned['name']}. Please keep your phone and email reachable "
            "for confirmation updates."
        )

    return CounsellorBookingResponse(
        booking_id=booking_id,
        status=status,
        assigned_counsellor=str(assigned["name"]),
        assigned_mode=request.preferred_mode,
        scheduled_at=scheduled_at,
        message=message,
        urgent_help_recommended=urgent_help_recommended,
        urgent_message=report["guidance"] if urgent_help_recommended else None,
    )
