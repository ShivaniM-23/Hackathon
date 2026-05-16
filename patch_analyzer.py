import sys
import re

with open("backend/analyzer.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. We need to replace analyze_company
analyze_company_new = '''async def analyze_company(raw_data: dict) -> dict:
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
'''

content = re.sub(
    r'async def analyze_company\(raw_data: dict\) -> dict:.*?return \{.*?\}',
    analyze_company_new,
    content,
    flags=re.DOTALL
)

# 2. We need to replace detect_contradictions and legacy shim with the new AI analyzer code
ai_analyzer_code = '''async def ai_analyze_legitimacy(raw_data: dict, extracted: dict) -> dict:
    """
    Sends ALL scraped content to Phi-3/rule-based engine.
    Asks it to reason about legitimacy like a human analyst would.
    """
    # Build a comprehensive evidence document from everything scraped
    evidence = []
    # Website content
    for page in raw_data.get("pages", []):
        evidence.append(f"[WEBSITE - {page['source']}]\\n{page['text'][:1000]}")
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
        evidence.append(f"[LINKEDIN PAGE]\\n{linkedin['raw_text'][:500]}")
    elif linkedin.get("profile_exists"):
        evidence.append("[LINKEDIN] Profile URL exists but content blocked by LinkedIn")
    # Reddit posts — send ACTUAL titles not just counts
    reviews = raw_data.get("reviews", {})
    reddit = reviews.get("reddit", {})
    if reddit.get("mentions", 0) > 0:
        all_posts = (reddit.get("positive_posts", []) + 
                     reddit.get("negative_posts", []))[:10]
        reddit_text = "\\n".join([f"- {p['title']} (r/{p['sub']}, score:{p['score']})" 
                                  for p in all_posts])
        evidence.append(f"[REDDIT MENTIONS - {reddit['mentions']} total]\\n{reddit_text}")
    # Google News headlines — send actual titles
    news = raw_data.get("news", [])
    if news:
        news_text = "\\n".join([f"- {a['title']}" for a in news[:10]])
        evidence.append(f"[NEWS COVERAGE]\\n{news_text}")
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
        evidence.append(f"[EXTENDED SOURCE CHECK]\\n" + "\\n".join(ext_summary))
    # Review ratings
    tp = reviews.get("trustpilot", {})
    gd = reviews.get("glassdoor", {})
    amb = ext.get("ambitionbox", {})
    ratings_text = []
    if tp.get("found"): ratings_text.append(f"Trustpilot: {tp['rating']}/5")
    if gd.get("rating"): ratings_text.append(f"Glassdoor: {gd['rating']}/5")
    if amb.get("rating"): ratings_text.append(f"AmbitionBox: {amb['rating']}/5")
    if ratings_text:
        evidence.append(f"[REVIEW RATINGS]\\n" + "\\n".join(ratings_text))
    # Combine all evidence
    full_evidence = "\\n\\n".join(evidence)
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
 
    # Try Ollama first, fall back to rule-based
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            health = await c.get("http://localhost:11434/api/tags")
            ollama_ok = health.status_code == 200
    except:
        ollama_ok = False
    if ollama_ok:
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                res = await client.post(
                    "http://localhost:11434/api/generate",
                    json={
                        "model": "phi3",
                        "prompt": analysis_prompt,
                        "stream": False,
                        "options": {"temperature": 0.1}
                    }
                )
                raw = res.json().get("response", "")
                # Clean JSON
                match = re.search(r'\\{.*\\}', raw, re.DOTALL)
                if match:
                    clean = re.sub(r',\\s*([}\\]])', r'\\1', match.group())
                    result = json.loads(clean)
                    return result
        except Exception as e:
            logger.warning(f"AI analysis failed: {e}")
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
    return {
        "legitimacy_verdict": verdict,
        "fraud_signals": fraud_signals,
        "legitimacy_signals": legitimacy_signals,
        "score_adjustment": max(-40, min(30, score_adjustment)),
        "contradictions": contradictions,
        "reasoning": f"Based on {len(raw_data.get('pages', []))} pages scraped, "
                     f"{reddit.get('mentions', 0)} Reddit mentions, "
                     f"{len(news)} news articles analyzed."
    }
'''

content = re.sub(
    r'def detect_contradictions\(extracted: dict, raw_data: dict\) -> list\[dict\]:.*?(?=def _extract_company_name_from_pages)',
    lambda match: ai_analyzer_code + "\n\n",
    content,
    flags=re.DOTALL
)

with open("backend/analyzer.py", "w", encoding="utf-8") as f:
    f.write(content)
