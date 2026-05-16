"""
ShadowTrace AI — Scraper (Discovery & Review Edition)
Collects raw data from: company website, LinkedIn, WHOIS, Reddit, Glassdoor, and Trustpilot.
"""

import asyncio
import re
import logging
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse, quote

import httpx
import whois
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
REDDIT_HEADERS = {
    "User-Agent": "ShadowTraceBot/1.0 (hackathon project; contact@shadowtrace.ai)"
}


async def discover_company_links(url: str) -> dict:
    """Agentic discovery: finds social and review links from a single website URL."""
    discovered = {
        "website": url,
        "linkedin": None,
        "twitter": None,
        "github": None,
        "crunchbase": None,
        "company_name": None
    }
    try:
        if not url.startswith("http"):
            url = "https://" + url

        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15) as client:
            res = await client.get(url)
            soup = BeautifulSoup(res.text, "html.parser")

            # 1. Company name
            og_name = soup.find("meta", property="og:site_name")
            if og_name and og_name.get("content"):
                discovered["company_name"] = og_name["content"].strip()
            elif soup.title:
                discovered["company_name"] = re.split(r'[-|–|:]', soup.title.string)[0].strip()

            # 2. Social links
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "linkedin.com/company/" in href and not discovered["linkedin"]:
                    discovered["linkedin"] = href if href.startswith("http") else "https://" + href.lstrip("/")
                if ("twitter.com/" in href or "x.com/" in href) and not discovered["twitter"]:
                    discovered["twitter"] = href
                if "github.com/" in href and not discovered["github"]:
                    discovered["github"] = href

            # 3. Crunchbase heuristic
            if discovered["company_name"]:
                slug = re.sub(r'[^a-z0-9]+', '-', discovered["company_name"].lower()).strip('-')
                discovered["crunchbase"] = f"https://www.crunchbase.com/organization/{slug}"

    except Exception as e:
        logger.warning(f"Link discovery failed for {url}: {e}")
    return discovered


async def scrape_reviews(company_name: str, raw_data: dict):
    """Multi-platform review scraper using Google News RSS as proxy for blocked sites."""
    if not company_name or company_name == "Unknown":
        raw_data["reviews"] = _empty_reviews()
        return

    reviews = _empty_reviews()
    encoded_name = quote(company_name)

    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=20) as client:

        # ── 1. Reddit via JSON API ────────────────────────────────────────────
        try:
            reddit_url = f"https://www.reddit.com/search.json?q={encoded_name}&sort=relevance&limit=15&type=link"
            res = await client.get(reddit_url, headers=REDDIT_HEADERS)
            if res.status_code == 200:
                data = res.json()
                posts = data.get("data", {}).get("children", [])
                reviews["reddit"]["mentions"] = len(posts)
                neg_kw = ["scam", "fraud", "fake", "avoid", "warning", "worst", "bad", "cheat", "liar", "exposed"]
                for post in posts:
                    p = post.get("data", {})
                    title = p.get("title", "").lower()
                    post_info = {
                        "title": p.get("title", ""),
                        "score": p.get("score", 0),
                        "sub": p.get("subreddit", "")
                    }
                    if any(kw in title for kw in neg_kw):
                        reviews["reddit"]["negative_posts"].append(post_info)
                    else:
                        reviews["reddit"]["positive_posts"].append(post_info)
            else:
                logger.warning(f"Reddit returned {res.status_code}")
        except Exception as e:
            logger.warning(f"Reddit scrape failed: {e}")

        # ── 2. Glassdoor via Google News RSS (direct fetch blocks bots) ───────
        try:
            gd_query = quote(f"{company_name} glassdoor rating reviews")
            gd_rss = f"https://news.google.com/rss/search?q={gd_query}&hl=en-IN&gl=IN&ceid=IN:en"
            res = await client.get(gd_rss)
            soup = BeautifulSoup(res.text, "xml")
            for item in soup.find_all("item")[:5]:
                title = item.find("title")
                desc = item.find("description")
                text = (title.text if title else "") + " " + (desc.text if desc else "")
                # Look for rating pattern like "3.8/5" or "4.1 out of 5"
                match = re.search(r'(\d\.\d)\s*(?:out of 5|/5|\s*stars)', text, re.IGNORECASE)
                if match:
                    reviews["glassdoor"]["rating"] = float(match.group(1))
                    # Estimate review count
                    count_match = re.search(r'(\d[\d,]+)\s*reviews', text, re.IGNORECASE)
                    if count_match:
                        reviews["glassdoor"]["review_count"] = int(count_match.group(1).replace(",", ""))
                    break
        except Exception as e:
            logger.warning(f"Glassdoor RSS failed: {e}")

        # ── 3. Trustpilot via direct fetch + Google RSS fallback ──────────────
        try:
            # Try direct fetch first
            tp_slug = re.sub(r'[^a-z0-9]', '', company_name.lower())
            tp_url = f"https://www.trustpilot.com/review/{tp_slug}.com"
            res = await client.get(tp_url, timeout=10)
            if res.status_code == 200 and "trustpilot" in res.url.host:
                soup = BeautifulSoup(res.text, "html.parser")
                desc = soup.find("meta", property="og:description")
                if desc and desc.get("content"):
                    match = re.search(r'(\d\.\d)\s*(?:out of 5|stars)', desc["content"], re.IGNORECASE)
                    if match:
                        reviews["trustpilot"]["rating"] = float(match.group(1))
                        reviews["trustpilot"]["found"] = True
        except Exception:
            pass

        # Trustpilot RSS fallback if direct fetch failed
        if not reviews["trustpilot"]["found"]:
            try:
                tp_query = quote(f"{company_name} trustpilot rating")
                tp_rss = f"https://news.google.com/rss/search?q={tp_query}"
                res = await client.get(tp_rss)
                soup = BeautifulSoup(res.text, "xml")
                for item in soup.find_all("item")[:5]:
                    text = (item.find("title").text if item.find("title") else "") + \
                           (item.find("description").text if item.find("description") else "")
                    match = re.search(r'(\d\.\d)\s*(?:out of 5|/5|stars)', text, re.IGNORECASE)
                    if match and "trustpilot" in text.lower():
                        reviews["trustpilot"]["rating"] = float(match.group(1))
                        reviews["trustpilot"]["found"] = True
                        break
            except Exception as e:
                logger.warning(f"Trustpilot RSS fallback failed: {e}")

        # ── 4. Google News Sentiment ──────────────────────────────────────────
        try:
            news_query = quote(f"{company_name} reviews complaints")
            rss_url = f"https://news.google.com/rss/search?q={news_query}&hl=en-IN&gl=IN&ceid=IN:en"
            res = await client.get(rss_url)
            soup = BeautifulSoup(res.text, "xml")
            items = soup.find_all("item")
            reviews["google_news_sentiment"]["total"] = len(items)
            neg_kw = ["scam", "fraud", "fake", "lawsuit", "complaint", "arrested", "cheated"]
            for item in items:
                title = item.find("title")
                if title:
                    if any(kw in title.text.lower() for kw in neg_kw):
                        reviews["google_news_sentiment"]["negative"] += 1
                    else:
                        reviews["google_news_sentiment"]["positive"] += 1
        except Exception as e:
            logger.warning(f"Google News sentiment failed: {e}")

    # ── Overall sentiment calculation ─────────────────────────────────────────
    neg = (len(reviews["reddit"]["negative_posts"]) +
           reviews["google_news_sentiment"]["negative"])
    if reviews["trustpilot"].get("rating") and reviews["trustpilot"]["rating"] < 3.0:
        neg += 2
    if reviews["glassdoor"].get("rating") and reviews["glassdoor"]["rating"] < 3.0:
        neg += 1

    total_signals = (reviews["reddit"]["mentions"] +
                     reviews["google_news_sentiment"]["total"])

    if neg >= 3:
        reviews["overall_sentiment"] = "NEGATIVE"
    elif neg > 0:
        reviews["overall_sentiment"] = "MIXED"
    elif total_signals > 0:
        reviews["overall_sentiment"] = "POSITIVE"
    else:
        reviews["overall_sentiment"] = "NO_DATA"

    raw_data["reviews"] = reviews
    logger.info(f"Reviews scraped for '{company_name}': Reddit={reviews['reddit']['mentions']}, "
                f"Trustpilot={reviews['trustpilot']['found']}, Glassdoor={reviews['glassdoor']['rating']}")


def _empty_reviews() -> dict:
    return {
        "reddit": {"mentions": 0, "negative_posts": [], "positive_posts": []},
        "glassdoor": {"rating": None, "review_count": None},
        "trustpilot": {"rating": None, "found": False},
        "google_news_sentiment": {"total": 0, "negative": 0, "positive": 0},
        "overall_sentiment": "NO_DATA"
    }


async def scrape_company(url: str, linkedin_url: str = None, gst_number: str = None) -> dict:
    """Main entry point. Accepts one URL, auto-discovers the rest."""
    raw_data = {
        "pages": [], "summary": {}, "whois": {}, "linkedin": {},
        "news": [], "reviews": {}, "errors": [], "discovered_links": {}
    }

    if not url.startswith("http"):
        url = "https://" + url

    # Step 1: Auto-discover
    discovered = await discover_company_links(url)
    raw_data["discovered_links"] = discovered

    # Step 2: Resolve targets
    final_linkedin = linkedin_url or discovered.get("linkedin")
    company_name = discovered.get("company_name") or urlparse(url).netloc.replace("www.", "").split(".")[0].title()
    raw_data["url_linkedin"] = final_linkedin
    raw_data["company_name"] = company_name

    # Step 3: Run all scrapers concurrently
    tasks = [
        scrape_website(url, raw_data),
        scrape_whois(url, raw_data),
        scrape_google_news(url, company_name, raw_data),
        scrape_reviews(company_name, raw_data),
    ]
    if final_linkedin:
        tasks.append(scrape_linkedin(final_linkedin, raw_data))

    await asyncio.gather(*tasks, return_exceptions=True)

    # Step 4: Build summary
    summary = build_summary(raw_data)
    raw_data["summary"] = summary
    raw_data["website_text"] = summary.get("combined_text", "")
    raw_data["domain_age_days"] = raw_data.get("whois", {}).get("domain_age_days", 0)
    raw_data["url"] = url

    return raw_data


async def scrape_website(url: str, raw_data: dict):
    try:
        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15) as client:
            res = await client.get(url)
            soup = BeautifulSoup(res.text, "html.parser")
            text = extract_clean_text(soup)
            raw_data["pages"].append({
                "url": url,
                "source": "website",
                "text": text,
                "title": soup.title.string.strip() if soup.title else "",
                "links": [a["href"] for a in soup.find_all("a", href=True)][:50],
                "meta": {t.get("name", t.get("property", "")): t.get("content", "")
                         for t in soup.find_all("meta") if t.get("content")}
            })

            # Try About page
            about_url = _find_about_url(soup, url)
            if about_url:
                try:
                    res2 = await client.get(about_url)
                    soup2 = BeautifulSoup(res2.text, "html.parser")
                    raw_data["pages"].append({
                        "url": about_url, "source": "about_page",
                        "text": extract_clean_text(soup2), "title": "About"
                    })
                except Exception:
                    pass
    except Exception as e:
        logger.error(f"Website scrape error: {e}")
        raw_data["errors"].append({"source": "website", "error": str(e)})


def _find_about_url(soup, base_url):
    base = urlparse(base_url)
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        if any(kw in href for kw in ["/about", "/company", "/team", "/who-we-are"]):
            if a["href"].startswith("http"):
                return a["href"]
            return f"{base.scheme}://{base.netloc}{a['href']}"
    return None


def extract_clean_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(separator=" ", strip=True))[:8000]


async def scrape_whois(url: str, raw_data: dict):
    try:
        domain = urlparse(url if "://" in url else "https://" + url).netloc.replace("www.", "")
        loop = asyncio.get_event_loop()
        w = await loop.run_in_executor(None, whois.whois, domain)

        creation = w.creation_date
        if isinstance(creation, list):
            creation = creation[0]

        expiry = w.expiration_date
        if isinstance(expiry, list):
            expiry = expiry[0]

        age_days = (datetime.now() - creation).days if isinstance(creation, datetime) else 365

        raw_data["whois"] = {
            "domain": domain,
            "registrar": getattr(w, "registrar", "Unknown"),
            "creation_date": creation.isoformat() if isinstance(creation, datetime) else None,
            "creation_year": creation.year if isinstance(creation, datetime) else None,
            "expiry_date": expiry.isoformat() if isinstance(expiry, datetime) else None,
            "country": getattr(w, "country", "Unknown"),
            "org": getattr(w, "org", "Unknown"),
            "domain_age_days": age_days,
        }
    except Exception as e:
        logger.warning(f"WHOIS failed: {e}")
        raw_data["whois"] = {"domain_age_days": 365, "error": str(e)}


async def scrape_linkedin(linkedin_url: str, raw_data: dict):
    """
    LinkedIn blocks all scrapers. If URL was provided, trust it exists.
    Try to get whatever text we can, but never penalize for being blocked.
    """
    base = {
        "url": linkedin_url,
        "profile_exists": True,  # ALWAYS True when URL is explicitly provided
        "raw_text": "",
        "employee_count": None,
        "founded_year": None,
        "scraped_at": datetime.now().isoformat(),
    }
    try:
        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15) as client:
            res = await client.get(linkedin_url)
            text = extract_clean_text(BeautifulSoup(res.text, "html.parser"))
            # Check for login wall
            is_blocked = any(kw in text.lower() for kw in
                             ["authwall", "sign in", "join now", "log in to see", "join linkedin"])
            if not is_blocked:
                base["raw_text"] = text[:3000]
                base["employee_count"] = _extract_employee_count(text)
                base["founded_year"] = _extract_year(text, ["founded", "established", "since"])
            else:
                logger.info("LinkedIn blocked scraping (expected) — profile_exists still True")
    except Exception as e:
        logger.warning(f"LinkedIn fetch error (URL still trusted): {e}")

    raw_data["linkedin"] = base


async def scrape_google_news(url: str, company_name: str, raw_data: dict):
    try:
        query = quote(company_name or urlparse(url).netloc.split(".")[0])
        rss_url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
        async with httpx.AsyncClient(headers=HEADERS, timeout=10) as client:
            res = await client.get(rss_url)
            soup = BeautifulSoup(res.text, "xml")
            articles = []
            neg_kw = ["fraud", "scam", "fake", "cheated", "lawsuit", "fir", "arrested"]
            for item in soup.find_all("item")[:10]:
                title = item.find("title")
                pub = item.find("pubDate")
                link = item.find("link")
                t = title.text if title else ""
                articles.append({
                    "title": t,
                    "published": pub.text if pub else "",
                    "url": link.text if link else "",
                    "fraud_mention": any(kw in t.lower() for kw in neg_kw)
                })
            raw_data["news"] = articles
            raw_data["news_count"] = len(articles)
            raw_data["fraud_news_count"] = sum(1 for a in articles if a["fraud_mention"])
    except Exception as e:
        logger.warning(f"Google News failed: {e}")
        raw_data["news"] = []
        raw_data["news_count"] = 0
        raw_data["fraud_news_count"] = 0


def build_summary(raw_data: dict) -> dict:
    combined = ""
    for page in raw_data.get("pages", []):
        combined += f"\n\n[{page['source']}]\n{page['text']}"
    if raw_data.get("linkedin", {}).get("raw_text"):
        combined += f"\n\n[LinkedIn]\n{raw_data['linkedin']['raw_text']}"

    return {
        "combined_text": combined[:10000],
        "whois_creation_year": raw_data.get("whois", {}).get("creation_year"),
        "domain_age_days": raw_data.get("whois", {}).get("domain_age_days"),
        "news_article_count": raw_data.get("news_count", 0),
        "fraud_news_count": raw_data.get("fraud_news_count", 0),
        "linkedin_employees": raw_data.get("linkedin", {}).get("employee_count"),
        "scraped_sources": [p["source"] for p in raw_data.get("pages", [])],
        "reviews": raw_data.get("reviews", {}),
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_employee_count(text: str) -> Optional[int]:
    patterns = [
        r"(\d[\d,]+)\s*\+?\s*(?:employees|staff|people|team members)",
        r"team\s+of\s+(\d[\d,]+)",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            try:
                return int(m.group(1).replace(",", ""))
            except ValueError:
                pass
    return None


def _extract_year(text: str, keywords: list) -> Optional[int]:
    for kw in keywords:
        m = re.search(rf"{kw}\D{{0,20}}(19|20)\d{{2}}", text, re.IGNORECASE)
        if m:
            y = re.search(r"(19|20)\d{2}", m.group())
            if y:
                return int(y.group())
    return None


# ── Legacy shim ───────────────────────────────────────────────────────────────
class ScraperEngine:
    def scrape_all(self, url: str, linkedin_url: str = None) -> dict:
        return asyncio.run(scrape_company(url, linkedin_url))