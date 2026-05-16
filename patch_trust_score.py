import re

with open("backend/trust_score.py", "r", encoding="utf-8") as f:
    content = f.read()

new_content = """    # ── Total ─────────────────────────────────────────────────────────────────
    raw_score = sum(f.score for f in factors)
    
    # Apply AI score adjustment (based on reading actual content)
    ai_adjustment = dossier.get("score_adjustment", 0)
    
    final_score = max(0, min(100, raw_score - contradiction_penalty + ai_adjustment))

    # Also use AI's fraud and legitimacy signals for red flags
    ai_fraud_signals = dossier.get("fraud_signals", [])
    ai_legit_signals = dossier.get("legitimacy_signals", [])

    # Combine red flags: score-based + AI-detected
    red_flags = [f.reason for f in factors if f.is_red_flag] + ai_fraud_signals

    # Add contradiction-based red flags
    for c in dossier.get("contradictions", []):
        if c.get("severity") == "HIGH":
            claim = c.get("claimed") or c.get("claim") or c.get("field", "Claim")
            red_flags.append(f"Contradiction: {claim} - {c.get('evidence', 'conflicting evidence found')}")

    risk_level = (
        "LOW" if final_score >= 70
        else "MEDIUM" if final_score >= 40
        else "HIGH"
    )

    breakdown = {
        f.name: {
            "score": f.score,
            "max": f.max_points,
            "pct": round((f.score / f.max_points) * 100) if f.max_points else 0,
            "reason": f.reason,
            "is_red_flag": f.is_red_flag,
        }
        for f in factors
    }

    return {
        "score": final_score,
        "raw_score": raw_score,
        "contradiction_penalty": contradiction_penalty,
        "risk_level": risk_level,
        "breakdown": breakdown,
        "red_flags": red_flags[:10],  # Top 10 red flags
        "legitimacy_signals": ai_legit_signals,
        "legitimacy_verdict": dossier.get("legitimacy_verdict", "UNCERTAIN"),
        "ai_reasoning": dossier.get("ai_reasoning", ""),
        "factors": [
            {
                "name": f.name,
                "score": f.score,
                "max_points": f.max_points,
                "reason": f.reason,
                "is_red_flag": f.is_red_flag,
            }
            for f in factors
        ],
    }"""

content = re.sub(
    r'    # ── Total ─────────────────────────────────────────────────────────────────.*?        \],[\n\s]+}',
    new_content,
    content,
    flags=re.DOTALL
)

with open("backend/trust_score.py", "w", encoding="utf-8") as f:
    f.write(content)
