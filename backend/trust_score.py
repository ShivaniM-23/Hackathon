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
    Main scoring function. Returns:
    {
        score: int (0–100),
        risk_level: "LOW" | "MEDIUM" | "HIGH",
        breakdown: { factor_name: {score, max, reason} },
        red_flags: [str],
        factors: [ScoreFactor]
    }
    """
    factors: list[ScoreFactor] = []
    extracted = dossier.get("extracted", {})
    raw_data = dossier.get("raw_data_summary", {})
    raw_summary = _normalize_raw_summary(raw_data)
    established = _has_established_footprint(raw_summary, extracted)

    # ── Factor 1: Domain age vs founding year (20 pts) ───────────────────────
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

    # ── Contradiction penalty (up to -20 pts) ────────────────────────────────
    contradiction_penalty = _calculate_contradiction_penalty(dossier.get("contradictions", []))

    # ── Total ─────────────────────────────────────────────────────────────────
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

    claimed_year = None
    if claimed_year_str:
        match = re.search(r"(19|20)\d{2}", str(claimed_year_str))
        if match:
            claimed_year = int(match.group())

    if domain_year is None:
        return ScoreFactor("domain_age", 5, MAX, "Could not verify domain registration date", False)

    domain_age_days = raw_summary.get("domain_age_days", 0) or 0

    # Domain less than 1 year old — very suspicious
    if domain_age_days < 365:
        return ScoreFactor(
            "domain_age", 0, MAX,
            f"Domain created recently ({domain_year}) — only {domain_age_days} days old",
            is_red_flag=True,
        )

    # Cross-check with claimed founding year
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

    # Domain > 5 years old — good sign
    if domain_age_days > 1825:
        return ScoreFactor("domain_age", MAX, MAX, f"Domain is {domain_age_days // 365} years old — established", False)

    # Domain 1–5 years old
    score = int((domain_age_days / 1825) * MAX)
    return ScoreFactor("domain_age", score, MAX, f"Domain is {domain_age_days // 365} years old", False)


def _score_employee_consistency(extracted: dict, established: bool = False) -> ScoreFactor:
    MAX = 15
    claimed = extracted.get("employee_count_claimed")
    linkedin = extracted.get("employee_count_linkedin")

    if claimed is None or linkedin is None:
        return ScoreFactor("employee_consistency", 8, MAX, "Employee data unavailable — neutral score", False)

    # Parse numbers
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

    if not issues:
        return ScoreFactor("document_integrity", MAX, MAX, "No document integrity issues detected", False)

    if len(issues) > 2:
        return ScoreFactor(
            "document_integrity", 0, MAX,
            f"{len(issues)} document issues: {', '.join(issues[:2])}…",
            is_red_flag=True,
        )

    return ScoreFactor(
        "document_integrity", 4, MAX,
        f"Document issues: {', '.join(issues)}",
        is_red_flag=False,
    )


def _calculate_contradiction_penalty(contradictions: list[dict]) -> int:
    """
    Deducts points for each confirmed mismatch.
    High severity mismatch: -8 pts
    Medium: -4 pts
    Unverified: -1 pt
    Max penalty: 20 pts
    """
    penalty = 0
    for c in contradictions:
        status = c.get("status", "MISMATCH")
        severity = c.get("severity", "LOW")

        if status == "MISMATCH":
            penalty += 8 if severity == "HIGH" else 2 if severity == "MEDIUM" else 1
        elif status == "UNVERIFIED":
            penalty += 1

    return min(penalty, 20)
