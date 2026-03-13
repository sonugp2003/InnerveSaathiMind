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
        self.gemini_agent_name = settings.gemini_agent_name or "SaathiMind-Gemini-Agent"
        self.vertex_agent_name = "SaathiMind-Vertex-Agent"
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

    @property
    def active_agent(self) -> str:
        if self.gemini_api_enabled and self.settings.prefer_gemini_agent:
            return self.gemini_agent_name
        if self.vertex_enabled:
            return self.vertex_agent_name
        if self.gemini_api_enabled:
            return self.gemini_agent_name
        return "SaathiMind-Local-Fallback"

    def generate_reply(
        self,
        message: str,
        history: list[dict[str, str]],
        language: str,
        safety_report: dict[str, Any],
    ) -> str:
        risk_level = str(safety_report.get("risk_level", "low"))
        gemini_failed = False
        if risk_level == "high":
            return (
                "I am really glad you shared this. Your safety matters more than anything right now. "
                "Please contact Tele-MANAS at 14416 or Kiran at 1800-599-0019 immediately. "
                "If you feel in immediate danger, call emergency services and stay with a trusted person."
            )

        if self.settings.gemini_only_chat:
            if not self.gemini_api_enabled:
                self.error = "Gemini-only mode enabled but GEMINI_API_KEY is not configured."
                return self._gemini_unavailable_reply(language=language, missing_key=True)
            try:
                return self._generate_gemini_api_reply(message, history, language)
            except Exception as exc:
                self.error = f"Gemini API runtime failed: {exc}"
                return self._gemini_unavailable_reply(language=language)

        if self.gemini_api_enabled and self.settings.prefer_gemini_agent:
            try:
                return self._generate_gemini_api_reply(message, history, language)
            except Exception as exc:
                self.error = f"Gemini API runtime failed: {exc}"
                gemini_failed = True

        if self.vertex_enabled:
            try:
                return self._generate_vertex_reply(message, history, language)
            except Exception as exc:
                self.error = f"Vertex runtime failed: {exc}"

        if self.gemini_api_enabled and not gemini_failed:
            try:
                return self._generate_gemini_api_reply(message, history, language)
            except Exception as exc:
                self.error = f"Gemini API runtime failed: {exc}"

        return self._generate_local_reply(message, history, language, risk_level)

    def _gemini_unavailable_reply(self, language: str, missing_key: bool = False) -> str:
        if missing_key:
            return (
                "Gemini is not configured for chat right now. Please ask the admin to set GEMINI_API_KEY."
                if language == "english"
                else "Gemini abhi configure nahi hai. Please admin se bolo GEMINI_API_KEY set karein."
            )

        return (
            "I can respond only through Gemini right now, and Gemini is temporarily unavailable. Please try again in a minute."
            if language == "english"
            else "Main abhi sirf Gemini se reply karta hoon, aur Gemini temporary unavailable hai. Please 1 minute baad dobara try karo."
        )

    def _build_agent_prompt(
        self,
        *,
        message: str,
        history: list[dict[str, str]],
        language: str,
        agent_name: str,
    ) -> str:
        style_hint = (
            "Reply in natural Roman Hinglish (casual but respectful), like a caring friend in India."
            if language == "hinglish"
            else "Use warm natural English that sounds like a caring human."
        )

        history_block = "\n".join([f"{item['role']}: {item['content']}" for item in history])

        return f"""
You are {agent_name}, the conversational agent inside SaathiMind, a confidential youth wellness companion for India.
Guidelines:
- Be empathetic, non-judgmental, and culturally sensitive.
- Do not diagnose or prescribe medication.
- Normalize help-seeking and reduce stigma.
- Sound human, not scripted.
- Use 2-5 natural sentences.
- Offer 1-2 practical next steps (more only when necessary).
- Avoid repeating the user's exact words unless useful.
- Avoid repetitive canned openers like "I hear you" on every turn.
- Ask a follow-up question only when it genuinely helps.
- Keep continuity with the latest user context.
- Keep tone warm and simple, like a real person texting support.
- Never end mid-sentence; always complete the final thought naturally.
- Keep response under 170 words.
- {style_hint}

Conversation so far:
{history_block}

User message:
{message}
""".strip()

    def _clean_model_text(self, text: str) -> str:
        # Normalize spacing so model outputs render like a natural chat message.
        return re.sub(r"\s+", " ", text).strip()

    def _looks_incomplete(self, text: str) -> bool:
        value = self._clean_model_text(text)
        if not value:
            return True

        words = value.split()
        tail = value.lower()
        trailing_connectors = (
            "and",
            "or",
            "because",
            "like",
            "when",
            "if",
            "to",
            "but",
            "so",
            "that",
        )

        if value.endswith(("...", ",", ":", ";", "-")):
            return True
        if any(tail.endswith(f" {token}") or tail == token for token in trailing_connectors):
            return True
        if len(words) <= 8 and not re.search(r"[.!?]\s*$", value):
            return True
        if len(words) <= 24 and not re.search(r"[.!?]\s*$", value):
            return True
        if re.search(r"\b(a|an|the|my|your|our|their|to|for|with|of|in|on|at|from|that|this|these|those|feel|feels|feeling|been|being|quite|very|really)\s*$", tail):
            return True

        return False

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

        prompt = self._build_agent_prompt(
            message=message,
            history=history,
            language=language,
            agent_name=self.vertex_agent_name,
        )

        response = self.model.generate_content(
            prompt,
            generation_config={"temperature": 0.78, "max_output_tokens": 360},
        )

        text = self._clean_model_text(getattr(response, "text", ""))
        if not text or self._looks_incomplete(text):
            return self._generate_local_reply(message, history, language, "low")

        return text

    def _generate_gemini_api_reply(
        self,
        message: str,
        history: list[dict[str, str]],
        language: str,
    ) -> str:
        prompt = self._build_agent_prompt(
            message=message,
            history=history,
            language=language,
            agent_name=self.gemini_agent_name,
        )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.settings.gemini_model}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.78, "maxOutputTokens": 360},
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
            raise RuntimeError("Gemini API returned no candidates.")

        parts = candidates[0].get("content", {}).get("parts", [])
        text = self._clean_model_text("".join([str(item.get("text", "")) for item in parts]))
        if not text or self._looks_incomplete(text):
            raise RuntimeError("Gemini API returned empty or incomplete text.")

        return text

    def _generate_local_reply(
        self,
        message: str,
        history: list[dict[str, str]],
        language: str,
        risk_level: str,
    ) -> str:
        msg = re.sub(r"\s+", " ", message.lower()).strip()
        is_hinglish = language == "hinglish"
        word_count = len(msg.split())

        last_user_message = ""
        for item in reversed(history):
            if str(item.get("role", "")) != "user":
                continue
            text = str(item.get("content", "")).strip()
            if text:
                last_user_message = re.sub(r"\s+", " ", text.lower()).strip()
                break

        last_assistant_message = ""
        for item in reversed(history):
            if str(item.get("role", "")) != "assistant":
                continue
            text = str(item.get("content", "")).strip()
            if text:
                last_assistant_message = re.sub(r"\s+", " ", text.lower()).strip()
                break

        def pick_variant(seed_text: str, options: list[str]) -> str:
            if not options:
                return ""
            seed = seed_text or "seed"
            hash_value = 0
            for index, ch in enumerate(seed):
                hash_value = (hash_value + ord(ch) * (index + 1)) % 2147483647
            return options[hash_value % len(options)]

        def pick_non_repeating(seed_text: str, options: list[str]) -> str:
            if not options:
                return ""
            candidates = options
            if last_assistant_message:
                filtered = [option for option in options if option.lower() not in last_assistant_message]
                if filtered:
                    candidates = filtered
            return pick_variant(seed_text, candidates)

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
        is_brief_ack = bool(re.fullmatch(r"(ok|okay|hmm+|h|haan|han|yeah|yep|no|nah|k|theek|thik)", msg))
        is_emotion_label = bool(
            re.fullmatch(r"(mad|angry|sad|happy|anxious|stressed|worried|gussa|dukhi|khush)", msg)
        )
        has_emotion_word = bool(
            re.search(r"\b(mad|angry|sad|happy|anxious|stressed|worried|gussa|dukhi|khush)\b", msg)
        )
        is_action_request = bool(
            re.search(
                r"\b(what small step|small step|next step|what should i do|what do i do now|abhi kya karu|ab kya karu|kya karu|kya karoon)\b",
                msg,
            )
        )

        emotion_follow_up: str | None = None

        def infer_theme(text: str) -> str:
            if not text:
                return "general"
            if any(token in text for token in ["exam", "study", "marks"]):
                return "exam"
            if any(token in text for token in ["alone", "lonely", "no one"]):
                return "loneliness"
            if any(token in text for token in ["family", "judge", "log kya"]):
                return "stigma"
            if any(token in text for token in ["sleep", "tired", "burnout"]):
                return "sleep"
            return "general"

        theme = infer_theme(last_user_message)
        has_context = bool(last_user_message)

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
        elif is_emotion_label and msg in {"mad", "angry", "gussa"}:
            core = (
                "Thanks, aapne clearly emotion name kiya, that is strong self-awareness."
                if is_hinglish
                else "Thanks for naming that clearly. That is strong self-awareness."
            )
            emotion_follow_up = (
                pick_non_repeating(
                    msg + "|emad",
                    [
                        "Abhi body me sabse zyada tension kaha feel ho rahi hai: chest, shoulders, ya head?",
                        "Pehla tiny step: 30-second jaw aur shoulders relax karo. Kar paoge?",
                    ],
                )
                if is_hinglish
                else pick_non_repeating(
                    msg + "|emad",
                    [
                        "Where do you feel this anger most right now: chest, shoulders, or head?",
                        "First tiny step: relax your jaw and shoulders for 30 seconds. Can you try that now?",
                    ],
                )
            )
        elif is_emotion_label and msg in {"sad", "dukhi"}:
            core = (
                "Sad feel karna weakness nahi hai. Aapne honestly bola, that matters."
                if is_hinglish
                else "Feeling sad is not weakness. You named it honestly, and that matters."
            )
            emotion_follow_up = (
                pick_non_repeating(
                    msg + "|esad",
                    [
                        "Abhi ke liye ek gentle step choose karein: paani, face wash, ya 2-minute slow breathing?",
                        "Kya aap 1 supportive person ko simple text bhej sakte ho: 'thoda low feel kar raha/rahi hoon'?",
                    ],
                )
                if is_hinglish
                else pick_non_repeating(
                    msg + "|esad",
                    [
                        "For this moment, pick one gentle step: water, a quick face wash, or 2 minutes of slow breathing?",
                        "Can you send one simple text to a supportive person: 'I am feeling low right now'?",
                    ],
                )
            )
        elif is_emotion_label and msg in {"happy", "khush"}:
            core = (
                "Yeh sunke accha laga. Aapke mood me yeh lift important hai."
                if is_hinglish
                else "I am glad to hear that. This lift in your mood is important."
            )
            emotion_follow_up = (
                pick_non_repeating(
                    msg + "|ehappy",
                    [
                        "Aaj kya cheez helpful rahi? Usko repeatable routine bana sakte hain.",
                        "Is positive moment ko hold karne ke liye ek small win note kar lo.",
                    ],
                )
                if is_hinglish
                else pick_non_repeating(
                    msg + "|ehappy",
                    [
                        "What helped you feel this way today? We can make that repeatable.",
                        "To hold this positive moment, note one small win from today.",
                    ],
                )
            )
        elif is_emotion_label and msg in {"anxious", "stressed", "worried"}:
            core = (
                "Samajh gaya, anxiety/tension body ko jaldi overload kar deti hai."
                if is_hinglish
                else "Got it, anxiety can overload your body very quickly."
            )
            emotion_follow_up = (
                pick_non_repeating(
                    msg + "|eanx",
                    [
                        "Chalo 4 rounds karein: inhale 4 sec, exhale 6 sec. Bas itna hi.",
                        "Abhi ek hi kaam choose karo jo 10 minute me complete ho sake.",
                    ],
                )
                if is_hinglish
                else pick_non_repeating(
                    msg + "|eanx",
                    [
                        "Let us do 4 rounds now: inhale for 4 seconds, exhale for 6 seconds.",
                        "Pick just one task right now that can be finished in 10 minutes.",
                    ],
                )
            )
        elif is_short_number:
            core = (
                "Lagta hai aapne quick mood number share kiya. Accha kiya."
                if is_hinglish
                else "Looks like you shared a quick mood number. That helps."
            )
        elif is_brief_ack and has_context:
            core = (
                "Theek hai, hum aaram se chalenge. Agar chaaho to pehle ek chhota step decide karte hain."
                if is_hinglish
                else "That is okay, we can go slowly. If you want, we can choose one tiny next step first."
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
        elif is_action_request:
            core = (
                "Abhi ke liye ek simple 3-step karo: 1) 4 slow breaths, 2) thoda paani piyo, "
                "3) ek trusted person ko short message bhejo: 'thoda low feel kar raha/rahi hoon'."
                if is_hinglish
                else "Try this simple 3-step right now: 1) take 4 slow breaths, 2) drink some water, "
                "3) text one trusted person: 'I am feeling low and could use a quick check-in'."
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
                "Accha kiya jo aapne emotion identify kiya. Ab next 10-15 minutes ka ek tiny step choose karte hain."
                if is_hinglish and has_emotion_word
                else "Thanks for naming that emotion. Now let us pick one tiny step for the next 10-15 minutes."
                if has_emotion_word
                else "Chalo isse thoda manageable banate hain: abhi ke liye ek emotion ka naam do, "
                "phir next 10-15 minutes ka ek tiny step choose karo."
                if is_hinglish
                else "Let us make this feel manageable: name one emotion first, then choose one tiny "
                "step for the next 10-15 minutes."
            )
            core = f"{reflective_prefix} {action_prompt}"

        if word_count <= 3 and has_context and not is_emotion_label:
            if theme == "exam":
                core = (
                    "Samajh gaya. Exam pressure ka load lagatar feel ho raha hoga."
                    if is_hinglish
                    else "I hear you. The exam pressure probably feels nonstop right now."
                )
            elif theme == "loneliness":
                core = (
                    "Samajh raha hoon. Akelapan jab stretch hota hai to bahut draining lagta hai."
                    if is_hinglish
                    else "I hear you. Ongoing loneliness can feel deeply draining."
                )
            elif theme == "stigma":
                core = (
                    "Haan, judgement ka fear bahut real lagta hai. Aapka feel karna valid hai."
                    if is_hinglish
                    else "Yes, fear of judgement can feel very real. What you are feeling is valid."
                )

        ask_follow_up = (
            risk_level == "medium"
            or word_count <= 5
            or is_short_number
            or is_affection
            or is_brief_ack
        )
        if is_action_request:
            ask_follow_up = False
        if emotion_follow_up is not None:
            ask_follow_up = False

        if risk_level == "medium":
            follow_up = (
                pick_non_repeating(
                    msg + "|m",
                    [
                        "Abhi sabse tough kya lag raha hai: thoughts, body stress, ya people pressure?",
                        "Is waqt sabse heavy part kya hai: dimag ki racing, body tension, ya social pressure?",
                        "Agar chaaho, hum is moment ko 1 se 10 scale pe rate karke next step choose kar sakte hain.",
                    ],
                )
                if is_hinglish
                else pick_non_repeating(
                    msg + "|m",
                    [
                        "What feels hardest right now: racing thoughts, body stress, or people pressure?",
                        "What is most intense at this moment: thoughts, physical tension, or social pressure?",
                        "If you want, we can rate this moment from 1 to 10 and pick one clear next step.",
                    ],
                )
            )
        elif emotion_follow_up is not None:
            follow_up = emotion_follow_up
        elif ask_follow_up:
            follow_up = (
                pick_non_repeating(
                    msg + "|l",
                    [
                        "Ab next step ke liye kya easy lagega: 2-minute grounding ya chhota action plan?",
                        "Aap chaaho to hum abhi short grounding karein, ya seedha practical plan banayein.",
                        "Aap bol do, main abhi ek tiny plan bana deta hoon jo 10 minute me ho jaye.",
                    ],
                )
                if is_hinglish
                else pick_non_repeating(
                    msg + "|l",
                    [
                        "What would feel easier right now: a 2-minute grounding or a short action plan?",
                        "If you want, we can do a short grounding first or go straight to a practical plan.",
                        "Tell me and I can create a tiny 10-minute plan for right now.",
                    ],
                )
            )
        else:
            follow_up = (
                pick_non_repeating(
                    msg + "|l",
                    [
                        "Main yahin hoon, step by step chalte hain.",
                        "Hum isse dheere dheere handle kar lenge, aap akela nahi ho.",
                        "Jaldi nahi hai, hum calmly isko ek ek step me handle karte hain.",
                    ],
                )
                if is_hinglish
                else pick_non_repeating(
                    msg + "|l",
                    [
                        "I am here with you, and we can take this step by step.",
                        "You are not alone in this. We can handle it one step at a time.",
                        "There is no rush. We can handle this calmly, one small step at a time.",
                    ],
                )
            )

        return core + " " + follow_up
