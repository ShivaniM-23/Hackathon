import re

with open("backend/trust_score.py", "r", encoding="utf-8") as f:
    content = f.read()

# Replace _score_employee_consistency
old_emp = re.search(r'def _score_employee_consistency.*?return ScoreFactor\("employee_consistency", MAX, MAX, f"Employee count consistent: \{claimed_n\} claimed, \{linkedin_n\} on LinkedIn", False\)', content, re.DOTALL).group(0)

new_emp = '''def _score_employee_consistency(extracted: dict, established: bool = False) -> ScoreFactor:
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

    return ScoreFactor("employee_consistency", MAX, MAX, f"Employee count consistent: {claimed_n} claimed, {linkedin_n} on LinkedIn", False)'''
content = content.replace(old_emp, new_emp)

# Replace _score_social_presence
old_social = re.search(r'def _score_social_presence.*?is_red_flag\n    \)', content, re.DOTALL).group(0)

new_social = '''def _score_social_presence(extracted: dict, established: bool = False) -> ScoreFactor:
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
    
    return ScoreFactor("social_presence", min(MAX, score), MAX, f"Social presence found: {', '.join(notes)}", is_red_flag)'''
content = content.replace(old_social, new_social)

# Replace _score_news_coverage
old_news = re.search(r'def _score_news_coverage.*?well covered", False\)', content, re.DOTALL).group(0)

new_news = '''def _score_news_coverage(raw_summary: dict, established: bool = False) -> ScoreFactor:
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
        return ScoreFactor("news_coverage", MAX, MAX, f"{news_count}+ news articles — well covered", False)'''
content = content.replace(old_news, new_news)

# Replace _score_address
old_addr = re.search(r'def _score_address.*?independently verified", False\)', content, re.DOTALL).group(0)

new_addr = '''def _score_address(extracted: dict, established: bool = False) -> ScoreFactor:
    MAX = 15

    if extracted.get("address_suspicious"):
        return ScoreFactor("address_verification", 0, MAX, "Registered address flagged as suspicious or shell network", is_red_flag=True)

    if not extracted.get("addresses"):
        return ScoreFactor("address_verification", 5, MAX, "No registered address found on website — neutral score", False)

    return ScoreFactor("address_verification", 10, MAX, "Address found on website", False)'''
content = content.replace(old_addr, new_addr)

# Replace _score_reviews
old_reviews = re.search(r'def _score_reviews.*?" \| "\.join\(notes\), is_red_flag\)', content, re.DOTALL).group(0)

new_reviews = '''def _score_reviews(extracted: dict, raw_data: dict = {}, established: bool = False) -> ScoreFactor:
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
        
    return ScoreFactor("review_sentiment", max(0, min(MAX, score)), MAX, " | ".join(notes), is_red_flag)'''
content = content.replace(old_reviews, new_reviews)

# Replace _score_client_claims
old_clients = re.search(r'def _score_client_claims.*?False,\n    \)', content, re.DOTALL).group(0)

new_clients = '''def _score_client_claims(extracted: dict, raw_summary: dict = None, established: bool = False) -> ScoreFactor:
    MAX = 10
    raw_summary = raw_summary or {}
    claimed_clients = extracted.get("claimed_clients", [])
    verified_clients = extracted.get("verified_clients", [])

    if not claimed_clients:
        return ScoreFactor("client_verification", 6, MAX, "No clients claimed — neutral score", False)

    if not verified_clients:
        return ScoreFactor("client_verification", 5, MAX, f"Claims {len(claimed_clients)} clients but unverified — neutral score", False)

    return ScoreFactor("client_verification", 9, MAX, f"{len(verified_clients)} client claims verified externally", False)'''
content = content.replace(old_clients, new_clients)

with open("backend/trust_score.py", "w", encoding="utf-8") as f:
    f.write(content)
