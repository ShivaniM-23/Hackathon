# chat.py — Anthropic API powered, deployment-ready
import httpx, os, re
from dotenv import load_dotenv
load_dotenv()

GROQ_API_KEY = os.getenv("ANTHROPIC_API_KEY") # Note: using the same env var name you set
API_URL = "https://api.groq.com/openai/v1/chat/completions"

async def chat_with_dossier(message: str, dossier: dict, confidence_threshold=0.6) -> dict:
    guard = _topic_guard(message, dossier)
    if guard:
        return guard

    context = _build_context(dossier)

    if not GROQ_API_KEY:
        return template_answer(message, dossier)
    
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(API_URL, 
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": [
                        {
                            "role": "system", 
                            "content": f"You are ShadowTrace AI, a due diligence analyst.\nAnswer ONLY using this company dossier. Never make up facts.\nCite your source. Give detailed, structured answers when the user asks for detail.\nAdd [Confidence: X/10] at the end.\n\nDOSSIER:\n{context}"
                        },
                        {"role": "user", "content": message}
                    ]
                }
            )
            if resp.status_code >= 400:
                print(f"API Error: {resp.status_code} - {resp.text}")
                return template_answer(message, dossier)
            data = resp.json()
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not text:
                return template_answer(message, dossier)
            confidence = _extract_confidence(text)
            answer = re.sub(r"\[Confidence:.*?\]", "", text).strip()
            
            if confidence < confidence_threshold:
                answer = "Insufficient data to assess this reliably."
            
            return {
                "answer": answer,
                "citations": _extract_citations(answer),
                "confidence": confidence,
                "disclaimer": "AI-generated analysis. Verify independently."
            }
    except Exception:
        return template_answer(message, dossier)


def _build_context(d: dict) -> str:
    """Detailed but bounded context for dossier-grounded answers."""
    breakdown = d.get("score_breakdown", {}) or {}
    factors = [
        f"- {key}: {value.get('score')}/{value.get('max')} - {value.get('reason')}"
        for key, value in breakdown.items()
    ]
    contradictions = [
        f"- {c.get('field')}: claimed {c.get('claimed')} | evidence {c.get('evidence')} | severity {c.get('severity')}"
        for c in (d.get("contradictions", []) or [])[:8]
    ]
    reviews = d.get("reviews", {}) or {}
    raw_summary = d.get("raw_data_summary", {}) or {}
    return f"""Company: {d.get('company_name')}
Score: {d.get('trust_score')}/100 — {d.get('risk_level')} RISK
Red flags: {'; '.join(d.get('red_flags', [])[:8])}
Contradictions: {len(d.get('contradictions', []))} found
Contradiction details:
{chr(10).join(contradictions) if contradictions else '- None detected'}
Score factors:
{chr(10).join(factors) if factors else '- Score breakdown unavailable'}
Employees claimed: {d.get('extracted',{}).get('employee_count_claimed')}
Employees LinkedIn: {d.get('extracted',{}).get('employee_count_linkedin')}
Domain created: {d.get('extracted',{}).get('domain_created')}
Founded claimed: {d.get('extracted',{}).get('founding_year')}
Address: {d.get('extracted',{}).get('addresses',['Unknown'])[0] if d.get('extracted',{}).get('addresses') else 'Unknown'}
Sources scraped: {', '.join(raw_summary.get('scraped_sources', [])) if raw_summary.get('scraped_sources') else 'Unknown'}
Pages crawled: {raw_summary.get('pages_scraped', 'Unknown')}
Reviews: overall={reviews.get('overall_sentiment')}, reddit_mentions={reviews.get('reddit', {}).get('mentions')}, trustpilot={reviews.get('trustpilot', {}).get('rating')}, glassdoor={reviews.get('glassdoor', {}).get('rating')}"""


def _topic_guard(message: str, dossier: dict):
    off_topic = ["weather","recipe","joke","sports","movie","capital of","who is the president"]
    if any(kw in message.lower() for kw in off_topic):
        return {
            "answer": f"I only answer questions about {dossier.get('company_name','this company')}'s dossier. Try: 'Why is this risky?' or 'Summarise red flags.'",
            "citations": [], "confidence": 0.0, "guardrail_triggered": True
        }
    return None


def _extract_confidence(text: str) -> float:
    m = re.search(r"\[Confidence:\s*([\d.]+)/10\]", text)
    return float(m.group(1)) / 10 if m else 0.75


def _extract_citations(text: str) -> list:
    sources = re.findall(r"(?:based on|according to|from)\s+([A-Z][^,.]{2,30})", text, re.I)
    return [{"source": s.strip()} for s in sources[:2]]


def template_answer(message: str, dossier: dict) -> dict:
    """Detailed deterministic fallback if the hosted LLM is unavailable."""
    msg = message.lower()
    name = dossier.get('company_name', 'This company')
    score = dossier.get('trust_score', 'N/A')
    risk = dossier.get('risk_level', 'UNKNOWN')
    flags = dossier.get('red_flags', [])
    contradictions = dossier.get("contradictions", []) or []
    breakdown = dossier.get("score_breakdown", {}) or {}
    reviews = dossier.get("reviews", {}) or {}
    raw_summary = dossier.get("raw_data_summary", {}) or {}
    extracted = dossier.get("extracted", {}) or {}

    def factor_lines(limit: int = 8) -> str:
        if not breakdown:
            return "No score breakdown is available in the saved report."
        lines = []
        for key, value in list(breakdown.items())[:limit]:
            label = key.replace("_", " ")
            lines.append(f"{label}: {value.get('score')}/{value.get('max')} - {value.get('reason')}")
        return "\n".join(lines)

    def contradiction_lines() -> str:
        if not contradictions:
            return "No direct contradictions were detected between website claims and external evidence."
        return "\n".join(
            f"{c.get('field')}: claimed '{c.get('claimed')}', evidence '{c.get('evidence')}', severity {c.get('severity')}"
            for c in contradictions[:6]
        )

    def overview() -> str:
        red_flag_text = "\n".join(f"- {flag}" for flag in flags[:6]) if flags else "- No scoring red flags were recorded."
        return (
            f"{name} has a trust score of {score}/100 and is classified as {risk} risk.\n\n"
            f"Score breakdown:\n{factor_lines()}\n\n"
            f"Contradictions:\n{contradiction_lines()}\n\n"
            f"Red flags:\n{red_flag_text}\n\n"
            f"Evidence coverage: {raw_summary.get('pages_scraped', 'unknown')} pages crawled; "
            f"sources include {', '.join(raw_summary.get('scraped_sources', [])[:8]) if raw_summary.get('scraped_sources') else 'unknown'}."
        )

    if any(k in msg for k in ["risk","why","suspicious"]):
        return {"answer": overview(), "citations": [{"source": "score_breakdown"}, {"source": "contradictions"}], "confidence": 0.85}
    if any(k in msg for k in ["red flag","problem","flag"]):
        return {"answer": "Red flags:\n" + ("\n".join(f"- {flag}" for flag in flags[:8]) if flags else "None detected."), "citations": [{"source": "red_flags"}], "confidence": 0.9}
    if any(k in msg for k in ["score", "breakdown", "factor", "calculated"]):
        return {"answer": f"The score is {score}/100 ({risk} risk).\n\n{factor_lines()}", "citations": [{"source": "score_breakdown"}], "confidence": 0.9}
    if any(k in msg for k in ["contradiction", "mismatch", "conflict"]):
        return {"answer": contradiction_lines(), "citations": [{"source": "contradictions"}], "confidence": 0.9}
    if any(k in msg for k in ["address", "office", "location"]):
        addresses = extracted.get("addresses") or []
        answer = f"Addresses extracted: {', '.join(addresses) if addresses else 'none extracted from the crawl'}.\nAddress score: {breakdown.get('address_verification', {}).get('score', 'N/A')}/{breakdown.get('address_verification', {}).get('max', 'N/A')} - {breakdown.get('address_verification', {}).get('reason', 'No address factor available')}."
        return {"answer": answer, "citations": [{"source": "extracted"}, {"source": "score_breakdown"}], "confidence": 0.85}
    if any(k in msg for k in ["review", "sentiment", "reddit", "glassdoor", "trustpilot", "employee"]):
        answer = (
            f"Review sentiment: {reviews.get('overall_sentiment', 'NO_DATA')}.\n"
            f"Reddit mentions: {reviews.get('reddit', {}).get('mentions', 0)}; "
            f"negative Reddit posts: {len(reviews.get('reddit', {}).get('negative_posts', []))}.\n"
            f"Trustpilot rating: {reviews.get('trustpilot', {}).get('rating', 'not found')}; "
            f"Glassdoor rating: {reviews.get('glassdoor', {}).get('rating', 'not found')}.\n"
            f"Review score: {breakdown.get('review_sentiment', {}).get('score', 'N/A')}/{breakdown.get('review_sentiment', {}).get('max', 'N/A')} - {breakdown.get('review_sentiment', {}).get('reason', 'No review factor available')}."
        )
        return {"answer": answer, "citations": [{"source": "reviews"}, {"source": "score_breakdown"}], "confidence": 0.85}
    if any(k in msg for k in ["summar","overview","tell me"]):
        return {"answer": overview(), "citations": [{"source": "report"}], "confidence": 0.85}
    return {"answer": overview(), "citations": [{"source": "report"}], "confidence": 0.75}
