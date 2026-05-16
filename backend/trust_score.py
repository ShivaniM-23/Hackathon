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
    raw_summary = dossier.get("raw_data_summary", {})

    # ── Factor 1: Domain age vs founding year (20 pts) ───────────────────────
    factors.append(_score_domain_age(extracted, raw_summary))

    # ── Factor 2: Employee count consistency (15 pts) ─────────────────────────
    factors.append(_score_employee_consistency(extracted))

    # ── Factor 3: Social media presence (10 pts) ──────────────────────────────
    factors.append(_score_social_presence(extracted))

    # ── Factor 4: News coverage (10 pts) ─────────────────────────────────────
    factors.append(_score_news_coverage(raw_summary))

    # ── Factor 5: Address verification (15 pts) ───────────────────────────────
    factors.append(_score_address(extracted))

    # ── Factor 6: Review sentiment (10 pts) ───────────────────────────────────
    factors.append(_score_reviews(extracted, raw_summary))

    # ── Factor 7: Client verification (10 pts) ────────────────────────────────
    factors.append(_score_client_claims(extracted))

    # ── Factor 8: Document integrity (10 pts) ─────────────────────────────────
    factors.append(_score_documents(extracted))

    # ── Contradiction penalty (up to -20 pts) ────────────────────────────────
    contradiction_penalty = _calculate_contradiction_penalty(dossier.get("contradictions", []))

    # ── Total ─────────────────────────────────────────────────────────────────
    raw_score = sum(f.score for f in factors)
    final_score = max(0, min(100, raw_score - contradiction_penalty))

    red_flags = [f.reason for f in factors if f.is_red_flag]

    # Add contradiction-based red flags
    for c in dossier.get("contradictions", []):
        if c.get("status") == "MISMATCH" and c.get("severity") == "HIGH":
            red_flags.append(f"Contradiction: {c['claim']} — {c['evidence']}")

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
        year_diff = abs(domain_year - claimed_year)
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


def _score_employee_consistency(extracted: dict) -> ScoreFactor:
    MAX = 15
    claimed = extracted.get("employee_count_claimed")
    linkedin = extracted.get("employee_count_linkedin")

    if claimed is None and linkedin is None:
        return ScoreFactor("employee_consistency", 5, MAX, "No employee count data available", False)

    if claimed is None:
        return ScoreFactor("employee_consistency", 8, MAX, f"LinkedIn shows {linkedin} employees (no website claim to compare)", False)

    if linkedin is None:
        return ScoreFactor("employee_consistency", 8, MAX, f"Website claims {claimed} employees (no LinkedIn data)", False)

    # Parse numbers
    try:
        claimed_n = int(str(claimed).replace("+", "").replace(",", "").strip())
        linkedin_n = int(str(linkedin).replace("+", "").replace(",", "").strip())
    except (ValueError, AttributeError):
        return ScoreFactor("employee_consistency", 5, MAX, "Could not parse employee count numbers", False)

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


def _score_social_presence(extracted: dict) -> ScoreFactor:
    MAX = 10
    score = 0
    notes = []

    # LinkedIn — check profile_exists from raw linkedin data, not just has_linkedin text flag
    linkedin_exists = extracted.get("linkedin_profile_exists", False) or extracted.get("has_linkedin", False)
    if linkedin_exists:
        score += 5
        notes.append("LinkedIn page verified")
    else:
        notes.append("No LinkedIn company page detected")

    if extracted.get("has_twitter"):
        score += 2
        notes.append("Twitter/X presence")

    if extracted.get("linkedin_followers", 0) > 500:
        score += 2
        notes.append(f"{extracted['linkedin_followers']} LinkedIn followers")

    if extracted.get("linkedin_active"):
        score += 1
        notes.append("Active LinkedIn posting")

    # Only flag as red flag if truly no social presence at all
    is_red_flag = score == 0 and not linkedin_exists
    return ScoreFactor(
        "social_presence", score, MAX,
        " | ".join(notes) or "No social presence found",
        is_red_flag
    )


def _score_news_coverage(raw_summary: dict) -> ScoreFactor:
    MAX = 10
    news_count = raw_summary.get("news_article_count", 0)
    fraud_count = raw_summary.get("fraud_news_count", 0)

    if fraud_count > 0:
        return ScoreFactor(
            "news_coverage", 0, MAX,
            f"{fraud_count} fraud/scam-related news article(s) found",
            is_red_flag=True,
        )

    if news_count == 0:
        return ScoreFactor("news_coverage", 2, MAX, "No news coverage found — unverifiable reputation", False)
    elif news_count < 3:
        return ScoreFactor("news_coverage", 5, MAX, f"{news_count} news articles found", False)
    elif news_count < 10:
        return ScoreFactor("news_coverage", 8, MAX, f"{news_count} news articles found", False)
    else:
        return ScoreFactor("news_coverage", MAX, MAX, f"{news_count}+ news articles — well covered", False)


def _score_address(extracted: dict) -> ScoreFactor:
    MAX = 15

    if extracted.get("address_suspicious"):
        shared_count = extracted.get("address_shared_companies", 0)
        if shared_count > 3:
            return ScoreFactor(
                "address_verification", 0, MAX,
                f"Address shared with {shared_count} other companies — possible shell network",
                is_red_flag=True,
            )
        return ScoreFactor(
            "address_verification", 3, MAX,
            "Registered address flagged as suspicious",
            is_red_flag=True,
        )

    if not extracted.get("addresses"):
        return ScoreFactor("address_verification", 5, MAX, "No registered address found on website", False)

    if extracted.get("address_verified"):
        return ScoreFactor("address_verification", MAX, MAX, "Address verified on Google Maps", False)

    return ScoreFactor("address_verification", 8, MAX, "Address found but not independently verified", False)


def _score_reviews(extracted: dict, raw_data: dict = {}) -> ScoreFactor:
    MAX = 10
    reviews = raw_data.get("reviews", {})
    tp = reviews.get("trustpilot", {})
    gd = reviews.get("glassdoor", {})
    reddit = reviews.get("reddit", {})
    
    score = 0
    notes = []
    
    # 1. Trustpilot (Weight: 4)
    if tp.get("found") and tp.get("rating"):
        rating = tp["rating"]
        if rating >= 4.0: score += 4
        elif rating >= 3.0: score += 2
        else: score -= 5 # Penalty
        notes.append(f"Trustpilot: {rating}/5")
        
    # 2. Reddit Sentiment (Weight: 3)
    neg_reddit = len(reddit.get("negative_posts", []))
    if reddit.get("mentions", 0) > 0:
        if neg_reddit >= 3:
            score -= 10 # Massive penalty
            notes.append(f"Red flag: {neg_reddit} negative Reddit posts")
        elif neg_reddit > 0:
            score += 1
            notes.append("Mixed Reddit sentiment")
        else:
            score += 3
            notes.append("Clean Reddit footprint")
            
    # 3. Glassdoor (Weight: 3)
    if gd.get("rating"):
        score += 3 if gd["rating"] >= 3.5 else 1
        notes.append(f"Glassdoor: {gd['rating']}/5")

    # 4. No Data Penalty
    if not notes:
        return ScoreFactor("review_sentiment", 0, MAX, "No public reviews found — suspicious for established company", True)

    is_red_flag = score < 0
    return ScoreFactor("review_sentiment", max(0, min(MAX, score)), MAX, " | ".join(notes), is_red_flag)


def _score_client_claims(extracted: dict) -> ScoreFactor:
    MAX = 10
    claimed_clients = extracted.get("claimed_clients", [])
    verified_clients = extracted.get("verified_clients", [])

    if not claimed_clients:
        return ScoreFactor("client_verification", 5, MAX, "No specific client claims made", False)

    if not verified_clients:
        return ScoreFactor(
            "client_verification", 0, MAX,
            f"Claims {len(claimed_clients)} client(s) but none could be verified publicly",
            is_red_flag=True,
        )

    ratio = len(verified_clients) / len(claimed_clients)
    score = int(ratio * MAX)
    return ScoreFactor(
        "client_verification", score, MAX,
        f"{len(verified_clients)}/{len(claimed_clients)} client claims verified",
        False,
    )


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
        status = c.get("status", "UNVERIFIED")
        severity = c.get("severity", "LOW")

        if status == "MISMATCH":
            penalty += 8 if severity == "HIGH" else 4
        elif status == "UNVERIFIED":
            penalty += 1

    return min(penalty, 20)
