# chat.py — Anthropic API powered, deployment-ready
import httpx, os, re

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
API_URL = "https://api.anthropic.com/v1/messages"

async def chat_with_dossier(message: str, dossier: dict, confidence_threshold=0.6) -> dict:
    guard = _topic_guard(message, dossier)
    if guard:
        return guard

    context = _build_context(dossier)
    
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(API_URL, 
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-haiku-4-5-20251001",  # cheapest, fastest
                    "max_tokens": 300,
                    "system": f"""You are ShadowTrace AI, a due diligence analyst.
Answer ONLY using this company dossier. Never make up facts.
Cite your source. Keep answers under 3 sentences.
Add [Confidence: X/10] at the end.

DOSSIER:
{context}""",
                    "messages": [{"role": "user", "content": message}]
                }
            )
            data = resp.json()
            text = data["content"][0]["text"]
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
    """Compact context — keeps tokens low."""
    return f"""Company: {d.get('company_name')}
Score: {d.get('trust_score')}/100 — {d.get('risk_level')} RISK
Red flags: {'; '.join(d.get('red_flags', [])[:3])}
Contradictions: {len(d.get('contradictions', []))} found
Employees claimed: {d.get('extracted',{}).get('employee_count_claimed')}
Employees LinkedIn: {d.get('extracted',{}).get('employee_count_linkedin')}
Domain created: {d.get('extracted',{}).get('domain_created')}
Founded claimed: {d.get('extracted',{}).get('founding_year')}
Address: {d.get('extracted',{}).get('addresses',['Unknown'])[0] if d.get('extracted',{}).get('addresses') else 'Unknown'}"""


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
    """Fallback if API call fails."""
    msg = message.lower()
    name = dossier.get('company_name', 'This company')
    score = dossier.get('trust_score', 'N/A')
    risk = dossier.get('risk_level', 'UNKNOWN')
    flags = dossier.get('red_flags', [])

    if any(k in msg for k in ["risk","why","suspicious"]):
        return {"answer": f"{name} scored {score}/100 ({risk} risk). Top concern: {flags[0] if flags else 'no major issues detected'}.", "citations": [], "confidence": 0.8}
    if any(k in msg for k in ["red flag","problem","flag"]):
        return {"answer": "Red flags: " + (" | ".join(flags[:3]) if flags else "None detected."), "citations": [], "confidence": 0.85}
    if any(k in msg for k in ["summar","overview","tell me"]):
        return {"answer": f"{name}: {score}/100, {risk} risk. {len(dossier.get('contradictions',[]))} contradiction(s) found.", "citations": [], "confidence": 0.85}
    return {"answer": f"{name} has a trust score of {score}/100. Ask me about red flags, contradictions, or address.", "citations": [], "confidence": 0.7}