from __future__ import annotations

import re
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
        msg = re.sub(r"\s+", " ", message.lower()).strip()
        is_hinglish = language == "hinglish"
        compact_message = re.sub(r"\s+", " ", message).strip()[:110].replace('"', "'")

        def pick_variant(seed_text: str, options: list[str]) -> str:
            if not options:
                return ""
            seed = seed_text or "seed"
            hash_value = 0
            for index, ch in enumerate(seed):
                hash_value = (hash_value + ord(ch) * (index + 1)) % 2147483647
            return options[hash_value % len(options)]

        is_greeting = bool(re.search(r"\b(hi|hii|hello|hey|namaste)\b", msg)) and len(msg.split()) <= 5
        is_identity_query = bool(
            re.search(
                r"\b(who are you|what are you|your name|tum (kaun|kon) ho|aap (kaun|kon) ho|aapka naam|tumhara naam)\b",
                msg,
            )
        )
        is_thanks = bool(re.search(r"\b(thank you|thanks|thx|shukriya|dhanyavaad|dhanyavad)\b", msg))

        if is_greeting:
            core = (
                pick_variant(
                    msg,
                    [
                        "Hi, main SaathiMind hoon. Aap safe space mein ho.",
                        "Hey, main SaathiMind hoon. Bindaas share karo, no judgment.",
                        "Namaste, main SaathiMind hoon. Main aapki baat dhyan se sununga.",
                    ],
                )
                if is_hinglish
                else pick_variant(
                    msg,
                    [
                        "Hi, I am SaathiMind. You are in a safe and judgment-free space.",
                        "Hey, I am SaathiMind. You can share freely here without being judged.",
                        "Hello, I am SaathiMind. I am here to listen, not to judge.",
                    ],
                )
            )
        elif is_identity_query:
            core = (
                "Main SaathiMind hoon, ek empathetic wellness companion. Main diagnose nahi karta, "
                "par main aapko samajhne aur practical next step choose karne me help kar sakta hoon."
                if is_hinglish
                else "I am SaathiMind, an empathetic wellness companion. I do not diagnose, "
                "but I can help you unpack what you are feeling and choose a practical next step."
            )
        elif is_thanks:
            core = (
                "Aapne trust kiya, uske liye thank you. Yeh conversation aapke pace pe hi chalegi."
                if is_hinglish
                else "Thank you for trusting me with this. We can take this at your pace."
            )
        elif "exam" in msg or "study" in msg or "marks" in msg:
            core = (
                "Exam pressure heavy lagna bilkul common hai. Chalo overload kam karte hain: sirf 3 priority "
                "topics likho, phir 25-minute ka ek focused sprint karo, uske baad 5-minute break."
                if is_hinglish
                else "Exam pressure can feel really heavy, and that is very common. Let us reduce overload: "
                "write just 3 priority topics, do one 25-minute focused sprint, then take a 5-minute break."
            )
        elif "alone" in msg or "lonely" in msg or "no one" in msg:
            core = (
                "Akelapan ka weight bahut heavy lag sakta hai, aur aapne share karke strong step liya hai. "
                "Kya aap ek safe person ko simple message bhej sakte ho: '10 min baat kar sakte ho?'"
                if is_hinglish
                else "Feeling alone can feel very heavy, and sharing this is a strong step. "
                "Can you text one safe person with a simple message like, 'Can we talk for 10 minutes?'"
            )
        elif "family" in msg or "judge" in msg or "log kya" in msg:
            core = (
                "Log kya kahenge ka pressure real hota hai. Aap weak nahi ho. Agar safe lage, "
                "sab kuch ek saath bolne ke bajay ek chhoti feeling se start karo."
                if is_hinglish
                else "Fear of judgement is real, especially where mental health is stigmatized. "
                "Your struggle does not make you weak. If it feels safe, start by sharing one small feeling instead of everything at once."
            )
        elif "sleep" in msg or "tired" in msg or "burnout" in msg:
            core = (
                "Aap mentally aur physically dono tired lag rahe ho. Aaj raat ek simple reset try karo: "
                "sleep se 30 min pehle phone side me, aur worries ka quick brain-dump note bana do."
                if is_hinglish
                else "You sound mentally and physically exhausted. Try a simple reset tonight: keep your phone away "
                "30 minutes before sleep, and do a quick brain-dump note to park worries."
            )
        else:
            reflective_prefix = (
                pick_variant(
                    msg,
                    [
                        "Main aapki baat dhyan se sun raha hoon.",
                        "Aap jo feel kar rahe ho, woh valid hai.",
                        "Yeh jo chal raha hai, uska asar genuinely heavy ho sakta hai.",
                    ],
                )
                if is_hinglish
                else pick_variant(
                    msg,
                    [
                        "I am listening carefully to you.",
                        "What you are feeling is valid.",
                        "What you are carrying can genuinely feel heavy.",
                    ],
                )
            )
            action_prompt = (
                "Isko manageable banate hain: ek emotion name karo, 0-10 rate karo, "
                "aur next 15 minutes ke liye ek tiny action choose karo."
                if is_hinglish
                else "Let us make this manageable: name one emotion, rate it 0-10, "
                "and choose one tiny action for the next 15 minutes."
            )
            subject_line = f'Tumne bola "{compact_message}".' if is_hinglish else f'You said "{compact_message}".'
            core = f"{reflective_prefix} {subject_line} {action_prompt}"

        if risk_level == "medium":
            follow_up = (
                pick_variant(
                    msg + "|m",
                    [
                        "Abhi sabse tough kya lag raha hai: thoughts, body stress, ya people pressure?",
                        "Is waqt sabse heavy part kya hai: dimag ki racing, body tension, ya social pressure?",
                    ],
                )
                if is_hinglish
                else pick_variant(
                    msg + "|m",
                    [
                        "What feels hardest right now: racing thoughts, body stress, or people pressure?",
                        "What is most intense at this moment: thoughts, physical tension, or social pressure?",
                    ],
                )
            )
        else:
            follow_up = (
                pick_variant(
                    msg + "|l",
                    [
                        "Aap chaho to abhi 2-minute grounding karein ya practical plan banayein?",
                        "Next step ke liye aap kya choose karna chahoge: short grounding ya actionable plan?",
                    ],
                )
                if is_hinglish
                else pick_variant(
                    msg + "|l",
                    [
                        "Would you like a 2-minute grounding exercise or a practical plan for today?",
                        "For the next step, would you prefer a short grounding exercise or an actionable plan?",
                    ],
                )
            )

        return core + " " + follow_up
