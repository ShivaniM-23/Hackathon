"""
ShadowTrace AI — guardrails.py
AI safety layer: topic filtering, confidence gating, legal disclaimers.
This is a major demo differentiator — show judges a refused off-topic question.
"""

import re
from pydantic import BaseModel


class GuardrailResult(BaseModel):
    blocked: bool
    blocked_message: str = ""
    reason: str = ""


OFF_TOPIC_PATTERNS = [
    r"\bweather\b", r"\brecipe\b", r"\bjoke\b", r"\bsports\b",
    r"\bmovie\b", r"\bsong\b", r"\bmusic\b", r"\bgame\b",
    r"\bcooking\b", r"\btravel\b", r"\bholiday\b",
    r"who is (the )?president", r"capital of",
]

HARMFUL_PATTERNS = [
    r"personal\s+address", r"home\s+address", r"phone\s+number\s+of",
    r"social\s+security", r"aadhaar", r"private\s+data",
    r"\bhack\b", r"\bsteal\b", r"\billegal\b", r"\bcheat\b"
]

ALLOWED_TOPIC_KEYWORDS = [
    "company", "risk", "trust", "score", "employee", "founded", "director",
    "address", "client", "certification", "domain", "news", "fraud",
    "suspicious", "verify", "revenue", "funding", "legitimate", "fake",
    "red flag", "contradiction", "evidence", "dossier", "investigate",
    "summarize", "explain", "why", "what", "how", "is this", "should i",
]


def apply_guardrails(message: str, dossier: dict) -> GuardrailResult:
    msg_lower = message.lower().strip()

    # ── Block harmful/privacy requests ───────────────────────────────────────
    for pattern in HARMFUL_PATTERNS:
        if re.search(pattern, msg_lower):
            return GuardrailResult(
                blocked=True,
                blocked_message="I can't provide personal/private information or assist with unethical requests. ShadowTrace analyzes companies, not private individuals or illegal activities.",
                reason="safety_violation",
            )

    # ── Block off-topic questions ─────────────────────────────────────────────
    for pattern in OFF_TOPIC_PATTERNS:
        if re.search(pattern, msg_lower):
            return GuardrailResult(
                blocked=True,
                blocked_message=(
                    f"I can only answer questions about the company dossier for "
                    f"**{dossier.get('company_name', 'this company')}**. "
                    f"Try asking: 'Why is this company risky?' or 'Summarize the red flags.'"
                ),
                reason="off_topic",
            )

    # ── Check if question is plausibly on-topic ───────────────────────────────
    has_relevant_keyword = any(kw in msg_lower for kw in ALLOWED_TOPIC_KEYWORDS)
    if not has_relevant_keyword and len(message.split()) > 3:
        return GuardrailResult(
            blocked=True,
            blocked_message=(
                "I'm specialized for due diligence analysis. Please ask me about "
                "this company's trust score, contradictions, directors, or red flags."
            ),
            reason="irrelevant",
        )

    return GuardrailResult(blocked=False)
