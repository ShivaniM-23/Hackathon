import re
import os
import json
import httpx
from dataclasses import dataclass, field
from typing import Optional

GROQ_API_KEY = os.getenv("ANTHROPIC_API_KEY") # Using the Groq alias

@dataclass
class ScoreFactor:
    name: str
    score: int          # Points earned (0 to max_points)
    max_points: int
    reason: str
    is_red_flag: bool = False

def _normalize_raw_summary(raw_data: dict) -> dict:
    raw_data = raw_data or {}
    summary = raw_data.get("summary", {}) if isinstance(raw_data, dict) else {}
    whois = raw_data.get("whois", {}) if isinstance(raw_data, dict) else {}
    pages = raw_data.get("pages", []) if isinstance(raw_data, dict) else []
    reviews = raw_data.get("reviews", {}) if isinstance(raw_data, dict) else {}

    return {
        "whois_creation_year": (raw_data.get("whois_creation_year") or summary.get("whois_creation_year") or whois.get("creation_year")),
        "domain_age_days": (raw_data.get("domain_age_days") or summary.get("domain_age_days") or whois.get("domain_age_days")),
        "news_article_count": (raw_data.get("news_article_count") or summary.get("news_article_count") or raw_data.get("news_count", 0)),
        "fraud_news_count": (raw_data.get("fraud_news_count") or summary.get("fraud_news_count") or 0),
        "reviews": reviews or summary.get("reviews", {}),
        "pages_scraped": raw_data.get("pages_scraped") or summary.get("pages_scraped") or len(pages),
        "scraped_sources": summary.get("scraped_sources") or [p.get("source", "site_page") for p in pages],
        "crawl_stats": raw_data.get("crawl_stats") or summary.get("crawl_stats", {}),
        "wikipedia": raw_data.get("wikipedia", {}),
        "extended_sources": raw_data.get("extended_sources") or summary.get("extended_sources", {})
    }


def _determine_tier(raw_summary: dict, extracted: dict) -> int:
    wiki = raw_summary.get("wikipedia", {}).get("found", False)
    ext = raw_summary.get("extended_sources", {})
    regulatory = ext.get("regulatory", {}).get("found", False)
    crunchbase = ext.get("crunchbase", {}).get("found", False)
    
    linkedin_count_str = extracted.get("employee_count_linkedin", "0")
    linkedin_count = 0
    try:
        linkedin_count = int(str(linkedin_count_str).replace("+", "").replace(",", "").strip())
    except: pass
    
    # TIER 1: Enterprise / Public Company
    if wiki or regulatory or linkedin_count > 5000 or crunchbase:
        return 1
        
    # TIER 2: Established SME / Mid-Market
    tier2_signals = 0
    domain_age_days = raw_summary.get("domain_age_days", 0) or 0
    if domain_age_days >= 1825: tier2_signals += 1
    if raw_summary.get("news_article_count", 0) >= 3: tier2_signals += 1
    if raw_summary.get("pages_scraped", 0) >= 8: tier2_signals += 1
    if extracted.get("linkedin_profile_exists") or extracted.get("has_linkedin"): tier2_signals += 1
    
    if tier2_signals >= 2:
        return 2
        
    # TIER 3: Unknown / New Entrant
    return 3


def calculate_trust_score(dossier: dict) -> dict:
    factors: list[ScoreFactor] = []
    extracted = dossier.get("extracted", {})
    raw_data_summary = dossier.get("raw_data_summary", {})
    raw_summary = _normalize_raw_summary(raw_data_summary)
    
    tier = _determine_tier(raw_summary, extracted)

    factors.append(_score_domain_age(extracted, raw_summary, tier))
    factors.append(_score_employee_consistency(extracted, tier))
    factors.append(_score_social_presence(extracted, raw_summary, tier))
    factors.append(_score_news_coverage(raw_summary, tier))
    factors.append(_score_address(extracted, tier))
    factors.append(_score_reviews(extracted, raw_summary, tier))
    factors.append(_score_client_claims(extracted, raw_summary, tier))
    factors.append(_score_digital_footprint(extracted, raw_summary, tier))
    factors.append(_score_global_recognition(raw_summary, tier))
    factors.append(_score_documents(extracted, tier))
    factors.append(_score_extended_presence(extracted, raw_summary, tier))

    contradictions = dossier.get("contradictions", [])
    contradiction_penalty = _calculate_contradiction_penalty(contradictions, tier)

    raw_total = sum(f.score for f in factors)
    max_total = sum(f.max_points for f in factors)
    
    ai_adjustment = dossier.get("score_adjustment", 0)
    
    normalized_score = int((raw_total / max_total) * 100) if max_total > 0 else 0
    final_score = max(0, min(100, normalized_score - contradiction_penalty + ai_adjustment))

    # Data Confidence Checking
    waived_or_zero = sum(1 for f in factors if ("waived" in f.reason.lower() or f.score == 0))
    data_confidence = "HIGH"
    confidence_warning = None
    
    if waived_or_zero >= 4:
        if tier in [1, 2]:
            data_confidence = "LOW"
            confidence_warning = "Insufficient scraping coverage for reliable scoring. Manual review or re-crawl recommended."
        else:
            data_confidence = "LOW"
            confidence_warning = "Genuine risk detected: Multiple data factors completely missing for a Tier 3 entity."

    ai_fraud_signals = dossier.get("fraud_signals", [])
    ai_legit_signals = dossier.get("legitimacy_signals", [])

    red_flags = [f.reason for f in factors if f.is_red_flag] + ai_fraud_signals
    for c in contradictions:
        if c.get("status") == "MISMATCH" and c.get("severity") == "HIGH":
            claim = c.get("claimed") or c.get("claim") or c.get("field", "Claim")
            if tier != 1:  # Tier 1 avoids generic scraper contradiction flags
                red_flags.append(f"Contradiction: {claim} — {c.get('evidence', 'conflicting evidence found')}")

    risk_level = (
        "LOW RISK" if final_score >= 75
        else "LOW-MEDIUM" if final_score >= 55
        else "MEDIUM RISK" if final_score >= 30
        else "HIGH RISK"
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
        "tier": tier,
        "data_confidence": data_confidence,
        "confidence_warning": confidence_warning,
        "raw_score_sum": raw_total,
        "max_score_sum": max_total,
        "contradiction_penalty": contradiction_penalty,
        "risk_level": risk_level,
        "breakdown": breakdown,
        "red_flags": red_flags[:10],
        "legitimacy_signals": ai_legit_signals,
        "legitimacy_verdict": dossier.get("legitimacy_verdict", "UNCERTAIN"),
        "ai_reasoning": dossier.get("ai_reasoning", ""),
        "factors": [{"name": f.name, "score": f.score, "max_points": f.max_points, "reason": f.reason, "is_red_flag": f.is_red_flag} for f in factors],
    }


# ── Individual Scoring Rules by Tier ──────────────────────────────────────────

def _score_domain_age(extracted: dict, raw_summary: dict, tier: int) -> ScoreFactor:
    MAX = 20
    domain_age_days = raw_summary.get("domain_age_days", 0) or 0
    domain_year = raw_summary.get("whois_creation_year")
    
    if tier == 1:
        return ScoreFactor("domain_age", MAX, MAX, "Tier 1: Enterprise domain (WHOIS redaction standard, full points)", False)
    
    if domain_year is None:
        if tier == 2:
            return ScoreFactor("domain_age", 15, MAX, "Tier 2: Domain age unavailable (Partial credit)", False)
        return ScoreFactor("domain_age", 5, MAX, "Tier 3: Could not verify domain registration date", False)
        
    if tier == 3:
        if domain_age_days < 180:
            return ScoreFactor("domain_age", 0, MAX, "Tier 3: Domain < 6 months old", True)
        
        claimed_year_str = extracted.get("founding_year", "")
        claimed_year = None
        if claimed_year_str:
            match = re.search(r"(19|20)\d{2}", str(claimed_year_str))
            if match: claimed_year = int(match.group())
            
        if claimed_year and domain_year:
            if domain_year - claimed_year > 2:
                return ScoreFactor("domain_age", 0, MAX, f"Tier 3: Domain/founding gap > 2 years", True)
                
        score = min(MAX, int((domain_age_days / 1825) * MAX))
        return ScoreFactor("domain_age", score, MAX, f"Domain established for {domain_age_days // 365} years", False)
        
    return ScoreFactor("domain_age", MAX, MAX, "Domain verified", False)


def _score_employee_consistency(extracted: dict, tier: int) -> ScoreFactor:
    MAX = 15
    claimed = extracted.get("employee_count_claimed")
    linkedin = extracted.get("employee_count_linkedin")
    
    if tier in [1, 2] and (linkedin is None or claimed is None):
        return ScoreFactor("employee_consistency", MAX, MAX, f"Tier {tier}: LinkedIn scraping gap (waived)", False)
        
    if linkedin is None or claimed is None:
        return ScoreFactor("employee_consistency", 7, MAX, "Missing employee data", False)

    try:
        claimed_n = int(str(claimed).replace("+", "").replace(",", "").strip())
        linkedin_n = int(str(linkedin).replace("+", "").replace(",", "").strip())
    except:
        return ScoreFactor("employee_consistency", 7, MAX, "Could not parse employee counts", False)
        
    if tier == 3:
        if linkedin_n == 0 and claimed_n > 1000:
            return ScoreFactor("employee_consistency", 0, MAX, "Tier 3: Zero LinkedIn employees vs thousands claimed", True)
        if linkedin_n > 0:
            ratio = claimed_n / linkedin_n
            if ratio > 10: return ScoreFactor("employee_consistency", 0, MAX, "Tier 3: Claimed count > 10x LinkedIn", True)
            if ratio > 3: return ScoreFactor("employee_consistency", 5, MAX, "Tier 3: Claimed count > 3x LinkedIn", False)
            if ratio > 1.5: return ScoreFactor("employee_consistency", 10, MAX, "Tier 3: Claimed count > 1.5x LinkedIn", False)
            
    return ScoreFactor("employee_consistency", MAX, MAX, "Employee count consistent", False)


def _score_social_presence(extracted: dict, raw_summary: dict, tier: int) -> ScoreFactor:
    MAX = 10
    score = 0
    notes = []
    
    if extracted.get("linkedin_profile_exists") or extracted.get("has_linkedin"): score += 4; notes.append("LinkedIn")
    if extracted.get("has_twitter"): score += 2; notes.append("Twitter")
    if extracted.get("has_github"): score += 2; notes.append("GitHub")
    if extracted.get("has_youtube"): score += 1; notes.append("YouTube")
    if extracted.get("has_crunchbase"): score += 1; notes.append("Crunchbase")
    
    if tier in [1, 2] and score > 0:
        return ScoreFactor("social_presence", MAX, MAX, f"Tier {tier} established entity bonus ({', '.join(notes)})", False)
    if tier in [1, 2] and score == 0:
        return ScoreFactor("social_presence", MAX, MAX, f"Tier {tier}: Social presence check waived", False)
        
    if tier == 3 and score == 0:
        domain_age_days = raw_summary.get("domain_age_days", 0) or 0
        if domain_age_days < 730:
            return ScoreFactor("social_presence", 0, MAX, "Tier 3: Zero social presence + domain < 2 years", True)
        return ScoreFactor("social_presence", 0, MAX, "Tier 3: No social presence found", False)
        
    return ScoreFactor("social_presence", min(MAX, score), MAX, f"Socials: {', '.join(notes)}", False)


def _score_news_coverage(raw_summary: dict, tier: int) -> ScoreFactor:
    MAX = 10
    news_count = raw_summary.get("news_article_count", 0)
    fraud_count = raw_summary.get("fraud_news_count", 0)
    
    if fraud_count > 0:
        if tier in [1, 2]:
            return ScoreFactor("news_coverage", 5, MAX, f"Tier {tier}: Fraud news detected (likely false positive)", False)
        return ScoreFactor("news_coverage", 0, MAX, "Tier 3: Fraud-related news found", True)
        
    if news_count == 0: return ScoreFactor("news_coverage", 3, MAX, "No news coverage", False)
    if news_count < 4: return ScoreFactor("news_coverage", 5, MAX, "1-3 news articles", False)
    if news_count < 10: return ScoreFactor("news_coverage", 8, MAX, "4-9 news articles", False)
    return ScoreFactor("news_coverage", MAX, MAX, "10+ news articles", False)


def _score_address(extracted: dict, tier: int) -> ScoreFactor:
    MAX = 15
    if extracted.get("address_suspicious"):
        return ScoreFactor("address_verification", 0, MAX, "Address flagged as suspicious", True)
        
    if not extracted.get("addresses"):
        if tier in [1, 2]: return ScoreFactor("address_verification", MAX, MAX, f"Tier {tier}: Address gap waived", False)
        return ScoreFactor("address_verification", 5, MAX, "Tier 3: No address found", False)
        
    return ScoreFactor("address_verification", 10, MAX, "Address found", False)


def _score_reviews(extracted: dict, raw_summary: dict, tier: int) -> ScoreFactor:
    MAX = 10
    reviews = raw_summary.get("reviews", {})
    reddit = reviews.get("reddit", {})
    company_name = extracted.get("company_name", "the company")
    
    FRAUD_KEYWORDS = ["scam", "fraud", "fake", "ponzi", "fir filed", "police"]
    COMPLAINT_KEYWORDS = ["bad service", "poor quality", "delayed", "terrible"]
    
    neg_posts = reddit.get("negative_posts", [])
    raw_fraud_posts = [p for p in neg_posts if any(kw in p.get("title", "").lower() for kw in FRAUD_KEYWORDS)]
    complaint_posts = [p for p in neg_posts if any(kw in p.get("title", "").lower() for kw in COMPLAINT_KEYWORDS)]
    
    # ── SLM FALSE POSITIVE FILTER ───────────────────────────────────────────
    # Validate if the Reddit post is ACTUALLY about this company committing a scam.
    fraud_posts = []
    for p in raw_fraud_posts:
        title = p.get("title", "")
        if GROQ_API_KEY:
            prompt = f"Does this text describe a scam or fraud committed by the company '{company_name}'? Or is it completely unrelated (like a car, a game, or a different entity)? Text: '{title}'. Reply with ONLY the word YES or NO."
            try:
                response = httpx.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                    json={"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": prompt}], "temperature": 0.0},
                    timeout=5.0
                )
                answer = response.json()["choices"][0]["message"]["content"].strip().upper()
                print(answer)
                if "YES" in answer:
                    fraud_posts.append(p)
            except:
                fraud_posts.append(p) # Fallback to keyword if SLM fails
        else:
            fraud_posts.append(p)

    if len(fraud_posts) >= 2:
        if tier in [1, 2]:
            return ScoreFactor("review_sentiment", 5, MAX, f"Tier {tier}: Fraud keywords in Reddit (potential false positive)", False)
        return ScoreFactor("review_sentiment", 0, MAX, "Tier 3: 2+ Reddit fraud posts", True)
        
    if len(complaint_posts) >= 5: return ScoreFactor("review_sentiment", 7, MAX, "5+ service complaints", False)
    if reddit.get("mentions", 0) > 0 and len(fraud_posts) == 0: return ScoreFactor("review_sentiment", 9, MAX, "Positive/neutral Reddit mentions", False)
    
    if tier in [1, 2]: return ScoreFactor("review_sentiment", MAX, MAX, f"Tier {tier}: Review gap waived", False)
    return ScoreFactor("review_sentiment", 5, MAX, "Tier 3: No review data (neutral)", False)


def _score_client_claims(extracted: dict, raw_summary: dict, tier: int) -> ScoreFactor:
    MAX = 10
    claimed = extracted.get("claimed_clients", [])
    verified = extracted.get("verified_clients", [])
    
    if not claimed:
        if tier in [1, 2]: return ScoreFactor("client_verification", MAX, MAX, f"Tier {tier}: Client claims waived", False)
        return ScoreFactor("client_verification", 6, MAX, "Tier 3: No clients claimed", False)
        
    if not verified:
        if tier in [1, 2]: return ScoreFactor("client_verification", MAX, MAX, f"Tier {tier}: Client verification waived", False)
        return ScoreFactor("client_verification", 5, MAX, "Tier 3: Clients claimed but unverified", False)
        
    return ScoreFactor("client_verification", 9, MAX, "Clients externally verified", False)


def _score_digital_footprint(extracted: dict, raw_summary: dict, tier: int) -> ScoreFactor:
    MAX = 10
    score = 0
    pages = raw_summary.get("pages_scraped", 0)
    if pages > 10: score += 4
    elif pages > 0: score += 2
    
    if tier == 1:
        return ScoreFactor("digital_footprint", max(8, score), MAX, "Tier 1 floor (8/10)", False)
        
    return ScoreFactor("digital_footprint", min(MAX, score + 4), MAX, f"Footprint coverage (pages: {pages})", False)


def _score_global_recognition(raw_summary: dict, tier: int) -> ScoreFactor:
    MAX = 20
    wiki = raw_summary.get("wikipedia", {}).get("found", False)
    
    if wiki: return ScoreFactor("global_recognition", 20, MAX, "Wikipedia confirmed", False)
    if tier == 1: return ScoreFactor("global_recognition", 20, MAX, "Tier 1: Global recognition assumed", False)
    
    ext = raw_summary.get("extended_sources", {})
    sec = 1 if ext.get("regulatory", {}).get("found") else 0
    news = 1 if raw_summary.get("news_article_count", 0) > 20 else 0
    ticker = 1 if "ticker" in str(raw_summary).lower() else 0
    
    secondaries = sec + news + ticker
    if secondaries >= 2: return ScoreFactor("global_recognition", 17, MAX, "2+ secondary global signals", False)
    if secondaries == 1: return ScoreFactor("global_recognition", 12, MAX, "1 secondary global signal", False)
    
    if raw_summary.get("domain_age_days", 0) > 1825:
        return ScoreFactor("global_recognition", 10, MAX, "Domain > 5 years, no other global signals", False)
        
    return ScoreFactor("global_recognition", 0, MAX, "No global recognition signals", False)


def _score_documents(extracted: dict, tier: int) -> ScoreFactor:
    MAX = 10
    if extracted.get("document_issues"):
        return ScoreFactor("document_integrity", 0, MAX, "Document issues found", True)
    return ScoreFactor("document_integrity", MAX, MAX, "No document issues", False)


def _score_extended_presence(extracted: dict, raw_summary: dict, tier: int) -> ScoreFactor:
    MAX = 15
    ext = raw_summary.get("extended_sources", {})
    score = 0
    if ext.get("ambitionbox", {}).get("found"): score += 3
    if ext.get("job_portals", {}).get("found"): score += 3
    if ext.get("regulatory", {}).get("found"): score += 3
    if ext.get("crunchbase", {}).get("found"): score += 2
    if ext.get("general_news", {}).get("count", 0) > 5: score += 2
    if ext.get("linkedin_news", {}).get("mentions", 0) > 3: score += 2
    
    fraud_count = ext.get("fraud_signals", {}).get("count", 0)
    
    if fraud_count >= 2:
        if tier == 3: return ScoreFactor("extended_presence", 0, MAX, "Tier 3: 2+ fraud signals in extended search", True)
        return ScoreFactor("extended_presence", 5, MAX, f"Tier {tier}: Fraud signals flagged (false positive potential)", False)
        
    if tier == 1 and score == 0:
        return ScoreFactor("extended_presence", MAX, MAX, "Tier 1: Extended data gap waived", False)
        
    return ScoreFactor("extended_presence", min(MAX, score), MAX, f"Extended footprint score: {score}", False)


def _calculate_contradiction_penalty(contradictions: list[dict], tier: int) -> int:
    penalty = 0
    for c in contradictions:
        status = c.get("status", "MISMATCH")
        severity = c.get("severity", "LOW")
        
        if tier == 1:
            # Tier 1 companies don't get generic scraper contradiction penalties 
            continue
            
        if status == "MISMATCH":
            penalty += 8 if severity == "HIGH" else 2 if severity == "MEDIUM" else 1
        elif status == "UNVERIFIED":
            penalty += 1
            
    return min(penalty, 20)
