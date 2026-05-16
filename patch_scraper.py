import sys

with open("backend/scraper.py", "r", encoding="utf-8") as f:
    content = f.read()

before = content.split("async def scrape_reviews(company_name: str, raw_data: dict):")[0]

# Find the end of _empty_reviews to get the rest of the code
after = "async def scrape_company" + content.split("async def scrape_company")[1]

scrape_reviews_code = '''async def scrape_reviews(company_name: str, raw_data: dict):
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


'''

new_content = before + scrape_reviews_code + after
with open("backend/scraper.py", "w", encoding="utf-8") as f:
    f.write(new_content)
