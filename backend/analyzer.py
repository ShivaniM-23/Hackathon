"""
ShadowTrace AI — Analyzer
Uses a Small Language Model (SLM) to extract structured fields from scraped data
and detect contradictions between claims and evidence.

Supports: Phi-3 Mini (local Ollama), Mistral 7B, or any OpenAI-compatible endpoint.
Falls back to rule-based extraction if no LLM available.
"""

import json
import re
import httpx
import logging
import asyncio
from typing import Optional

logger = logging.getLogger(__name__)

# ── LLM config — change OLLAMA_MODEL to switch models ────────────────────────
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "phi3"           # or "mistral", "gemma2:2b"
OLLAMA_TIMEOUT = 60

LLM_AVAILABLE = True            # Set to False to force rule-based mode


async def analyze_company(raw_data: dict) -> dict:
    """
    Main analysis pipeline:
    1. Extract structured fields from scraped text (LLM or rule-based)
    2. Detect contradictions between claims and evidence
    3. Return a structured dossier
    """
    summary = raw_data.get("summary", {})
    whois_data = raw_data.get("whois", {})
    combined_text = summary.get("combined_text", "")

    # ── Step 1: Extract structured fields ────────────────────────────────────
    if LLM_AVAILABLE:
        extracted = await llm_extract(combined_text)
    else:
        extracted = rule_based_extract(combined_text, raw_data)

    # Merge WHOIS data (always reliable, no LLM needed)
    extracted["domain_created"] = str(whois_data.get("creation_year", "Unknown"))
    extracted["domain_age_days"] = whois_data.get("domain_age_days")
    extracted["registrar"] = whois_data.get("registrar", "Unknown")

    # Merge LinkedIn data
    linkedin = raw_data.get("linkedin", {})
    if linkedin.get("employee_count"):
        extracted["employee_count_linkedin"] = linkedin["employee_count"]

    # Pass linkedin_profile_exists so trust_score doesn't penalize blocked-but-provided URLs
    extracted["linkedin_profile_exists"] = linkedin.get("profile_exists", False)

    # Also pass reviews data for trust scoring
    extracted["_reviews"] = raw_data.get("reviews", {})

    # ── Step 2: Detect contradictions ────────────────────────────────────────
    contradictions = detect_contradictions(extracted, raw_data)

    # ── Step 3: Build dossier ─────────────────────────────────────────────────
    company_name = (
        extracted.get("company_name")
        or _extract_company_name_from_pages(raw_data.get("pages", []))
        or "Unknown Company"
    )

    return {
        "company_name": company_name,
        "extracted": extracted,
        "contradictions": contradictions,
        "analysis_method": "llm" if LLM_AVAILABLE else "rule_based",
        "raw_data_summary": raw_data  # Pass through for scoring
    }


# ── LLM extraction (Ollama) ───────────────────────────────────────────────────

EXTRACTION_PROMPT = """You are a business intelligence analyst. Extract the following information from the company text below.

Return ONLY a valid JSON object with these exact keys. Use null if information is not found.

{{
  "company_name": "string or null",
  "founding_year": "string or null (e.g. '2015')",
  "employee_count_claimed": "string or null (e.g. '200+')",
  "headquarters": "string or null",
  "addresses": ["list of addresses mentioned"],
  "directors": ["list of director/founder names"],
  "claimed_clients": ["list of companies claimed as clients"],
  "certifications": ["list of certifications mentioned"],
  "funding": "string or null (e.g. 'Series A, $5M')",
  "has_linkedin": false,
  "has_twitter": false,
  "tagline": "string or null"
}}

Company text:
{text}

Return only the JSON object, no other text."""


async def llm_extract(text: str) -> dict:
    """
    Calls local Ollama endpoint to extract structured data.
    Falls back to rule-based on failure.
    """
    prompt = EXTRACTION_PROMPT.format(text=text[:4000])  # Keep within context window

    try:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1},  # Low temp for factual extraction
                },
            )
            data = response.json()
            raw_output = data.get("response", "")

            # Strip markdown fences
            raw_output = re.sub(r"```json|```", "", raw_output).strip()
            
            # Extract just the JSON object (everything between first { and last })
            match = re.search(r'\{.*\}', raw_output, re.DOTALL)
            if match:
                raw_output = match.group()
            
            # Remove trailing commas before } or ] (invalid JSON)
            raw_output = re.sub(r',\s*([}\]])', r'\1', raw_output)
            
            parsed = json.loads(raw_output)
            return parsed

    except (httpx.ConnectError, httpx.TimeoutException):
        logger.warning("Ollama not running. Using rule-based extraction.")
        return rule_based_extract(text, {})

    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(f"LLM returned bad JSON: {e}. Using rule-based extraction.")
        return rule_based_extract(text, {})


# ── Rule-based extraction (fallback) ─────────────────────────────────────────

def rule_based_extract(text: str, raw_data: dict) -> dict:
    """
    Regex-based extraction when LLM is unavailable.
    Covers the most common patterns in company websites.
    """
    return {
        "company_name": None,
        "founding_year": _re_founding_year(text),
        "employee_count_claimed": _re_employee_count(text),
        "headquarters": _re_headquarters(text),
        "addresses": _re_addresses(text),
        "directors": [],
        "claimed_clients": _re_client_names(text),
        "certifications": _re_certifications(text),
        "funding": None,
        "has_linkedin": "linkedin.com" in text.lower(),
        "has_twitter": "twitter.com" in text.lower() or "x.com" in text.lower(),
        "tagline": None,
    }


def _re_founding_year(text: str) -> Optional[str]:
    patterns = [
        r"(?:founded|established|incorporated|since|started)\s+(?:in\s+)?((19|20)\d{2})",
        r"((19|20)\d{2})\s+(?:founded|established)",
        r"©\s*((19|20)\d{2})",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def _re_employee_count(text: str) -> Optional[str]:
    patterns = [
        r"([\d,]+)\s*\+?\s*(?:employees|staff|team members|professionals)",
        r"team of\s+([\d,]+)",
        r"over\s+([\d,]+)\s+(?:employees|people)",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1).replace(",", "")
    return None


def _re_headquarters(text: str) -> Optional[str]:
    m = re.search(
        r"(?:headquartered|located|based)\s+in\s+([A-Z][a-zA-Z\s,]+?)(?:\.|,|\n)",
        text,
        re.IGNORECASE,
    )
    return m.group(1).strip() if m else None


def _re_addresses(text: str) -> list[str]:
    # Look for PIN codes (Indian) or ZIP codes
    addresses = re.findall(r"[A-Z][\w\s,.-]{10,60}(?:\d{6}|\d{5})", text)
    return [a.strip() for a in addresses[:3]]


def _re_client_names(text: str) -> list[str]:
    """Look for Fortune 500 / well-known company names mentioned as clients."""
    known_companies = [
        "Infosys", "TCS", "Wipro", "HCL", "Accenture", "Deloitte",
        "Google", "Microsoft", "Amazon", "Apple", "Meta", "IBM",
        "HDFC", "ICICI", "Reliance", "Tata", "Mahindra", "Bajaj",
    ]
    found = [c for c in known_companies if c.lower() in text.lower()]
    return found


def _re_certifications(text: str) -> list[str]:
    certs = ["ISO 9001", "ISO 27001", "ISO 14001", "SOC 2", "PCI DSS", "GDPR", "CMMI"]
    return [c for c in certs if c.lower() in text.lower()]


# ── Contradiction detection ───────────────────────────────────────────────────

def detect_contradictions(extracted: dict, raw_data: dict) -> list[dict]:
    """
    Compares claimed values against scraped evidence.
    Returns a list of contradiction objects for the dashboard table.
    """
    contradictions = []
    summary = raw_data.get("summary", {})
    whois_data = raw_data.get("whois", {})

    # ── Check 1: LinkedIn Presence ────────────────────────────────────────────
    linkedin_input_url = raw_data.get("url_linkedin") or raw_data.get("linkedin", {}).get("url")
    linkedin_scraped = raw_data.get("linkedin", {}).get("profile_exists", False)

    if not linkedin_input_url and not linkedin_scraped:
        contradictions.append({
            "field": "LinkedIn Presence",
            "claimed": "Active company page link found on website",
            "evidence": "No valid LinkedIn company page found",
            "severity": "MEDIUM",
        })

    # ── Check 2: Founding year vs domain creation ─────────────────────────────
    founding_year_str = extracted.get("founding_year")
    domain_year = whois_data.get("creation_year")

    if founding_year_str and domain_year:
        m = re.search(r"(19|20)\d{2}", str(founding_year_str))
        if m:
            founding_year = int(m.group())
            if domain_year > founding_year + 2:
                contradictions.append({
                    "field": "Company Age",
                    "claimed": f"Founded in {founding_year}",
                    "evidence": f"Domain registered in {domain_year} (WHOIS)",
                    "severity": "HIGH",
                })

    # ── Check 3: Employee count ───────────────────────────────────────────────
    emp_claimed = extracted.get("employee_count_claimed")
    emp_linkedin = extracted.get("employee_count_linkedin")

    if emp_claimed and emp_linkedin:
        try:
            claimed_n = int(str(emp_claimed).replace("+", "").replace(",", ""))
            linkedin_n = int(str(emp_linkedin).replace("+", "").replace(",", ""))
            ratio = claimed_n / max(linkedin_n, 1)

            if ratio > 5:
                contradictions.append({
                    "field": "Headcount",
                    "claimed": f"{emp_claimed} employees",
                    "evidence": f"LinkedIn shows {emp_linkedin} employees",
                    "severity": "HIGH" if ratio > 10 else "MEDIUM",
                })
        except (ValueError, ZeroDivisionError):
            pass

    # ── Check 4: Client claims ────────────────────────────────────────────────
    claimed_clients = extracted.get("claimed_clients", [])
    if len(claimed_clients) > 0 and raw_data.get("news", []) == []:
        contradictions.append({
            "field": "Client Verification",
            "claimed": f"Works with {', '.join(claimed_clients[:2])}",
            "evidence": "No external news or press mentions found for these clients",
            "severity": "MEDIUM",
        })

    # ── Check 5: Domain Age (General Risk) ────────────────────────────────────
    domain_age_days = whois_data.get("domain_age_days", 365)
    if domain_age_days < 90:
        contradictions.append({
            "field": "Domain Reputation",
            "claimed": "Established business website",
            "evidence": f"Domain registered only {domain_age_days} days ago",
            "severity": "HIGH",
        })

    # ── Check 5: Community Reputation (Reddit) ──────────────────────────────
    reviews = raw_data.get("reviews", {})
    reddit_negative = len(reviews.get("reddit", {}).get("negative_posts", []))
    if reddit_negative >= 3:
        contradictions.append({
            "field": "Community Reputation",
            "claimed": "Reputable company",
            "evidence": f"{reddit_negative} negative Reddit posts found mentioning fraud/scam",
            "severity": "HIGH"
        })

    # ── Check 6: Customer Reviews (Trustpilot) ────────────────────────────────
    trustpilot = reviews.get("trustpilot", {})
    if trustpilot.get("rating") and trustpilot["rating"] < 2.5:
        contradictions.append({
            "field": "Customer Reviews",
            "claimed": "Quality service provider", 
            "evidence": f"Trustpilot rating: {trustpilot['rating']}/5",
            "severity": "HIGH"
        })

    return contradictions


def _extract_company_name_from_pages(pages: list[dict]) -> Optional[str]:
    for page in pages:
        title = page.get("title", "")
        if title:
            # Remove common suffixes
            name = re.sub(
                r"\s*[-|–]\s*.+$|\s*(Pvt\.?\s*Ltd\.?|Inc\.?|LLC|Corp\.?|Limited).*",
                "",
                title,
                flags=re.IGNORECASE,
            ).strip()
            if 2 < len(name) < 60:
                return name
    return None

# ── Legacy Compatibility Layer ────────────────────────────────────────────────
class TrustScoreGenerator:
    def __init__(self):
        pass

    def generate_score(self, scraped_data: dict, extracted_data: dict) -> dict:
        # This is now handled by trust_score.py, but we provide a shim here
        # for any code still calling this method directly.
        from trust_score import calculate_trust_score
        dossier = {
            "trust_score": 0,
            "risk_level": "UNKNOWN",
            "contradictions": detect_contradictions(extracted_data, scraped_data),
            "extracted": extracted_data
        }
        score_result = calculate_trust_score(dossier)
        return {
            "trust_score": score_result["score"],
            "risk_level": score_result["risk_level"],
            "contradictions": dossier["contradictions"]
        }
