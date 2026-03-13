from __future__ import annotations

import re

HIGH_RISK_KEYWORDS = {
    "suicide",
    "sucide",
    "suside",
    "suiside",
    "suicde",
    "suicidal",
    "kill myself",
    "end my life",
    "ending everything",
    "harm myself",
    "self harm",
    "die",
    "marna hai",
    "jeene ka mann nahi",
    "khatam karna hai",
    "want to disappear forever",
}

MEDIUM_RISK_KEYWORDS = {
    "hopeless",
    "worthless",
    "panic",
    "cant breathe",
    "can't breathe",
    "anxiety attack",
    "nobody understands",
    "alone",
    "empty",
    "burnout",
    "failure",
}

STIGMA_KEYWORDS = {
    "log kya kahenge",
    "people will judge",
    "shame",
    "embarrassed",
    "weak if i ask",
    "family will not understand",
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _find_matches(text: str, keywords: set[str]) -> list[str]:
    return sorted([keyword for keyword in keywords if keyword in text])


def _contains_high_risk_fuzzy(text: str) -> bool:
    # Catch common misspellings/variants of suicide intent phrases.
    return bool(
        re.search(
            r"\b(suicide|sucide|suside|suiside|suicde|suicidal|kill myself|end my life|harm myself|self harm)\b",
            text,
        )
    )


def assess_text(text: str) -> dict[str, object]:
    normalized = _normalize(text)

    high_matches = _find_matches(normalized, HIGH_RISK_KEYWORDS)
    if _contains_high_risk_fuzzy(normalized):
        if "suicide" not in high_matches:
            high_matches.append("suicide")
        high_matches = sorted(set(high_matches))
    medium_matches = _find_matches(normalized, MEDIUM_RISK_KEYWORDS)
    stigma_matches = _find_matches(normalized, STIGMA_KEYWORDS)

    if high_matches:
        risk_level = "high"
    elif medium_matches:
        risk_level = "medium"
    else:
        risk_level = "low"

    triggers = sorted(set(high_matches + medium_matches + stigma_matches))

    return {
        "risk_level": risk_level,
        "triggers": triggers,
        "immediate_help": risk_level == "high",
        "guidance": build_guidance(risk_level),
    }


def build_guidance(risk_level: str) -> str:
    if risk_level == "high":
        return (
            "You deserve immediate human support right now. Please contact Tele-MANAS (14416) or "
            "Kiran (1800-599-0019), or call local emergency services if you are in immediate danger."
        )
    if risk_level == "medium":
        return (
            "Your message shows high emotional strain. Consider grounding steps, reaching out to a trusted "
            "person, and connecting with a counselor soon."
        )
    return "No immediate crisis detected. Continue with supportive conversation and preventive care habits."
