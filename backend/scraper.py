"""
ShadowTrace AI — Scraper (Discovery & Review Edition)
Collects raw data from: company website, LinkedIn, WHOIS, Reddit, Glassdoor, and Trustpilot.
"""

import asyncio
import re
import logging
from datetime import datetime
from collections import deque
from typing import Optional
from urllib.parse import urljoin, urldefrag, urlparse, quote

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
MAX_WEBSITE_PAGES = 100
MAX_CRAWL_DEPTH = 5
MAX_PAGE_TEXT_CHARS = 12000
PRIORITY_PATH_KEYWORDS = [
    "about", "company", "who-we-are", "leadership", "team", "contact",
    "location", "office", "career", "clients", "customers", "case-stud",
    "partner", "services", "solutions", "industries", "privacy", "terms",
]


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
                pos_kw = ["great", "awesome", "good", "best", "love", "recommend", "amazing", "excellent", "legit"]
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
                    elif any(kw in title for kw in pos_kw):
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
            soup = BeautifulSoup(res.text, "html.parser")
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
                soup = BeautifulSoup(res.text, "html.parser")
                for item in soup.find_all("item")[:5]:
                    text = (item.find("title").text if item.find("title") else "") +                            (item.find("description").text if item.find("description") else "")
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
            soup = BeautifulSoup(res.text, "html.parser")
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


async def scrape_extended_sources(company_name: str, url: str, raw_data: dict):
    """Scrapes 10+ additional sources beyond the basics via Google News RSS proxies."""
    encoded = quote(company_name)
    results = {}
    
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15) as client:
        # 1. IndiaMART / Justdial presence (for Indian companies)
        try:
            jd_rss = f"https://news.google.com/rss/search?q={encoded}+justdial+reviews"
            res = await client.get(jd_rss)
            soup = BeautifulSoup(res.text, "xml")
            results["justdial"] = {"found": len(soup.find_all("item")) > 0}
        except: results["justdial"] = {"found": False}
        
        # 2. AmbitionBox (India Glassdoor alternative)
        try:
            ab_rss = f"https://news.google.com/rss/search?q={encoded}+ambitionbox+rating"
            res = await client.get(ab_rss)
            soup = BeautifulSoup(res.text, "xml")
            rating = None
            for item in soup.find_all("item")[:3]:
                text = item.find("title").text if item.find("title") else ""
                m = re.search(r'(\d\.\d)\s*(?:/5|out of 5|stars)', text)
                if m: rating = float(m.group(1)); break
            results["ambitionbox"] = {"rating": rating, "found": rating is not None}
        except: results["ambitionbox"] = {"rating": None, "found": False}
        
        # 3. G2 / Capterra (for SaaS companies)
        try:
            g2_rss = f"https://news.google.com/rss/search?q={encoded}+G2+software+reviews"
            res = await client.get(g2_rss)
            soup = BeautifulSoup(res.text, "xml")
            results["g2"] = {"found": len(soup.find_all("item")) > 2}
        except: results["g2"] = {"found": False}
        
        # 4. LinkedIn news mentions
        try:
            li_rss = f"https://news.google.com/rss/search?q={encoded}+linkedin"
            res = await client.get(li_rss)
            soup = BeautifulSoup(res.text, "xml")
            results["linkedin_news"] = {"mentions": len(soup.find_all("item"))}
        except: results["linkedin_news"] = {"mentions": 0}
        
        # 5. Crunchbase presence check via news
        try:
            cb_rss = f"https://news.google.com/rss/search?q={encoded}+crunchbase+funding"
            res = await client.get(cb_rss)
            soup = BeautifulSoup(res.text, "xml")
            results["crunchbase"] = {"found": len(soup.find_all("item")) > 0}
        except: results["crunchbase"] = {"found": False}
        
        # 6. YouTube presence (company channel or mentions)
        try:
            yt_rss = f"https://news.google.com/rss/search?q={encoded}+youtube+channel"
            res = await client.get(yt_rss)
            soup = BeautifulSoup(res.text, "xml")
            results["youtube"] = {"found": len(soup.find_all("item")) > 0}
        except: results["youtube"] = {"found": False}
        
        # 7. Government/regulatory mentions (MCA, ROC for Indian companies)
        try:
            mca_rss = f"https://news.google.com/rss/search?q={encoded}+MCA+ROC+registered+company"
            res = await client.get(mca_rss)
            soup = BeautifulSoup(res.text, "xml")
            results["regulatory"] = {"found": len(soup.find_all("item")) > 0}
        except: results["regulatory"] = {"found": False}
        
        # 8. Job portals presence (Naukri, Indeed, LinkedIn Jobs)
        try:
            jobs_rss = f"https://news.google.com/rss/search?q={encoded}+jobs+hiring+careers"
            res = await client.get(jobs_rss)
            soup = BeautifulSoup(res.text, "xml")
            results["job_portals"] = {"found": len(soup.find_all("item")) > 2,
                                       "count": len(soup.find_all("item"))}
        except: results["job_portals"] = {"found": False, "count": 0}
        
        # 9. News coverage volume (general press)
        try:
            news_rss = f"https://news.google.com/rss/search?q={encoded}&hl=en-IN"
            res = await client.get(news_rss)
            soup = BeautifulSoup(res.text, "xml")
            results["general_news"] = {"count": len(soup.find_all("item"))}
        except: results["general_news"] = {"count": 0}
        
        # 10. ScamAdviser / fraud databases via news search
        try:
            scam_rss = f"https://news.google.com/rss/search?q={encoded}+scam+fraud+complaint+cheated"
            res = await client.get(scam_rss)
            soup = BeautifulSoup(res.text, "xml")
            neg_items = soup.find_all("item")
            results["fraud_signals"] = {
                "count": len(neg_items),
                "titles": [i.find("title").text for i in neg_items[:3] if i.find("title")]
            }
        except: results["fraud_signals"] = {"count": 0, "titles": []}
    
    raw_data["extended_sources"] = results
    logger.info(f"Extended sources scraped: {list(results.keys())}")


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
        scrape_wikipedia(company_name, raw_data),
        scrape_extended_sources(company_name, url, raw_data),
    ]
    if final_linkedin:
        tasks.append(scrape_linkedin(final_linkedin, raw_data))

    await asyncio.gather(*tasks, return_exceptions=True)

    # Step 4: Build summary
    summary = build_summary(raw_data)
    summary["extended_sources"] = raw_data.get("extended_sources", {})
    raw_data["summary"] = summary
    raw_data["website_text"] = summary.get("combined_text", "")
    raw_data["domain_age_days"] = raw_data.get("whois", {}).get("domain_age_days", 0)
    raw_data["url"] = url

    return raw_data


async def scrape_website(url: str, raw_data: dict):
    try:
        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15) as client:
            start_url = _normalize_url(url)
            base_host = _registered_host(urlparse(start_url).netloc)
            queue = deque([(start_url, 0)])
            seen = set()

            while queue and len(raw_data["pages"]) < MAX_WEBSITE_PAGES:
                current_url, depth = queue.popleft()
                if current_url in seen:
                    continue
                seen.add(current_url)

                try:
                    res = await client.get(current_url)
                    content_type = res.headers.get("content-type", "")
                    if res.status_code >= 400 or "text/html" not in content_type:
                        continue
                except Exception as page_error:
                    logger.debug(f"Skipping {current_url}: {page_error}")
                    continue

                soup = BeautifulSoup(res.text, "html.parser")
                links = _extract_internal_links(soup, current_url, base_host)
                source = "website" if current_url == start_url else _classify_page_source(current_url)

                raw_data["pages"].append({
                    "url": current_url,
                    "source": source,
                    "text": extract_clean_text(soup),
                    "title": soup.title.string.strip() if soup.title and soup.title.string else "",
                    "links": links[:80],
                    "meta": {t.get("name", t.get("property", "")): t.get("content", "")
                             for t in soup.find_all("meta") if t.get("content")}
                })

                if depth >= MAX_CRAWL_DEPTH:
                    continue

                for link in _rank_links(links):
                    if link not in seen and len(seen) + len(queue) < MAX_WEBSITE_PAGES * 3:
                        queue.append((link, depth + 1))

            raw_data["crawl_stats"] = {
                "pages_scraped": len(raw_data["pages"]),
                "max_pages": MAX_WEBSITE_PAGES,
                "max_depth": MAX_CRAWL_DEPTH,
                "same_domain_only": True,
            }
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


def _normalize_url(url: str) -> str:
    if not url.startswith("http"):
        url = "https://" + url
    clean, _ = urldefrag(url)
    return clean.rstrip("/")


def _registered_host(hostname: str) -> str:
    host = hostname.lower().replace("www.", "")
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def _extract_internal_links(soup: BeautifulSoup, current_url: str, base_host: str) -> list[str]:
    links = []
    blocked_ext = (
        ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".zip",
        ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".mp4", ".mov",
    )
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        absolute = _normalize_url(urljoin(current_url, href))
        parsed = urlparse(absolute)
        if parsed.scheme not in ("http", "https"):
            continue
        if _registered_host(parsed.netloc) != base_host:
            continue
        if parsed.path.lower().endswith(blocked_ext):
            continue
        links.append(absolute)
    return list(dict.fromkeys(links))


def _rank_links(links: list[str]) -> list[str]:
    def score(link: str) -> tuple[int, int, str]:
        path = urlparse(link).path.lower()
        priority = 0 if any(kw in path for kw in PRIORITY_PATH_KEYWORDS) else 1
        return (priority, path.count("/"), link)
    return sorted(links, key=score)


def _classify_page_source(url: str) -> str:
    path = urlparse(url).path.lower()
    for key in PRIORITY_PATH_KEYWORDS:
        if key in path:
            return f"{key.replace('-', '_')}_page"
    return "site_page"


def extract_clean_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(separator=" ", strip=True))[:MAX_PAGE_TEXT_CHARS]


async def scrape_whois(url: str, raw_data: dict):
    try:
        domain = urlparse(url if "://" in url else "https://" + url).netloc.replace("www.", "")
        # Using the standard python-whois library call
        loop = asyncio.get_event_loop()
        w = await loop.run_in_executor(None, whois.whois, domain)

        if not w or not getattr(w, "creation_date", None):
            raise ValueError("WHOIS returned empty or invalid data")

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
        logger.warning(f"WHOIS failed for {url}: {e}")
        raw_data["whois"] = {"domain_age_days": 365, "error": str(e)}


async def scrape_wikipedia(company_name: str, raw_data: dict):
    """Check Wikipedia for company presence, a strong indicator of an established global entity."""
    raw_data["wikipedia"] = {"found": False, "url": None, "summary": None}
    if not company_name or company_name.lower() == "unknown":
        return

    try:
        # Wikipedia API search
        search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={quote(company_name)}&utf8=&format=json"
        async with httpx.AsyncClient(headers=HEADERS, timeout=10) as client:
            res = await client.get(search_url)
            if res.status_code == 200:
                data = res.json()
                search_results = data.get("query", {}).get("search", [])
                
                # Check if the first result is a good match
                if search_results:
                    first_result = search_results[0]
                    title = first_result.get("title", "")
                    
                    # Ensure it's not a completely unrelated page by doing a loose match
                    # E.g. search "Relanto" might return something else if it doesn't exist
                    company_words = set(re.findall(r'\w+', company_name.lower()))
                    title_words = set(re.findall(r'\w+', title.lower()))
                    
                    # If at least one significant word matches
                    if company_words.intersection(title_words):
                        # Fetch the page summary
                        page_id = first_result.get("pageid")
                        summary_url = f"https://en.wikipedia.org/w/api.php?action=query&prop=extracts&exintro&explaintext&pageids={page_id}&format=json"
                        res_sum = await client.get(summary_url)
                        if res_sum.status_code == 200:
                            sum_data = res_sum.json()
                            pages = sum_data.get("query", {}).get("pages", {})
                            if str(page_id) in pages:
                                extract = pages[str(page_id)].get("extract", "")
                                if len(extract) > 50: # Valid summary
                                    raw_data["wikipedia"] = {
                                        "found": True,
                                        "url": f"https://en.wikipedia.org/?curid={page_id}",
                                        "summary": extract[:1000]
                                    }
    except Exception as e:
        logger.warning(f"Wikipedia scrape failed: {e}")


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
            soup = BeautifulSoup(res.text, "html.parser")
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
        "combined_text": combined[:30000],
        "whois_creation_year": raw_data.get("whois", {}).get("creation_year"),
        "domain_age_days": raw_data.get("whois", {}).get("domain_age_days"),
        "news_article_count": raw_data.get("news_count", 0),
        "fraud_news_count": raw_data.get("fraud_news_count", 0),
        "linkedin_employees": raw_data.get("linkedin", {}).get("employee_count"),
        "scraped_sources": [p["source"] for p in raw_data.get("pages", [])],
        "pages_scraped": len(raw_data.get("pages", [])),
        "crawl_stats": raw_data.get("crawl_stats", {}),
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
