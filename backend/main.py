from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from scraper import ScraperEngine
from slm_extractor import EntityExtractor
from analyzer import TrustScoreGenerator
import logging
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ShadowTrace AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    url: str
    gst_number: Optional[str] = None
    linkedin_url: Optional[str] = None

class AnalyzeResponse(BaseModel):
    status: str
    trust_score: int
    risk_level: str
    contradictions: list
    extracted_data: dict

scraper = ScraperEngine()
extractor = EntityExtractor()
analyzer = TrustScoreGenerator()

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_company(request: AnalyzeRequest):
    logger.info(f"Analyzing company: {request.url}")
    try:
        # Phase 1: Multi-Source Scraper
        scraped_data = scraper.scrape_all(request.url, request.linkedin_url)
        
        # Phase 1: Entity Extractor (SLM)
        extracted_entities = extractor.extract(scraped_data['website_text'])
        
        # Phase 1: Contradiction & Score
        analysis_result = analyzer.generate_score(scraped_data, extracted_entities)
        
        return AnalyzeResponse(
            status="success",
            trust_score=analysis_result['trust_score'],
            risk_level=analysis_result['risk_level'],
            contradictions=analysis_result['contradictions'],
            extracted_data=extracted_entities
        )
    except Exception as e:
        logger.error(f"Error analyzing company: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "healthy"}
