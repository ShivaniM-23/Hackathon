import datetime

class TrustScoreGenerator:
    def __init__(self):
        pass

    def generate_score(self, scraped_data: dict, extracted_data: dict) -> dict:
        score = 100
        contradictions = []

        domain_age = scraped_data.get("domain_age_days", 0)
        founding_year_claim = extracted_data.get("founding_year")
        current_year = datetime.datetime.now().year

        # Check 1: Domain Age vs Founding Year
        if founding_year_claim:
            claimed_age_years = current_year - founding_year_claim
            actual_age_years = domain_age / 365.25

            if actual_age_years < 1 and claimed_age_years > 2:
                score -= 30
                contradictions.append({
                    "claim": f"Founded in {founding_year_claim}",
                    "evidence": f"Domain created {int(actual_age_years * 12)} months ago",
                    "status": "RED",
                    "match": False
                })
            else:
                contradictions.append({
                    "claim": f"Founded in {founding_year_claim}",
                    "evidence": f"Domain is ~{int(actual_age_years)} years old",
                    "status": "GREEN",
                    "match": True
                })
        else:
            if domain_age < 180: # less than 6 months
                score -= 20
                contradictions.append({
                    "claim": "Unknown founding year",
                    "evidence": "Domain age is less than 6 months",
                    "status": "AMBER",
                    "match": False
                })

        # Check 2: Employee count vs LinkedIn
        employees_claim = extracted_data.get("employees")
        linkedin_data = scraped_data.get("linkedin_data", "")
        
        if employees_claim and linkedin_data:
            # Simple mock check - in reality, use SLM to compare
            if "50 employees" in linkedin_data and employees_claim >= 50:
                 contradictions.append({
                    "claim": f"{employees_claim} employees",
                    "evidence": linkedin_data,
                    "status": "GREEN",
                    "match": True
                })
            else:
                score -= 20
                contradictions.append({
                    "claim": f"{employees_claim} employees",
                    "evidence": linkedin_data or "No LinkedIn profile found",
                    "status": "RED",
                    "match": False
                })

        # Check 3: Generic checks
        if not extracted_data.get("address"):
            score -= 10
            contradictions.append({
                "claim": "Physical Location",
                "evidence": "No address found on website",
                "status": "AMBER",
                "match": False
            })

        # Risk tier calculation
        risk_level = "LOW RISK"
        if score < 50:
            risk_level = "HIGH RISK"
        elif score < 80:
            risk_level = "MEDIUM RISK"

        return {
            "trust_score": max(0, min(100, score)),
            "risk_level": risk_level,
            "contradictions": contradictions
        }
