from __future__ import annotations

from typing import Any

import httpx

from backend.config import Settings

try:
    import vertexai
    from vertexai.generative_models import GenerativeModel
except Exception:  # pragma: no cover
    vertexai = None
    GenerativeModel = None


class WellnessAssistant:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.vertex_enabled = False
        self.gemini_api_enabled = False
        self.model: Any | None = None
        self.error: str | None = None

        if settings.use_vertex_ai:
            if not settings.gcp_project:
                self.error = "GOOGLE_CLOUD_PROJECT is missing."
            elif vertexai is None or GenerativeModel is None:
                self.error = "Vertex AI SDK import failed."
            else:
                try:
                    vertexai.init(project=settings.gcp_project, location=settings.gcp_location)
                    self.model = GenerativeModel(settings.vertex_model)
                    self.vertex_enabled = True
                except Exception as exc:  # pragma: no cover
                    self.error = f"Vertex AI init failed: {exc}"

        if not self.vertex_enabled and settings.gemini_api_key:
            self.gemini_api_enabled = True

    @property
    def engine_name(self) -> str:
        if self.vertex_enabled:
            return "vertex"
        if self.gemini_api_enabled:
            return "gemini-api"
        return "local"

    def generate_reply(
        self,
        message: str,
        history: list[dict[str, str]],
        language: str,
        safety_report: dict[str, Any],
    ) -> str:
        risk_level = str(safety_report.get("risk_level", "low"))
        if risk_level == "high":
            return (
                "I am really glad you shared this. Your safety matters more than anything right now. "
                "Please contact Tele-MANAS at 14416 or Kiran at 1800-599-0019 immediately. "
                "If you feel in immediate danger, call emergency services and stay with a trusted person."
            )

        if self.vertex_enabled:
            try:
                return self._generate_vertex_reply(message, history, language)
            except Exception as exc:
                self.error = f"Vertex runtime failed: {exc}"

        if self.gemini_api_enabled:
            try:
                return self._generate_gemini_api_reply(message, history, language)
            except Exception as exc:
                self.error = f"Gemini API runtime failed: {exc}"

        return self._generate_local_reply(message, language, risk_level)

    def generate_checkin_plan(
        self,
        mood: int,
        stressors: list[str],
        note: str | None,
        language: str,
        safety_report: dict[str, Any],
    ) -> dict[str, Any]:
        risk_level = str(safety_report.get("risk_level", "low"))

        if risk_level == "high":
            return {
                "summary": "Your check-in suggests acute emotional distress.",
                "plan": [
                    "Call Tele-MANAS (14416) or Kiran (1800-599-0019) now.",
                    "Move to a safe space and stay near a trusted person.",
                    "Avoid being alone until the intensity comes down.",
                ],
                "affirmation": "Asking for urgent support is a strong and brave step.",
            }

        stressor_text = ", ".join(stressors) if stressors else "general stress"

        if mood <= 3:
            summary = f"You seem to be having a very heavy day, especially around {stressor_text}."
            plan = [
                "Do a 60-second reset: inhale 4 sec, exhale 6 sec, repeat 8 rounds.",
                "Send one message to a trusted friend or mentor saying you need support.",
                "Pick one tiny task (5-10 min) and complete only that.",
            ]
        elif mood <= 6:
            summary = f"Your mood is in a vulnerable but manageable range, with stress around {stressor_text}."
            plan = [
                "Use a 25-minute focus sprint and keep phone away.",
                "Drink water and take a short walk before your next study block.",
                "Journal one worry and one action you can take today.",
            ]
        else:
            summary = f"You are currently doing reasonably okay despite pressure around {stressor_text}."
            plan = [
                "Keep momentum with 2 intentional breaks today.",
                "Check in with a friend who might be struggling too.",
                "Sleep hygiene: no doom-scrolling 30 minutes before bed.",
            ]

        if note:
            summary += " Thanks for sharing your note; your self-awareness is a protective strength."

        affirmation = (
            "Your feelings are valid. Small consistent steps can create real emotional recovery."
            if language == "english"
            else "Jo aap feel kar rahe ho wo valid hai. Chhote steps bhi strong recovery banate hain."
        )

        return {"summary": summary, "plan": plan, "affirmation": affirmation}

    def _generate_vertex_reply(
        self,
        message: str,
        history: list[dict[str, str]],
        language: str,
    ) -> str:
        assert self.model is not None

        style_hint = (
            "Use natural Hinglish, short empathetic lines, and practical guidance."
            if language == "hinglish"
            else "Use warm and clear English, concise and practical."
        )

        history_block = "\n".join([f"{item['role']}: {item['content']}" for item in history])

        prompt = f"""
You are SaathiMind, a confidential youth wellness companion for India.
Guidelines:
- Be empathetic, non-judgmental, and culturally sensitive.
- Do not diagnose or prescribe medication.
- Normalize help-seeking and reduce stigma.
- Give 2-4 practical micro-actions.
- Keep response under 140 words.
- End with one gentle follow-up question.
- {style_hint}

Conversation so far:
{history_block}

User message:
{message}
""".strip()

        response = self.model.generate_content(
            prompt,
            generation_config={"temperature": 0.6, "max_output_tokens": 280},
        )

        text = getattr(response, "text", "")
        return text.strip() if text else self._generate_local_reply(message, language, "low")

    def _generate_gemini_api_reply(
        self,
        message: str,
        history: list[dict[str, str]],
        language: str,
    ) -> str:
        style_hint = (
            "Use natural Hinglish, short empathetic lines, and practical guidance."
            if language == "hinglish"
            else "Use warm and clear English, concise and practical."
        )

        history_block = "\n".join([f"{item['role']}: {item['content']}" for item in history])

        prompt = f"""
You are SaathiMind, a confidential youth wellness companion for India.
Guidelines:
- Be empathetic, non-judgmental, and culturally sensitive.
- Do not diagnose or prescribe medication.
- Normalize help-seeking and reduce stigma.
- Give 2-4 practical micro-actions.
- Keep response under 140 words.
- End with one gentle follow-up question.
- {style_hint}

Conversation so far:
{history_block}

User message:
{message}
""".strip()

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.settings.gemini_model}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.6, "maxOutputTokens": 280},
        }

        response = httpx.post(
            url,
            params={"key": self.settings.gemini_api_key},
            json=payload,
            timeout=20.0,
        )
        if response.status_code >= 400:
            snippet = response.text[:400]
            raise RuntimeError(f"Gemini API HTTP {response.status_code}: {snippet}")
        body = response.json()

        candidates = body.get("candidates", [])
        if not candidates:
            return self._generate_local_reply(message, language, "low")

        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join([str(item.get("text", "")) for item in parts]).strip()
        return text if text else self._generate_local_reply(message, language, "low")

    def _generate_local_reply(self, message: str, language: str, risk_level: str) -> str:
        msg = message.lower()

        if "exam" in msg or "study" in msg or "marks" in msg:
            core = (
                "It sounds like exam pressure is draining you, and that is very common among students. "
                "Try one 25-minute focused study sprint, then a 5-minute break. "
                "Write only 3 priority topics for today so your brain feels less overloaded."
            )
        elif "alone" in msg or "lonely" in msg or "no one" in msg:
            core = (
                "Feeling alone can feel very heavy, and sharing it here is a strong step. "
                "Can you reach out to one safe person with a simple message like, 'Can we talk for 10 mins?' "
                "Also, do one grounding action right now: feet on floor, slow breathing for 1 minute."
            )
        elif "family" in msg or "judge" in msg or "log kya" in msg:
            core = (
                "Fear of judgement is real, especially when mental health is treated as taboo. "
                "Your struggle does not make you weak; it makes you human. "
                "Try sharing one small feeling instead of everything at once with someone you trust."
            )
        elif "sleep" in msg or "tired" in msg or "burnout" in msg:
            core = (
                "Your body and mind both sound exhausted. "
                "For tonight, aim for a digital sunset: stop scrolling 30 minutes before sleep. "
                "Do a brief brain-dump list so worries are parked outside your head."
            )
        else:
            core = (
                "Thank you for opening up. What you are feeling matters. "
                "Let us take this one step at a time: name the top emotion, rate it 0-10, and choose one tiny action for the next 15 minutes."
            )

        follow_up = (
            "What feels hardest right now: thoughts, body stress, or people pressure?"
            if risk_level == "medium"
            else "Would you like a 2-minute grounding exercise or a practical plan for today?"
        )

        if language == "hinglish":
            return (
                "Main sun raha hoon, aur aap akela nahi ho. "
                + core
                + " "
                + "Aapke liye yeh manageable ban sakta hai. "
                + follow_up
            )

        return core + " " + follow_up
