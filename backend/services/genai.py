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
            "Use natural Hinglish that sounds like a caring friend in India."
            if language == "hinglish"
            else "Use warm natural English that sounds like a caring human."
        )

        history_block = "\n".join([f"{item['role']}: {item['content']}" for item in history])

        prompt = f"""
You are SaathiMind, a confidential youth wellness companion for India.
Guidelines:
- Be empathetic, non-judgmental, and culturally sensitive.
- Do not diagnose or prescribe medication.
- Normalize help-seeking and reduce stigma.
- Sound human, not scripted.
- Use 2-5 natural sentences.
- Offer 1-2 practical next steps (more only when necessary).
- Avoid repeating the user's exact words unless useful.
- Ask a follow-up question only when it genuinely helps.
- Keep response under 170 words.
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
            "Use natural Hinglish that sounds like a caring friend in India."
            if language == "hinglish"
            else "Use warm natural English that sounds like a caring human."
        )

        history_block = "\n".join([f"{item['role']}: {item['content']}" for item in history])

        prompt = f"""
You are SaathiMind, a confidential youth wellness companion for India.
Guidelines:
- Be empathetic, non-judgmental, and culturally sensitive.
- Do not diagnose or prescribe medication.
- Normalize help-seeking and reduce stigma.
- Sound human, not scripted.
- Use 2-5 natural sentences.
- Offer 1-2 practical next steps (more only when necessary).
- Avoid repeating the user's exact words unless useful.
- Ask a follow-up question only when it genuinely helps.
- Keep response under 170 words.
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
        word_count = len(msg.split())

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
        is_affection = bool(re.search(r"\b(i love you|love u|luv u|love you)\b", msg))
        is_short_number = bool(re.fullmatch(r"\d{1,2}", msg))

        if is_greeting:
            core = (
                pick_variant(
                    msg,
                    [
                        "Hey, main yahin hoon. Aaram se bolo, main bina judge kiye sun raha hoon.",
                        "Namaste, aap safe space mein ho. Jo dil mein hai woh share kar sakte ho.",
                        "Hi, main SaathiMind hoon. Chalo dheere se start karte hain, aaj kaisa lag raha hai?",
                    ],
                )
                if is_hinglish
                else pick_variant(
                    msg,
                    [
                        "Hey, I am right here with you. You can share without being judged.",
                        "Hello, this is a safe space. We can take this one step at a time.",
                        "Hi, I am SaathiMind. Tell me what this day has felt like for you.",
                    ],
                )
            )
        elif is_identity_query:
            core = (
                "Main SaathiMind hoon. Main therapist ka replacement nahi hoon, lekin main aapko samajhkar "
                "practical next step nikalne mein help kar sakta hoon."
                if is_hinglish
                else "I am SaathiMind. I am not a replacement for therapy, but I can listen with care "
                "and help you choose a practical next step."
            )
        elif is_affection:
            core = (
                "Aww, thank you. Main yahan genuinely support karne ke liye hoon."
                if is_hinglish
                else "Thank you, that is kind. I am here to support you genuinely."
            )
        elif is_short_number:
            core = (
                "Lagta hai aapne quick mood number share kiya. Accha kiya."
                if is_hinglish
                else "Looks like you shared a quick mood number. That helps."
            )
        elif is_thanks:
            core = (
                "Aapne trust kiya, uske liye thank you. Hum aapke pace pe hi chalenge."
                if is_hinglish
                else "Thank you for trusting me with this. We can take this at your pace."
            )
        elif "exam" in msg or "study" in msg or "marks" in msg:
            core = (
                "Exam pressure bahut real hota hai, aur aap overreact nahi kar rahe. Aaj ke liye bas 3 priority "
                "topics choose karo, ek 25-minute focus sprint karo, phir 5-minute break lo."
                if is_hinglish
                else "Exam pressure can feel really heavy, and you are not overreacting. For today, pick just "
                "3 priorities, do one 25-minute focus sprint, then take a 5-minute break."
            )
        elif "alone" in msg or "lonely" in msg or "no one" in msg:
            core = (
                "Akelapan ka weight sach mein heavy hota hai, aur aapne share karke strong step liya hai. "
                "Agar theek lage, kisi safe person ko simple text bhejo: '10 min baat kar sakte ho?'"
                if is_hinglish
                else "Feeling alone can feel very heavy, and sharing this is a strong step. "
                "If it feels okay, text one safe person: 'Can we talk for 10 minutes?'"
            )
        elif "family" in msg or "judge" in msg or "log kya" in msg:
            core = (
                "Log kya kahenge ka pressure bahut real hota hai. Aap weak nahi ho. Agar safe lage, "
                "sab kuch ek saath bolne ke bajay ek chhoti feeling se start karo."
                if is_hinglish
                else "Fear of judgement is real, especially where mental health is stigmatized. "
                "Your struggle does not make you weak. If it feels safe, start by sharing one small feeling instead of everything at once."
            )
        elif "sleep" in msg or "tired" in msg or "burnout" in msg:
            core = (
                "Aap mentally aur physically dono drained lag rahe ho. Aaj raat ek gentle reset try karo: "
                "sleep se 30 min pehle phone side me rakho, aur worries ka quick brain-dump note bana do."
                if is_hinglish
                else "You sound mentally and physically drained. Try a gentle reset tonight: keep your phone away "
                "30 minutes before sleep, and do a quick brain-dump note to park worries."
            )
        else:
            reflective_prefix = (
                pick_variant(
                    msg,
                    [
                        "Main aapki baat dhyan se sun raha hoon.",
                        "Aap jo feel kar rahe ho, woh valid hai.",
                        "Yeh phase heavy lag sakta hai, aur aap akela nahi ho.",
                    ],
                )
                if is_hinglish
                else pick_variant(
                    msg,
                    [
                        "I am listening carefully to you.",
                        "What you are feeling is valid.",
                        "What you are carrying can feel really heavy.",
                    ],
                )
            )
            action_prompt = (
                "Chalo isse thoda manageable banate hain: abhi ke liye ek emotion ka naam do, "
                "phir next 10-15 minutes ka ek tiny step choose karo."
                if is_hinglish
                else "Let us make this feel manageable: name one emotion first, then choose one tiny "
                "step for the next 10-15 minutes."
            )
            core = f"{reflective_prefix} {action_prompt}"

        ask_follow_up = risk_level == "medium" or word_count <= 5 or is_short_number or is_affection
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
        elif ask_follow_up:
            follow_up = (
                pick_variant(
                    msg + "|l",
                    [
                        "Ab next step ke liye kya easy lagega: 2-minute grounding ya chhota action plan?",
                        "Aap chaaho to hum abhi short grounding karein, ya seedha practical plan banayein.",
                    ],
                )
                if is_hinglish
                else pick_variant(
                    msg + "|l",
                    [
                        "What would feel easier right now: a 2-minute grounding or a short action plan?",
                        "If you want, we can do a short grounding first or go straight to a practical plan.",
                    ],
                )
            )
        else:
            follow_up = (
                pick_variant(
                    msg + "|l",
                    [
                        "Main yahin hoon, step by step chalte hain.",
                        "Hum isse dheere dheere handle kar lenge, aap akela nahi ho.",
                    ],
                )
                if is_hinglish
                else pick_variant(
                    msg + "|l",
                    [
                        "I am here with you, and we can take this step by step.",
                        "You are not alone in this. We can handle it one step at a time.",
                    ],
                )
            )

        return core + " " + follow_up
