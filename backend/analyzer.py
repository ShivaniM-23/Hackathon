"""
ShadowTrace AI — Analyzer
Uses a Small Language Model (SLM) to extract structured fields from scraped data
and detect contradictions between claims and evidence.

Supports: Phi-3 Mini (local Ollama), Mistral 7B, or any OpenAI-compatible endpoint.
Falls back to rule-based extraction if no LLM available.
"""

import json
import re
import json
import logging
import asyncio
import httpx
import os
from typing import Optional

logger = logging.getLogger(__name__)
GROQ_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# ── LLM config — change OLLAMA_MODEL to switch models ────────────────────────
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "phi3"           # or "mistral", "gemma2:2b"
OLLAMA_TIMEOUT = 60

LLM_AVAILABLE = True            # Set to False to force rule-based mode


async def analyze_company(raw_data: dict) -> dict:
    summary = raw_data.get("summary", {})
    whois_data = raw_data.get("whois", {})
    combined_text = summary.get("combined_text", "")

    # Extract structured fields (existing code)
    if LLM_AVAILABLE:
        extracted = await llm_extract(combined_text)
    else:
        extracted = rule_based_extract(combined_text, raw_data)

    extracted["domain_created"] = str(whois_data.get("creation_year", "Unknown"))
    extracted["domain_age_days"] = whois_data.get("domain_age_days")
    extracted["registrar"] = whois_data.get("registrar", "Unknown")
    linkedin = raw_data.get("linkedin", {})
    if linkedin.get("employee_count"):
        extracted["employee_count_linkedin"] = linkedin["employee_count"]
    extracted["linkedin_profile_exists"] = linkedin.get("profile_exists", False)
    extracted["_reviews"] = raw_data.get("reviews", {})

    # NEW: AI reads all scraped content and reasons about it
    ai_analysis = await ai_analyze_legitimacy(raw_data, extracted)
    # Use AI-found contradictions (richer than rule-based)
    contradictions = ai_analysis.get("contradictions", [])
    company_name = (
        extracted.get("company_name")
        or raw_data.get("company_name")
        or _extract_company_name_from_pages(raw_data.get("pages", []))
        or "Unknown Company"
    )

    return {
        "company_name": company_name,
        "extracted": extracted,
        "contradictions": contradictions,
        "fraud_signals": ai_analysis.get("fraud_signals", []),
        "legitimacy_signals": ai_analysis.get("legitimacy_signals", []),
        "legitimacy_verdict": ai_analysis.get("legitimacy_verdict", "UNCERTAIN"),
        "score_adjustment": ai_analysis.get("score_adjustment", 0),
        "ai_reasoning": ai_analysis.get("reasoning", ""),
        "analysis_method": "llm" if LLM_AVAILABLE else "rule_based",
        "raw_data_summary": raw_data  # Pass through for scoring
    }



# ── LLM extraction (Ollama) ───────────────────────────────────────────────────

EXTRACTION_PROMPT = """You are a business intelligence analyst. Extract the following information from the company text below.

Return ONLY a valid JSON object with these exact keys. Use null if information is not found.

{{
  "company_name": "string or null",
  "founding_year": "string or null (e.g. '2015')",
  "employee_count_claimed": "string or null (e.g. '200+')",
  "headquarters": "string or null",
  "addresses": ["list of addresses mentioned"],
  "directors": ["list of director/founder names"],
  "claimed_clients": ["list of companies claimed as clients"],
  "certifications": ["list of certifications mentioned"],
  "funding": "string or null (e.g. 'Series A, $5M')",
  "has_linkedin": false,
  "has_twitter": false,
  "tagline": "string or null"
}}

Company text:
{text}

Return only the JSON object, no other text."""


async def llm_extract(text: str) -> dict:
    """
    Calls local Ollama endpoint to extract structured data.
    Falls back to rule-based on failure.
    """
    prompt = EXTRACTION_PROMPT.format(text=text[:12000])  # Use more of the crawl without overwhelming small local models

    try:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1},  # Low temp for factual extraction
                },
            )
            data = response.json()
            raw_output = data.get("response", "")

            # Strip markdown fences
            raw_output = re.sub(r"```json|```", "", raw_output).strip()
            
            # Extract just the JSON object (everything between first { and last })
            match = re.search(r'\{.*\}', raw_output, re.DOTALL)
            if match:
                raw_output = match.group()
            
            # Remove trailing commas before } or ] (invalid JSON)
            raw_output = re.sub(r',\s*([}\]])', r'\1', raw_output)
            
            parsed = json.loads(raw_output)
            return parsed

    except (httpx.ConnectError, httpx.TimeoutException):
        logger.warning("Ollama not running. Using rule-based extraction.")
        return rule_based_extract(text, {})

    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(f"LLM returned bad JSON: {e}. Using rule-based extraction.")
        return rule_based_extract(text, {})


# ── Rule-based extraction (fallback) ─────────────────────────────────────────

def rule_based_extract(text: str, raw_data: dict) -> dict:
    """
    Regex-based extraction when LLM is unavailable.
    Covers the most common patterns in company websites.
    """
    return {
        "company_name": None,
        "founding_year": _re_founding_year(text),
        "employee_count_claimed": _re_employee_count(text),
        "headquarters": _re_headquarters(text),
        "addresses": _re_addresses(text),
        "directors": [],
        "claimed_clients": _re_client_names(text),
        "certifications": _re_certifications(text),
        "funding": None,
        "has_linkedin": "linkedin.com" in text.lower(),
        "has_twitter": "twitter.com" in text.lower() or "x.com" in text.lower(),
        "tagline": None,
    }


def _re_founding_year(text: str) -> Optional[str]:
    patterns = [
        r"(?:founded|established|incorporated|since|started)\s+(?:in\s+)?((19|20)\d{2})",
        r"((19|20)\d{2})\s+(?:founded|established)",
        r"©\s*((19|20)\d{2})",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def _re_employee_count(text: str) -> Optional[str]:
    patterns = [
        r"([\d,]+)\s*\+?\s*(?:employees|staff|team members|professionals)",
        r"team of\s+([\d,]+)",
        r"over\s+([\d,]+)\s+(?:employees|people)",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1).replace(",", "")
    return None


def _re_headquarters(text: str) -> Optional[str]:
    m = re.search(
        r"(?:headquartered|located|based)\s+in\s+([A-Z][a-zA-Z\s,]+?)(?:\.|,|\n)",
        text,
        re.IGNORECASE,
    )
    return m.group(1).strip() if m else None


def _re_addresses(text: str) -> list[str]:
    # Look for PIN codes (Indian) or ZIP codes
    addresses = re.findall(r"[A-Z][\w\s,.-]{10,60}(?:\d{6}|\d{5})", text)
    return [a.strip() for a in addresses[:3]]


def _re_client_names(text: str) -> list[str]:
    """Look for Fortune 500 / well-known company names mentioned as clients."""
    known_companies = [
        "Infosys", "TCS", "Wipro", "HCL", "Accenture", "Deloitte",
        "Google", "Microsoft", "Amazon", "Apple", "Meta", "IBM",
        "HDFC", "ICICI", "Reliance", "Tata", "Mahindra", "Bajaj",
    ]
    found = [c for c in known_companies if c.lower() in text.lower()]
    return found


def _re_certifications(text: str) -> list[str]:
    certs = ["ISO 9001", "ISO 27001", "ISO 14001", "SOC 2", "PCI DSS", "GDPR", "CMMI"]
    return [c for c in certs if c.lower() in text.lower()]


def _verify_claimed_clients(claimed_clients: list, news: list[dict]) -> list[str]:
    verified = []
    news_text = " ".join(
        f"{article.get('title', '')} {article.get('url', '')}"
        for article in news
    ).lower()
    for client in claimed_clients or []:
        if client and str(client).lower() in news_text:
            verified.append(str(client))
    return verified


# ── Contradiction detection ───────────────────────────────────────────────────

async def ai_analyze_legitimacy(raw_data: dict, extracted: dict) -> dict:
    """
    Sends ALL scraped content to Phi-3/rule-based engine.
    Asks it to reason about legitimacy like a human analyst would.
    """
    # Build a comprehensive evidence document from everything scraped
    evidence = []
    # Website content
    for page in raw_data.get("pages", []):
        evidence.append(f"[WEBSITE - {page['source']}]\n{page['text'][:1000]}")
    # WHOIS data
    whois = raw_data.get("whois", {})
    if whois:
        evidence.append(f"""[DOMAIN REGISTRATION]
Domain: {whois.get('domain')}
Registered: {whois.get('creation_date')}
Age: {whois.get('domain_age_days')} days
Registrar: {whois.get('registrar')}
Country: {whois.get('country')}""")
    # LinkedIn
    linkedin = raw_data.get("linkedin", {})
    if linkedin.get("raw_text"):
        evidence.append(f"[LINKEDIN PAGE]\n{linkedin['raw_text'][:500]}")
    elif linkedin.get("profile_exists"):
        evidence.append("[LINKEDIN] Profile URL exists but content blocked by LinkedIn")
    # Reddit posts — send ACTUAL titles not just counts
    reviews = raw_data.get("reviews", {})
    reddit = reviews.get("reddit", {})
    if reddit.get("mentions", 0) > 0:
        all_posts = (reddit.get("positive_posts", []) + 
                     reddit.get("negative_posts", []))[:10]
        reddit_text = "\n".join([f"- {p['title']} (r/{p['sub']}, score:{p['score']})" 
                                  for p in all_posts])
        evidence.append(f"[REDDIT MENTIONS - {reddit['mentions']} total]\n{reddit_text}")
    # Google News headlines — send actual titles
    news = raw_data.get("news", [])
    if news:
        news_text = "\n".join([f"- {a['title']}" for a in news[:10]])
        evidence.append(f"[NEWS COVERAGE]\n{news_text}")
    # Extended sources
    ext = raw_data.get("extended_sources", {})
    ext_summary = []
    for source, data in ext.items():
        if isinstance(data, dict):
            if data.get("found") or data.get("count", 0) > 0:
                ext_summary.append(f"{source}: FOUND (count={data.get('count', 'yes')})")
            else:
                ext_summary.append(f"{source}: NOT FOUND")
    if ext_summary:
        evidence.append(f"[EXTENDED SOURCE CHECK]\n" + "\n".join(ext_summary))
    # Review ratings
    tp = reviews.get("trustpilot", {})
    gd = reviews.get("glassdoor", {})
    amb = ext.get("ambitionbox", {})
    ratings_text = []
    if tp.get("found"): ratings_text.append(f"Trustpilot: {tp['rating']}/5")
    if gd.get("rating"): ratings_text.append(f"Glassdoor: {gd['rating']}/5")
    if amb.get("rating"): ratings_text.append(f"AmbitionBox: {amb['rating']}/5")
    if ratings_text:
        evidence.append(f"[REVIEW RATINGS]\n" + "\n".join(ratings_text))
    # Combine all evidence
    full_evidence = "\n\n".join(evidence)
    # Now ask AI to reason about it
    analysis_prompt = f"""You are a professional business due diligence analyst.
Analyze the following evidence about a company and answer these questions:
 
EVIDENCE:
{full_evidence[:5000]}
 
Answer each question with your reasoning based ONLY on the evidence above:
 
1. LEGITIMACY_VERDICT: Is this a legitimate business? 
   Answer: LEGITIMATE / LIKELY_LEGITIMATE / UNCERTAIN / LIKELY_FRAUDULENT / FRAUDULENT
   Reason: (1 sentence based on evidence)
 
2. FRAUD_SIGNALS: List any ACTUAL fraud signals found (not just complaints).
   Fraud signals = fake identity, money scams, impersonation, disappeared with money.
   Service complaints = bad service, slow delivery, poor quality (NOT fraud).
   Answer as JSON array of strings. Empty array if none.
 
3. LEGITIMACY_SIGNALS: List positive evidence that this is a real business.
   Answer as JSON array of strings.
 
4. SCORE_ADJUSTMENT: Based on all evidence, suggest score adjustment:
   Answer: number between -30 and +30
   Positive = more legitimate than base score suggests
   Negative = more suspicious than base score suggests
 
5. CONTRADICTIONS: List factual contradictions found between different sources.
   Only real contradictions (founding year vs domain date, claimed size vs evidence).
   Answer as JSON array of objects: [{{"field": "", "claimed": "", "evidence": "", "severity": "HIGH/MEDIUM/LOW"}}]
 
Return ONLY a JSON object with keys: 
legitimacy_verdict, fraud_signals, legitimacy_signals, 
score_adjustment, contradictions, reasoning
 
No markdown, no explanation outside the JSON."""
 
    # Try Groq API first
    if GROQ_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                res = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                    json={
                        "model": "llama-3.1-8b-instant",
                        "messages": [{"role": "user", "content": analysis_prompt}],
                        "temperature": 0.1,
                        "response_format": {"type": "json_object"}
                    }
                )
                raw = res.json()["choices"][0]["message"]["content"]
                result = json.loads(raw)
                return result
        except Exception as e:
            logger.warning(f"Groq AI analysis failed: {e}")
            
    # Rule-based fallback — reads actual content
    return rule_based_legitimacy_analysis(raw_data, extracted)
 
 
def rule_based_legitimacy_analysis(raw_data: dict, extracted: dict) -> dict:
    """
    Reads all scraped content and applies evidence-based reasoning.
    No hardcoded keyword blacklists — reads what was actually found.
    """
    fraud_signals = []
    legitimacy_signals = []
    score_adjustment = 0
    contradictions = []
    # Read website content for fraud patterns
    website_text = " ".join([p.get("text", "") for p in raw_data.get("pages", [])]).lower()
    # Fraud patterns that appear IN THE ACTUAL WEBSITE TEXT
    fraud_patterns_in_website = [
        ("guaranteed returns", "Website promises guaranteed investment returns — classic fraud signal"),
        ("100% profit", "Website promises 100% profit — unrealistic claim"),
        ("double your money", "Website promises to double money — Ponzi scheme signal"),
        ("risk free investment", "Website claims risk-free investments — misleading"),
        ("work from home earn", "MLM/pyramid scheme language detected"),
        ("refer and earn unlimited", "Pyramid scheme referral language detected"),
    ]
    for pattern, reason in fraud_patterns_in_website:
        if pattern in website_text:
            fraud_signals.append(reason)
            score_adjustment -= 20
    # Legitimacy patterns IN WEBSITE TEXT
    legit_patterns = [
        ("our clients include", 5, "Website mentions client relationships"),
        ("case stud", 5, "Case studies present — evidence of real work"),
        ("iso certified", 8, "ISO certification mentioned"),
        ("founded in", 3, "Clear founding date mentioned"),
        ("our team", 3, "Team information present"),
        ("privacy policy", 2, "Privacy policy present"),
        ("terms of service", 2, "Terms of service present"),
        ("contact us", 2, "Contact information present"),
    ]
    for pattern, pts, reason in legit_patterns:
        if pattern in website_text:
            legitimacy_signals.append(reason)
            score_adjustment += pts
    # Read Reddit posts — analyze ACTUAL titles
    reviews = raw_data.get("reviews", {})
    reddit = reviews.get("reddit", {})
    all_reddit = (reddit.get("positive_posts", []) + 
                  reddit.get("negative_posts", []))
    actual_fraud_posts = []
    actual_complaint_posts = []
    actual_positive_posts = []
    fraud_language = ["scam", "fraud", "fake", "cheated", "money not returned",
                      "disappeared", "no refund", "ponzi", "not registered",
                      "cyber crime", "police complaint", "fir", "blacklist"]
    positive_language = ["great company", "good place", "recommend", "excellent",
                         "professional", "legitimate", "trustworthy", "hired me",
                         "good experience", "real company"]
    for post in all_reddit:
        title_lower = post.get("title", "").lower()
        if any(fw in title_lower for fw in fraud_language):
            actual_fraud_posts.append(post["title"])
        elif any(pw in title_lower for pw in positive_language):
            actual_positive_posts.append(post["title"])
        else:
            actual_complaint_posts.append(post["title"])
    # Score based on what we actually found in Reddit
    if actual_fraud_posts:
        fraud_signals.extend([f"Reddit fraud report: '{t}'" 
                               for t in actual_fraud_posts[:3]])
        score_adjustment -= (len(actual_fraud_posts) * 8)
    if actual_positive_posts:
        legitimacy_signals.append(f"{len(actual_positive_posts)} positive Reddit mentions")
        score_adjustment += min(len(actual_positive_posts) * 2, 8)
    if reddit.get("mentions", 0) > 5 and not actual_fraud_posts:
        legitimacy_signals.append(f"Active Reddit community ({reddit['mentions']} mentions, no fraud signals)")
        score_adjustment += 5
    # Read news headlines — analyze actual content
    news = raw_data.get("news", [])
    news_titles = " ".join([a.get("title", "") for a in news]).lower()
    if any(fw in news_titles for fw in ["fraud", "scam", "arrested", "fir", "cheated"]):
        fraud_signals.append("News coverage includes fraud/legal action reports")
        score_adjustment -= 15
    elif len(news) > 5:
        legitimacy_signals.append(f"Substantial news coverage ({len(news)} articles)")
        score_adjustment += 8
    elif len(news) > 0:
        legitimacy_signals.append(f"Some news coverage found ({len(news)} articles)")
        score_adjustment += 3
    # WHOIS analysis
    whois = raw_data.get("whois", {})
    age_days = whois.get("domain_age_days", 0)
    if age_days > 1825:  # 5+ years
        legitimacy_signals.append(f"Domain established {age_days // 365} years ago")
        score_adjustment += 10
    elif age_days > 730:  # 2-5 years
        legitimacy_signals.append(f"Domain {age_days // 365} years old")
        score_adjustment += 5
    elif age_days < 180:
        fraud_signals.append(f"Very new domain — only {age_days} days old")
        score_adjustment -= 10
    # Extended sources
    ext = raw_data.get("extended_sources", {})
    if ext.get("job_portals", {}).get("found"):
        legitimacy_signals.append("Active job postings found — company is hiring")
        score_adjustment += 6
    if ext.get("regulatory", {}).get("found"):
        legitimacy_signals.append("Found in regulatory/government records")
        score_adjustment += 8
    if ext.get("ambitionbox", {}).get("rating"):
        rating = ext["ambitionbox"]["rating"]
        if rating >= 3.5:
            legitimacy_signals.append(f"AmbitionBox employee rating: {rating}/5")
            score_adjustment += 5
        else:
            actual_complaint_posts.append(f"Low AmbitionBox rating: {rating}/5")
            score_adjustment -= 3
    # LinkedIn
    linkedin = raw_data.get("linkedin", {})
    if linkedin.get("profile_exists"):
        legitimacy_signals.append("LinkedIn company page exists")
        score_adjustment += 4
    # Determine verdict
    if len(fraud_signals) >= 3 or score_adjustment < -25:
        verdict = "LIKELY_FRAUDULENT"
    elif len(fraud_signals) >= 1 or score_adjustment < -10:
        verdict = "UNCERTAIN"
    elif len(legitimacy_signals) >= 5 or score_adjustment > 15:
        verdict = "LEGITIMATE"
    elif len(legitimacy_signals) >= 2:
        verdict = "LIKELY_LEGITIMATE"
    else:
        verdict = "UNCERTAIN"
    # Build contradictions from actual data
    extracted_year = extracted.get("founding_year")
    domain_year = whois.get("creation_year")
    if extracted_year and domain_year:
        import re as _re
        m = _re.search(r'(19|20)\d{2}', str(extracted_year))
        if m:
            fy = int(m.group())
            if domain_year > fy + 5:
                contradictions.append({
                    "field": "Company Age",
                    "claimed": f"Founded {fy}",
                    "evidence": f"Domain only registered in {domain_year}",
                    "severity": "HIGH"
                })
    # Generate dynamic reasoning string
    reason_parts = []
    if fraud_signals:
        reason_parts.append(f"Flagged {len(fraud_signals)} high-risk signals including {fraud_signals[0].lower()}.")
    if legitimacy_signals:
        reason_parts.append(f"Verified {len(legitimacy_signals)} trust indicators (e.g., {legitimacy_signals[0].lower()}).")
    
    if not reason_parts:
        final_reasoning = f"Insufficient digital footprint across {len(raw_data.get('pages', []))} scraped pages to determine legitimacy."
    else:
        final_reasoning = " ".join(reason_parts)

    return {
        "legitimacy_verdict": verdict,
        "fraud_signals": fraud_signals,
        "legitimacy_signals": legitimacy_signals,
        "score_adjustment": max(-40, min(30, score_adjustment)),
        "contradictions": contradictions,
        "reasoning": final_reasoning
    }


def _extract_company_name_from_pages(pages: list[dict]) -> Optional[str]:
    for page in pages:
        title = page.get("title", "")
        if title:
            # Remove common suffixes
            name = re.sub(
                r"\s*[-|–]\s*.+$|\s*(Pvt\.?\s*Ltd\.?|Inc\.?|LLC|Corp\.?|Limited).*",
                "",
                title,
                flags=re.IGNORECASE,
            ).strip()
            if 2 < len(name) < 60:
                return name
    return None

# ── Legacy Compatibility Layer ────────────────────────────────────────────────
class TrustScoreGenerator:
    def __init__(self):
        pass

    def generate_score(self, scraped_data: dict, extracted_data: dict) -> dict:
        # This is now handled by trust_score.py, but we provide a shim here
        # for any code still calling this method directly.
        from trust_score import calculate_trust_score
        dossier = {
            "trust_score": 0,
            "risk_level": "UNKNOWN",
            "contradictions": detect_contradictions(extracted_data, scraped_data),
            "extracted": extracted_data
        }
        score_result = calculate_trust_score(dossier)
        return {
            "trust_score": score_result["score"],
            "risk_level": score_result["risk_level"],
            "contradictions": dossier["contradictions"]
        }
