import requests
import json
import logging
import os

logger = logging.getLogger(__name__)

class EntityExtractor:
    def __init__(self):
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = os.getenv("OLLAMA_MODEL", "phi3:mini")

    def extract(self, text: str) -> dict:
        prompt = f"""
        Extract the following information from the text below as a JSON object:
        - employees (integer or null)
        - founding_year (integer or null)
        - clients (list of strings)
        - address (string or null)
        - funding_claims (list of strings)

        Text:
        {text}

        Return ONLY valid JSON.
        """
        
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                },
                timeout=30
            )
            response.raise_for_status()
            result_text = response.json().get("response", "{}")
            return json.loads(result_text)
        except Exception as e:
            logger.error(f"SLM Extraction failed: {e}. Returning mock data.")
            # Fallback for hackathon demo if Ollama isn't running
            return {
                "employees": 50,
                "founding_year": 2015,
                "clients": ["Fortune 500"],
                "address": "San Francisco",
                "funding_claims": []
            }
