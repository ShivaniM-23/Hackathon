import whois
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import requests
import datetime
import logging

logger = logging.getLogger(__name__)

class ScraperEngine:
    def __init__(self):
        pass

    def scrape_all(self, url: str, linkedin_url: str = None) -> dict:
        data = {
            "website_text": "",
            "domain_age_days": 0,
            "registrar": "",
            "linkedin_data": "Mock LinkedIn Data: 50 employees" if linkedin_url else None
        }

        # 1. WHOIS
        try:
            domain = urlparse(url).netloc or url
            if domain.startswith("www."):
                domain = domain[4:]
            
            w = whois.whois(domain)
            creation_date = w.creation_date
            if isinstance(creation_date, list):
                creation_date = creation_date[0]
            
            if creation_date:
                age = (datetime.datetime.now() - creation_date).days
                data["domain_age_days"] = age
            data["registrar"] = w.registrar
        except Exception as e:
            logger.warning(f"WHOIS lookup failed for {url}: {e}")
            data["domain_age_days"] = 100 # Mock fallback

        # 2. Website Text (using requests + BS4 for speed in MVP, Playwright can be swapped in)
        try:
            if not url.startswith("http"):
                url = "http://" + url
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, "html.parser")
            # Extract basic text
            text = " ".join([p.get_text() for p in soup.find_all(['p', 'h1', 'h2', 'h3'])])
            data["website_text"] = text[:5000] # Limit length for SLM
        except Exception as e:
            logger.warning(f"Failed to scrape website {url}: {e}")
            data["website_text"] = "Mock Website Text: We are a leading AI startup founded in 2015. We have 50 employees and are trusted by Fortune 500 companies. Our US office is located in San Francisco."

        return data
