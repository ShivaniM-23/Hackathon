"""
ShadowTrace AI — Trust Score Engine
Calculates a 0–100 company risk score from the analyzed dossier.
Each factor is independently scored and weighted.
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ScoreFactor:
    name: str
    score: int          # Points earned (0 to max_points)
    max_points: int
    reason: str
    is_red_flag: bool = False


def calculate_trust_score(dossier: dict) -> dict:
    """
    Main scoring function. 
    Now expanded with extended presence signals.
    Total max points = 115, normalized to 100.
    """
    factors: list[ScoreFactor] = []
    extracted = dossier.get("extracted", {})
    raw_data_summary = dossier.get("raw_data_summary", {})
    raw_summary = _normalize_raw_summary(raw_data_summary)
    raw_data = dossier.get("raw_data", {}) # Access for extended sources
    established = _has_established_footprint(raw_summary, extracted)

    # ── Factor 1: Domain age (20 pts) ─────────────────────────────────────────
    factors.append(_score_domain_age(extracted, raw_summary))

    # ── Factor 2: Employee count consistency (15 pts) ─────────────────────────
    factors.append(_score_employee_consistency(extracted, established))

    # ── Factor 3: Social media presence (10 pts) ──────────────────────────────
    factors.append(_score_social_presence(extracted, established))

    # ── Factor 4: News coverage (10 pts) ─────────────────────────────────────
    factors.append(_score_news_coverage(raw_summary, established))

    # ── Factor 5: Address verification (15 pts) ───────────────────────────────
    factors.append(_score_address(extracted, established))

    # ── Factor 6: Review sentiment (10 pts) ───────────────────────────────────
    factors.append(_score_reviews(extracted, raw_summary, established))

    # ── Factor 7: Client verification (10 pts) ────────────────────────────────
    factors.append(_score_client_claims(extracted, raw_summary, established))

    # ── Factor 8: Digital footprint depth (10 pts) ───────────────────────────
    factors.append(_score_digital_footprint(extracted, raw_summary))

    # ── Factor 9: Global Recognition / Wikipedia (20 pts) ────────────────────
    global_factor = _score_global_recognition(raw_summary)
    factors.append(global_factor)

    # ── Factor 10: Document integrity (10 pts) ─────────────────────────────────
    factors.append(_score_documents(extracted))
    
    # ── Factor 11: Extended digital footprint (15 pts) ─────────────────────
    factors.append(_score_extended_presence(extracted, raw_summary))

    # ── Contradiction penalty (up to -20 pts) ────────────────────────────────
    contradiction_penalty = _calculate_contradiction_penalty(dossier.get("contradictions", []))

    # ── Normalization ─────────────────────────────────────────────────────────
    raw_total = sum(f.score for f in factors)
    max_total = sum(f.max_points for f in factors)
    
    # Apply AI score adjustment (based on reading actual content)
    ai_adjustment = dossier.get("score_adjustment", 0)
    
    # Calculate final score: (Raw / Max) * 100 - Penalty + AI Adjustment
    normalized_score = int((raw_total / max_total) * 100) if max_total > 0 else 0
    final_score = max(0, min(100, normalized_score - contradiction_penalty + ai_adjustment))

    # Also use AI's fraud and legitimacy signals for red flags
    ai_fraud_signals = dossier.get("fraud_signals", [])
    ai_legit_signals = dossier.get("legitimacy_signals", [])

    # Combine red flags: score-based + AI-detected
    red_flags = [f.reason for f in factors if f.is_red_flag] + ai_fraud_signals

    # Add contradiction-based red flags
    for c in dossier.get("contradictions", []):
        if c.get("status") == "MISMATCH" and c.get("severity") == "HIGH":
            claim = c.get("claimed") or c.get("claim") or c.get("field", "Claim")
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
        "raw_score_sum": raw_total,
        "max_score_sum": max_total,
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
    }


# ── Individual scoring functions ──────────────────────────────────────────────

def _normalize_raw_summary(raw_data: dict) -> dict:
    """Accept either the full raw scrape object or the compact summary object."""
    raw_data = raw_data or {}
    summary = raw_data.get("summary", {}) if isinstance(raw_data, dict) else {}
    whois = raw_data.get("whois", {}) if isinstance(raw_data, dict) else {}
    pages = raw_data.get("pages", []) if isinstance(raw_data, dict) else []
    reviews = raw_data.get("reviews", {}) if isinstance(raw_data, dict) else {}

    return {
        "whois_creation_year": (
            raw_data.get("whois_creation_year")
            or summary.get("whois_creation_year")
            or whois.get("creation_year")
        ),
        "domain_age_days": (
            raw_data.get("domain_age_days")
            or summary.get("domain_age_days")
            or whois.get("domain_age_days")
        ),
        "news_article_count": (
            raw_data.get("news_article_count")
            or summary.get("news_article_count")
            or raw_data.get("news_count", 0)
        ),
        "fraud_news_count": (
            raw_data.get("fraud_news_count")
            or summary.get("fraud_news_count")
            or 0
        ),
        "reviews": reviews or summary.get("reviews", {}),
        "pages_scraped": raw_data.get("pages_scraped") or summary.get("pages_scraped") or len(pages),
        "scraped_sources": summary.get("scraped_sources") or [p.get("source", "site_page") for p in pages],
        "crawl_stats": raw_data.get("crawl_stats") or summary.get("crawl_stats", {}),
        "wikipedia": raw_data.get("wikipedia", {}),
    }


def _has_established_footprint(raw_summary: dict, extracted: dict) -> bool:
    domain_age_days = raw_summary.get("domain_age_days") or 0
    return (
        domain_age_days >= 365 * 5
        or raw_summary.get("news_article_count", 0) >= 3
        or raw_summary.get("pages_scraped", 0) >= 8
        or bool(extracted.get("linkedin_profile_exists") or extracted.get("has_linkedin"))
        or raw_summary.get("wikipedia", {}).get("found", False)
    )

def _score_global_recognition(raw_summary: dict) -> ScoreFactor:
    MAX = 20
    wiki = raw_summary.get("wikipedia", {})
    if wiki.get("found"):
        return ScoreFactor(
            "global_recognition", MAX, MAX,
            "Company is globally recognized (Wikipedia page found)",
            False
        )
    return ScoreFactor("global_recognition", 0, MAX, "No global Wikipedia page found", False)


def _score_domain_age(extracted: dict, raw_summary: dict) -> ScoreFactor:
    MAX = 20
    domain_year = raw_summary.get("whois_creation_year")
    claimed_year_str = extracted.get("founding_year", "")
    domain_age_days = raw_summary.get("domain_age_days", 0) or 0

    claimed_year = None
    if claimed_year_str:
        match = re.search(r"(19|20)\d{2}", str(claimed_year_str))
        if match: claimed_year = int(match.group())

    if domain_year is None:
        return ScoreFactor("domain_age", 5, MAX, "Could not verify domain registration date", False)

    # REFINED LOGIC: Domain age > 5 years is a strong trust signal
    bonus = 5 if domain_age_days > 1825 else 0
    
    if domain_age_days < 180: # Very new domain (6 months)
        return ScoreFactor("domain_age", 0, MAX, f"Domain created recently ({domain_year}) — high risk", True)

    # Cross-check
    if claimed_year and domain_year:
        year_diff = domain_year - claimed_year
        if year_diff > 2:
            return ScoreFactor(
                "domain_age", 0, MAX,
                f"Domain created {domain_year} but company claims founding in {claimed_year} — {year_diff} year gap",
                is_red_flag=True,
            )
        elif year_diff > 0:
            return ScoreFactor(
                "domain_age", 10, MAX,
                f"Minor gap: domain {domain_year}, claimed founding {claimed_year}",
                is_red_flag=False,
            )
        elif year_diff < -3:
            return ScoreFactor("domain_age", 0, MAX, f"Claimed founding ({claimed_year}) vs Domain ({domain_year}) mismatch", True)

    score = min(MAX, int((domain_age_days / 1825) * MAX) + bonus)
    return ScoreFactor("domain_age", score, MAX, f"Domain established for {domain_age_days // 365} years", False)


def _score_employee_consistency(extracted: dict, established: bool = False) -> ScoreFactor:
    MAX = 15
    claimed = extracted.get("employee_count_claimed")
    linkedin = extracted.get("employee_count_linkedin")

    if claimed is None and linkedin is None:
        return ScoreFactor("employee_consistency", 7, MAX, "No employee count data found", False)

    if linkedin is None:
        return ScoreFactor("employee_consistency", 8, MAX, f"Website claims {claimed} (no LinkedIn data)", False)
    
    if claimed is None:
        return ScoreFactor("employee_consistency", 8, MAX, "Employee data unavailable — neutral score", False)

    # Ratio check
    try:
        claimed_n = int(str(claimed).replace("+", "").replace(",", "").strip())
        linkedin_n = int(str(linkedin).replace("+", "").replace(",", "").strip())
    except (ValueError, AttributeError):
        return ScoreFactor("employee_consistency", 8, MAX, "Could not parse employee count numbers — neutral score", False)

    if linkedin_n == 0:
        return ScoreFactor(
            "employee_consistency", 0, MAX,
            f"Zero LinkedIn employees vs claimed {claimed_n} — likely fake company",
            is_red_flag=True,
        )

    ratio = claimed_n / linkedin_n
    if ratio > 10:
        return ScoreFactor(
            "employee_consistency", 0, MAX,
            f"Employee count inflated {ratio:.0f}x: claims {claimed_n}, LinkedIn shows {linkedin_n}",
            is_red_flag=True,
        )
    elif ratio > 3:
        return ScoreFactor(
            "employee_consistency", 5, MAX,
            f"Employee count inconsistent: claims {claimed_n}, LinkedIn shows {linkedin_n}",
            is_red_flag=False,
        )
    elif ratio > 1.5:
        return ScoreFactor("employee_consistency", 10, MAX, f"Minor employee count gap: {claimed_n} vs {linkedin_n}", False)

    return ScoreFactor("employee_consistency", MAX, MAX, f"Employee count consistent: {claimed_n} claimed, {linkedin_n} on LinkedIn", False)


def _score_social_presence(extracted: dict, established: bool = False) -> ScoreFactor:
    MAX = 10
    score = 0
    notes = []

    linkedin_exists = extracted.get("linkedin_profile_exists", False) or extracted.get("has_linkedin", False)
    if linkedin_exists:
        score += 4
        notes.append("LinkedIn")
    if extracted.get("has_twitter"):
        score += 2
        notes.append("Twitter")
    if extracted.get("has_github"):
        score += 2
        notes.append("GitHub")
    if extracted.get("has_youtube", False):
        score += 1
        notes.append("YouTube")
    if extracted.get("has_crunchbase", False):
        score += 1
        notes.append("Crunchbase")

    domain_age_days = extracted.get("domain_age_days", 0) or 0
    is_red_flag = (score == 0 and domain_age_days < 730)
    
    if score == 0:
        return ScoreFactor("social_presence", 0, MAX, "No social presence found", is_red_flag)
    
    return ScoreFactor("social_presence", min(MAX, score), MAX, f"Social presence found: {', '.join(notes)}", is_red_flag)


def _score_news_coverage(raw_summary: dict, established: bool = False) -> ScoreFactor:
    MAX = 10
    news_count = raw_summary.get("news_article_count", 0)
    fraud_count = raw_summary.get("fraud_news_count", 0)

    if fraud_count > 0:
        return ScoreFactor("news_coverage", 0, MAX, f"{fraud_count} fraud/scam-related news article(s) found", is_red_flag=True)

    if news_count == 0:
        return ScoreFactor("news_coverage", 3, MAX, "No news coverage found — neutral score", False)
    elif news_count < 4:
        return ScoreFactor("news_coverage", 5, MAX, f"{news_count} news articles found", False)
    elif news_count < 10:
        return ScoreFactor("news_coverage", 8, MAX, f"{news_count} news articles found", False)
    else:
        return ScoreFactor("news_coverage", MAX, MAX, f"{news_count}+ news articles — well covered", False)


def _score_address(extracted: dict, established: bool = False) -> ScoreFactor:
    MAX = 15

    if extracted.get("address_suspicious"):
        return ScoreFactor("address_verification", 0, MAX, "Registered address flagged as suspicious or shell network", is_red_flag=True)

    if not extracted.get("addresses"):
        return ScoreFactor("address_verification", 5, MAX, "No registered address found on website — neutral score", False)

    return ScoreFactor("address_verification", 10, MAX, "Address found on website", False)


def _score_reviews(extracted: dict, raw_data: dict = {}, established: bool = False) -> ScoreFactor:
    MAX = 10
    reviews = raw_data.get("reviews", {})
    reddit = reviews.get("reddit", {})
    
    score = 5
    notes = []
    
    FRAUD_KEYWORDS = [
        "scam", "fraud", "fake", "cheated", "money not returned",
        "disappeared", "no refund", "ponzi", "fake company",
        "not registered", "illegal", "police complaint", "fir filed",
        "cyber crime", "blacklist", "avoid at all costs"
    ]
    SERVICE_COMPLAINT_KEYWORDS = [
        "bad service", "poor quality", "delayed", "not happy",
        "overpriced", "rude", "disappointed", "not recommended"
    ]
    
    neg_posts = reddit.get("negative_posts", [])
    fraud_posts = [p for p in neg_posts if any(kw in p.get("title", "").lower() for kw in FRAUD_KEYWORDS)]
    complaint_posts = [p for p in neg_posts if any(kw in p.get("title", "").lower() for kw in SERVICE_COMPLAINT_KEYWORDS)]
    
    is_red_flag = False
    if len(fraud_posts) >= 2:
        score -= 15
        is_red_flag = True
        notes.append(f"⚠️ {len(fraud_posts)} fraud-specific Reddit reports")
    elif len(complaint_posts) > 5:
        score -= 3
        notes.append(f"Some service complaints on Reddit ({len(complaint_posts)})")
    elif reddit.get("mentions", 0) > 0 and len(fraud_posts) == 0:
        score += 4
        notes.append(f"Reddit presence: {reddit.get('mentions')} mentions, no fraud signals")
    else:
        notes.append("No significant public review data found")
        
    return ScoreFactor("review_sentiment", max(0, min(MAX, score)), MAX, " | ".join(notes), is_red_flag)


def _score_client_claims(extracted: dict, raw_summary: dict = None, established: bool = False) -> ScoreFactor:
    MAX = 10
    raw_summary = raw_summary or {}
    claimed_clients = extracted.get("claimed_clients", [])
    verified_clients = extracted.get("verified_clients", [])

    if not claimed_clients:
        return ScoreFactor("client_verification", 6, MAX, "No clients claimed — neutral score", False)

    if not verified_clients:
        return ScoreFactor("client_verification", 5, MAX, f"Claims {len(claimed_clients)} clients but unverified — neutral score", False)

    return ScoreFactor("client_verification", 9, MAX, f"{len(verified_clients)} client claims verified externally", False)

def _score_digital_footprint(extracted: dict, raw_summary: dict) -> ScoreFactor:
    MAX = 10
    score = 0
    notes = []
    sources = set(raw_summary.get("scraped_sources", []))
    pages_scraped = raw_summary.get("pages_scraped", 0) or 0

    if pages_scraped >= 10:
        score += 3
        notes.append(f"{pages_scraped} website pages crawled")
    elif pages_scraped >= 4:
        score += 2
        notes.append(f"{pages_scraped} website pages crawled")
    elif pages_scraped > 0:
        score += 1
        notes.append("Only a shallow website footprint was crawlable")

    if any("contact" in s or "location" in s or "office" in s for s in sources):
        score += 2
        notes.append("Contact/location page found")
    if any("about" in s or "company" in s or "who_we_are" in s for s in sources):
        score += 2
        notes.append("About/company page found")
    if extracted.get("linkedin_profile_exists") or extracted.get("has_linkedin"):
        score += 2
        notes.append("LinkedIn footprint present")
    if raw_summary.get("news_article_count", 0) > 0 or raw_summary.get("reviews", {}).get("overall_sentiment") not in (None, "NO_DATA"):
        score += 1
        notes.append("External mentions/reviews found")

    is_red_flag = score <= 2
    reason = " | ".join(notes) if notes else "No crawlable website or external footprint found"
    return ScoreFactor("digital_footprint", min(MAX, score), MAX, reason, is_red_flag)


def _score_documents(extracted: dict) -> ScoreFactor:
    MAX = 10
    issues = extracted.get("document_issues", [])
    if issues: return ScoreFactor("document_integrity", 0, MAX, f"Document issues: {', '.join(issues[:2])}", True)
    return ScoreFactor("document_integrity", MAX, MAX, "No document issues detected", False)


def _score_extended_presence(extracted: dict, raw_summary: dict) -> ScoreFactor:
    """New factor: Scans 10+ additional digital signals."""
    MAX = 15
    ext = raw_summary.get("extended_sources", {})
    score = 0
    notes = []
    
    # Positive signals
    if ext.get("ambitionbox", {}).get("found"): score += 3; notes.append("AmbitionBox")
    if ext.get("job_portals", {}).get("found"): score += 3; notes.append("Hiring")
    if ext.get("regulatory", {}).get("found"): score += 3; notes.append("Regulatory")
    if ext.get("crunchbase", {}).get("found"): score += 2; notes.append("Crunchbase")
    if ext.get("general_news", {}).get("count", 0) > 5: score += 2; notes.append("News")
    if ext.get("linkedin_news", {}).get("mentions", 0) > 3: score += 2; notes.append("LinkedIn")
    
    # Negative signals
    fraud = ext.get("fraud_signals", {})
    fraud_count = fraud.get("count", 0)
    if fraud_count > 2:
        return ScoreFactor("extended_presence", 0, MAX, f"⚠️ {fraud_count} fraud/scam signals found in extended search", True)
    
    if not notes:
        return ScoreFactor("extended_presence", 3, MAX, "Limited footprint across extended platforms", False)
    
    return ScoreFactor("extended_presence", min(MAX, score), MAX, "Found in: " + ", ".join(notes), False)


def _calculate_contradiction_penalty(contradictions: list[dict]) -> int:
    penalty = 0
    for c in contradictions:
        status = c.get("status", "MISMATCH")
        severity = c.get("severity", "LOW")
        if status == "MISMATCH":
            penalty += 8 if severity == "HIGH" else 2 if severity == "MEDIUM" else 1
        elif status == "UNVERIFIED":
            penalty += 1
    return min(penalty, 20)
