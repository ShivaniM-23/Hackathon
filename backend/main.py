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

from database import graph_db

class ChatRequest(BaseModel):
    message: str
    context: dict

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
        
        # Phase 2: Save to Graph and get Graph Data
        graph_db.build_graph(request.url, extracted_entities, analysis_result['risk_level'])
        graph_data = graph_db.get_graph(request.url)
        
        # Let's attach graph data to extracted_data or response so frontend can use it
        extracted_entities["graph"] = graph_data
        
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

@app.post("/chat")
async def chat_with_dossier(request: ChatRequest):
    # Phase 2: Conversational AI
    # In a real app, send request.message + request.context to Mistral 7B.
    # We will mock the SLM response for reliability in demo if no SLM is running.
    msg = request.message.lower()
    if "why" in msg or "risky" in msg:
        response = "Based on the dossier, this company is risky because the domain age contradicts their claimed founding year, and there's a flagged director in their network."
    elif "summarise" in msg or "summarize" in msg:
        response = "Summary: Domain is recently registered despite claims of being founded in 2015. Employee count matches LinkedIn, but overall trust score is severely impacted by timeline contradictions."
    else:
        response = "I have analyzed the dossier. There are notable inconsistencies in their digital footprint. Please specify what you'd like me to look into."
    
    return {"reply": response}
@app.get("/health")
def health_check():
    return {"status": "healthy"}
