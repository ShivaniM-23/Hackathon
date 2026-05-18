"""
ShadowTrace AI — FastAPI Backend
Entry point: all routes, CORS, startup events.
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
import uuid
import asyncio
import os
import logging
from datetime import datetime
from dotenv import load_dotenv

from scraper import scrape_company
from analyzer import analyze_company
from trust_score import calculate_trust_score
from chat import chat_with_dossier
from guardrails import apply_guardrails, GuardrailResult
from database import (
    save_investigation,
    get_investigation,
    get_all_investigations,
    save_graph_data,
    get_graph_data,
    init_db,
)
from cache import init_cache, close_cache, get_cached, set_cached, invalidate
from pdf_export import generate_pdf_report

# ── Load Environment and Logging ─────────────────────────────────────────────
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="ShadowTrace AI",
    description="AI-powered due diligence and fraud detection API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://*.ngrok.io", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await init_db()
    await init_cache()


@app.on_event("shutdown")
async def shutdown():
    await close_cache()


# ── Request / Response models ─────────────────────────────────────────────────

class InvestigateRequest(BaseModel):
    url: str
    linkedin_url: Optional[str] = None
    gst_number: Optional[str] = None
    user_email: Optional[str] = None
    force_refresh: Optional[bool] = False

class InvestigateResponse(BaseModel):
    job_id: str
    status: str
    message: str
    cached: bool = False

class ChatRequest(BaseModel):
    job_id: str
    message: str


# ── Background investigation task ─────────────────────────────────────────────

async def run_investigation(job_id: str, request: InvestigateRequest):
    """
    Full pipeline: scrape → analyze → score → store.
    Updates the database store at each step for real-time progress.
    """
    
    job_data = {
        "job_id": job_id,
        "status": "processing",
        "progress_pct": 5,
        "progress_steps": ["🔍 Initializing investigation agent..."],
        "discovered_links": {},
        "report": None,
        "error": None,
        "user_email": request.user_email,
    }

    async def update_job(update_dict: dict):
        job_data.update(update_dict)
        await save_investigation(job_id, job_data)

    try:
        # Step 1: Discovery & Scrape
        await update_job({
            "progress_steps": job_data["progress_steps"] + ["🌐 Discovering company digital footprint..."],
            "progress_pct": 15
        })
        
        raw_data = await scrape_company(
            url=request.url,
            linkedin_url=request.linkedin_url,
            gst_number=request.gst_number,
        )
        
        disc = raw_data.get("discovered_links", {})
        found = [k for k, v in disc.items() if v and k != "website"]
        
        await update_job({
            "discovered_links": disc,
            "progress_steps": job_data["progress_steps"] + [f"✅ Discovered: {', '.join(found) if found else 'None'}"],
            "progress_pct": 30
        })

        await update_job({
            "progress_steps": job_data["progress_steps"] + ["📄 Scraped company website and WHOIS data"],
            "progress_pct": 50
        })

        # Step 2: Reddit & Reviews
        await update_job({
            "progress_steps": job_data["progress_steps"] + ["💬 Analyzing community sentiment (Reddit/Reviews)..."],
            "progress_pct": 70
        })
        
        # Step 3: AI Analysis
        await update_job({
            "progress_steps": job_data["progress_steps"] + ["🤖 AI extraction & contradiction detection..."],
            "progress_pct": 85
        })
        dossier = await analyze_company(raw_data)

        # Step 4: Scoring
        await update_job({
            "progress_steps": job_data["progress_steps"] + ["⚖️ Calculating final trust score..."],
            "progress_pct": 95
        })
        score_result = calculate_trust_score(dossier)

        # Step 5: Build Graph
        graph = build_graph_data(dossier, raw_data)
        await save_graph_data(job_id, graph)

        # Final Report
        final_report = {
            "job_id": job_id,
            "status": "complete",
            "company_name": dossier.get("company_name", "Unknown"),
            "url": request.url,
            "user_email": request.user_email,
            "trust_score": score_result["score"],
            "risk_level": score_result["risk_level"],
            "score_breakdown": score_result["breakdown"],
            "contradictions": dossier.get("contradictions", []),
            "extracted": dossier.get("extracted", {}),
            "red_flags": score_result.get("red_flags", []),
            "legitimacy_signals": score_result.get("legitimacy_signals", []),
            "legitimacy_verdict": score_result.get("legitimacy_verdict", "UNCERTAIN"),
            "ai_reasoning": dossier.get("ai_reasoning", ""),
            "discovered_links": raw_data.get("discovered_links", {}),
            "reviews": raw_data.get("reviews", {}),
            "raw_data_summary": raw_data.get("summary", {}),
            "entities": graph.get("nodes", []),
            "relationships": graph.get("edges", []),
            "progress_pct": 100,
            "progress_steps": job_data["progress_steps"] + ["✅ Investigation complete."]
        }
        await save_investigation(job_id, final_report)
        # Write to Redis cache so repeat requests are instant
        await set_cached(request.url, final_report, request.user_email)

    except Exception as e:
        logger.error(f"Investigation error: {e}")
        await update_job({
            "status": "error",
            "error": str(e),
            "progress_steps": job_data["progress_steps"] + [f"❌ Error: {str(e)}"]
        })


def build_graph_data(dossier: dict, raw_data: dict = {}) -> dict:
    """Builds a rich knowledge graph from all scraped data."""
    nodes = []
    edges = []
    company_id = "company_main"
    
    # Central company node
    nodes.append({
        "id": company_id,
        "type": "company",
        "label": dossier.get("company_name", "Target Company"),
        "risk": dossier.get("risk_level", "LOW"),
        "name": dossier.get("company_name", "Target"),
    })
    
    extracted = dossier.get("extracted", {})
    discovered = raw_data.get("discovered_links", {}) if raw_data else {}
    reviews = raw_data.get("reviews", {}) if raw_data else {}
    
    # Directors / founders
    for i, director in enumerate(extracted.get("directors", [])[:5]):
        if not director:
            continue
        nid = f"dir_{i}"
        nodes.append({"id": nid, "type": "person", "label": director, "name": director, "risk": "LOW"})
        edges.append({"source": company_id, "target": nid, "type": "DIRECTED_BY", "label": "director"})
    
    # Addresses
    for i, addr in enumerate(extracted.get("addresses", [])[:3]):
        if not addr:
            continue
        nid = f"addr_{i}"
        label = addr[:35] + "..." if len(addr) > 35 else addr
        nodes.append({"id": nid, "type": "address", "label": label, "name": label, "risk": "LOW"})
        edges.append({"source": company_id, "target": nid, "type": "LOCATED_AT", "label": "office"})
    
    # Claimed clients
    for i, client in enumerate(extracted.get("claimed_clients", [])[:4]):
        if not client:
            continue
        nid = f"client_{i}"
        nodes.append({"id": nid, "type": "company", "label": client, "name": client, "risk": "LOW"})
        edges.append({"source": company_id, "target": nid, "type": "CLAIMS_CLIENT", "label": "client"})
    
    # Domain node
    domain = raw_data.get("whois", {}).get("domain") if raw_data else None
    if domain:
        nid = "domain_main"
        age = raw_data.get("whois", {}).get("domain_age_days", 0)
        risk = "HIGH" if age < 365 else "LOW"
        nodes.append({"id": nid, "type": "domain", "label": domain, "name": domain, "risk": risk})
        edges.append({"source": company_id, "target": nid, "type": "OWNS_DOMAIN", "label": "domain"})
    
    # LinkedIn node
    linkedin_url = discovered.get("linkedin") or raw_data.get("url_linkedin") if raw_data else None
    if linkedin_url:
        nid = "linkedin_node"
        nodes.append({"id": nid, "type": "social", "label": "LinkedIn", "name": "LinkedIn Profile", "risk": "LOW"})
        edges.append({"source": company_id, "target": nid, "type": "HAS_SOCIAL", "label": "linkedin"})
    
    # GitHub node
    if discovered.get("github"):
        nid = "github_node"
        nodes.append({"id": nid, "type": "social", "label": "GitHub", "name": "GitHub", "risk": "LOW"})
        edges.append({"source": company_id, "target": nid, "type": "HAS_SOCIAL", "label": "github"})
    
    # Reddit node (if mentions found)
    reddit_mentions = reviews.get("reddit", {}).get("mentions", 0)
    if reddit_mentions > 0:
        nid = "reddit_node"
        neg = len(reviews.get("reddit", {}).get("negative_posts", []))
        risk = "HIGH" if neg >= 3 else "MEDIUM" if neg > 0 else "LOW"
        nodes.append({
            "id": nid, "type": "social",
            "label": f"Reddit ({reddit_mentions})",
            "name": f"Reddit — {reddit_mentions} mentions",
            "risk": risk
        })
        edges.append({"source": company_id, "target": nid, "type": "MENTIONED_ON", "label": "reddit"})
    
    # Certifications
    for i, cert in enumerate(extracted.get("certifications", [])[:3]):
        nid = f"cert_{i}"
        nodes.append({"id": nid, "type": "document", "label": cert, "name": cert, "risk": "LOW"})
        edges.append({"source": company_id, "target": nid, "type": "CERTIFIED", "label": "cert"})

    return {"nodes": nodes, "edges": edges}


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health(): return {"status": "ok"}

@app.post("/api/investigate", response_model=InvestigateResponse)
async def investigate(request: InvestigateRequest, background_tasks: BackgroundTasks):
    if not request.url: raise HTTPException(400, "URL required")

    # ── Redis cache check ────────────────────────────────────────────────────
    if not request.force_refresh:
        cached = await get_cached(request.url, request.user_email)
        if cached:
            job_id = cached["job_id"]
            # Re-persist to file store in case job_store.json was cleared
            # (ensures GET /api/report/<job_id> returns 200, not 404)
            existing = await get_investigation(job_id)
            if not existing:
                await save_investigation(job_id, cached)
                logger.info(f"♻️  Restored cached report {job_id} to file store")
            return {
                "job_id": job_id,
                "status": "complete",
                "message": f"Cached result (score: {cached.get('trust_score', '?')}). Pass force_refresh=true to re-investigate.",
                "cached": True,
            }
    else:
        # force_refresh=true: clear the old cache entry first
        await invalidate(request.url, request.user_email)

    job_id = str(uuid.uuid4())
    await save_investigation(job_id, {
        "job_id": job_id, "status": "queued", "progress_pct": 0, "progress_steps": ["Queued..."],
        "user_email": request.user_email
    })
    background_tasks.add_task(run_investigation, job_id, request)
    return {"job_id": job_id, "status": "queued", "message": "Investigation started", "cached": False}

@app.get("/api/report/{job_id}")
async def get_report(job_id: str):
    report = await get_investigation(job_id)
    if not report: raise HTTPException(404, "Report not found")
    if report.get("status") == "complete":
        report["graph"] = await get_graph_data(job_id)
    return report

@app.get("/api/graph/{job_id}")
async def get_graph(job_id: str):
    graph = await get_graph_data(job_id)
    if not graph: raise HTTPException(404, "Graph not found")
    return graph



@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    return await get_report(job_id)

@app.post("/api/chat")
async def chat(request: ChatRequest):
    report = await get_investigation(request.job_id)
    if not report or report.get("status") != "complete":
        raise HTTPException(404, "Report not ready")
    
    guard: GuardrailResult = apply_guardrails(request.message, report)
    if guard.blocked:
        return {"response": guard.blocked_message, "answer": guard.blocked_message}
    
    result = await chat_with_dossier(request.message, report)
    return {
        "response": result["answer"],   # for ChatPanel
        "answer": result["answer"],     # fallback
        "confidence": result.get("confidence", 0.7),
        "citations": result.get("citations", [])
    }

@app.get("/api/export/{job_id}")
async def export_pdf(job_id: str):
    report = await get_investigation(job_id)
    if not report or report.get("status") != "complete":
        raise HTTPException(404, "Report not ready")
    path = await generate_pdf_report(report)
    return FileResponse(path, filename=f"report_{job_id}.pdf")


@app.get("/api/history")
async def get_history(user_email: Optional[str] = None):
    """Returns one entry per unique URL, deduplicating any legacy duplicates, optionally filtered by user_email."""
    from cache import normalize_url
    all_reports = await get_all_investigations()

    # Build a map: normalized_url → best report (highest trust score wins)
    seen: dict[str, dict] = {}
    for job_id, report in all_reports.items():
        if report.get("status") != "complete":
            continue
        # Filter by user_email if provided
        if user_email and report.get("user_email") != user_email:
            continue
        key = normalize_url(report.get("url", "") or report.get("company_name", job_id))
        existing = seen.get(key)
        if not existing or report.get("trust_score", 0) > existing.get("trust_score", 0):
            seen[key] = report

    history = [
        {
            "job_id": r["job_id"],
            "company_name": r.get("company_name", "Unknown"),
            "url": r.get("url", ""),
            "trust_score": r.get("trust_score", 0),
            "risk_level": r.get("risk_level", "UNKNOWN"),
            "legitimacy_verdict": r.get("legitimacy_verdict", "UNCERTAIN"),
            "red_flags_count": len(r.get("red_flags", [])),
            "contradictions_count": len(r.get("contradictions", [])),
            "tier": r.get("tier"),
        }
        for r in seen.values()
    ]
    # Most risky first
    history.sort(key=lambda x: x["trust_score"])
    return history
