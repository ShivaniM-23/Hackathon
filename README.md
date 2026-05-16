# ShadowTrace AI 🕵️‍♂️🤖

"The AI That Detects Fake Vendors, Scam Companies, and Risky Clients Before You Do."

ShadowTrace AI is a powerful fraud detection platform that leverages Small Language Models (SLMs) and deep web scraping to automatically cross-reference a company's claims against its actual digital footprint.

This repository implements **Phase 0 (Foundation)**, **Phase 1 (Basic MVP)**, and **Phase 2 (Backend Graph & Chat)**.

---

## 🌟 Technical Flow & Key Features

### 1. Autonomous Multi-Source Scraper
The Python backend orchestration pipeline aggressively gathers ground-truth evidence across the internet:
- **Deep Website Crawling:** Crawls up to 100 pages deep to find contact pages, team info, terms of service, and hiring details.
- **WHOIS Domain Analysis:** Validates domain registration age against claimed founding years.
- **Social & Review Scraping:** Extracts data from Trustpilot, Glassdoor, AmbitionBox, and Reddit.
- **News Coverage:** Checks Google News for positive press or fraud/scam reports.
- **LinkedIn Discovery & Fallback:** Automatically finds LinkedIn profiles. If the website lacks a direct link, it uses a fallback algorithm to guess the URL and verify its existence.
- **Wikipedia Global Recognition:** Identifies globally recognized enterprises to ensure accurate, unpenalized scoring for major corporations.

### 2. AI-Powered Legitimacy Reasoning (Entity Extractor)
The core philosophy of ShadowTrace is **"let the AI READ and REASON about what it scraped"**.
- We pass the entire scraped dossier (website text, Reddit post titles, news headlines) to a local Small Language Model (e.g., Phi-3 Mini via Ollama).
- The AI evaluates whether the evidence points to a real company or a scam. It differentiates between **service complaints** ("slow shipping") and **actual fraud signals** ("ponzi scheme", "police FIR").

### 3. Dynamic Trust Scoring Engine & Risk Analyzer
A mathematical 0-100 Trust Score is computed natively without hardcoded overrides:
- **Legitimacy Signals (Green):** Points awarded for verified age, active hiring, regulatory presence, and positive news.
- **Fraud Signals (Red):** Penalties applied for confirmed AI-detected fraud terminology, extreme employee inflation, or domain age contradictions.
- **Risk Bands:** `HIGH RISK` (0-29), `MEDIUM RISK` (30-54), `LOW-MEDIUM` (55-74), and `LOW RISK` (75-100).
- **Contradiction Table:** Maps out claims vs. reality (e.g., "Claimed 500 employees, but LinkedIn shows 0").

### 4. Interactive Next.js Dashboard (Graph & Chat)
- **Knowledge Graph (React Flow):** Data is saved to a Neo4j graph to visualize the entities connected to the company (founders, locations, clients).
- **AI Investigator Chat:** A conversational AI interface allows users to ask the AI questions directly about the scraped dossier.
- **PDF Export:** Click to download the final due diligence report.

---

## 🚀 Setup Instructions

### Prerequisites
- Node.js (v18+)
- Python (3.10+)
- Docker & Docker Compose (For Postgres/Neo4j)
- (Optional) Ollama installed locally with `phi3` (`ollama run phi3`)

### 1. Environment Variables

We have provided a template for your environment variables. 
Open `.env` in the root directory and modify it if necessary:

**What you might need to edit:**
- `OLLAMA_BASE_URL` and `OLLAMA_MODEL`: If you are running Ollama on a different machine or using a different model like `gemma:2b` or `llama3`.
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `NEO4J_USER`, `NEO4J_PASSWORD`: Set secure passwords before deploying.

### 2. Start the Databases

Run the following command in the root directory to spin up PostgreSQL and Neo4j via Docker Compose:

```bash
docker-compose up -d
```

### 3. Start the Backend (FastAPI)

Open a new terminal, navigate to the `backend` directory, and run:

```bash
cd backend

# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the FastAPI server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The backend API will be available at `http://localhost:8000`. You can view the Swagger documentation at `http://localhost:8000/docs`.

### 4. Start the Frontend (Next.js)

Open a new terminal, navigate to the `frontend` directory, and run:

```bash
cd frontend

# Install dependencies
npm install

# Start the development server
npm run dev
```

The frontend will be available at `http://localhost:3000`.

---

## 🎬 Demo Steps (For the Hackathon Presentation)

1. Ensure Ollama is running (`ollama run phi3`).
2. Open `http://localhost:3000`.
3. Enter a suspicious startup URL or a well-known enterprise URL in the **Company Website** input.
4. (Optional) Provide a specific **LinkedIn URL** to bypass auto-discovery.
5. Click **Start Investigation**.
6. Watch as the sidebar dynamically streams the progress ("Scraping Website", "Analyzing Reviews").
7. Once complete, walk the judges through the:
   - **AI Verdict Badge** (e.g., LIKELY LEGITIMATE) and Trust Score.
   - **Legitimacy Signals (Green)** vs **Red Flags (Red)**.
   - **Digital Footprint Consistency Engine (Contradiction Table)** showing claim vs reality gaps.
   - **Knowledge Graph** visualizing the company's network.
   - **AI Chat Panel** by asking "What is the biggest risk with this company?".

---

## 🗺️ Roadmap & Implementation Status

### ✅ Phase 0 & 1: Core MVP (Completed)
- FastAPI backend with multi-source scraping (Website, WHOIS, News, Reviews, Wikipedia, LinkedIn fallback).
- Local SLM integration for entity extraction.
- Next.js dashboard with Trust Score, Legitimacy Signals, and Contradiction Table.
- Zero hardcoded scoring overrides — fully dynamic mathematics.

### ✅ Phase 2: Knowledge Graph & Conversational AI (Completed)
- **Backend:** Neo4j integration and `/chat` endpoint are fully functional. React Flow graph endpoints return correctly formatted node data.
- **Frontend:** Integrated React Flow graph visualization and AI Investigator Chat interface directly into the dashboard while maintaining the Phase 1 dark theme.
- **AI Analysis:** LLM parses evidence directly to detect fraud signals contextually.

### ⏳ Future Phases
- **Phase 3:** Guardrails and advanced PDF export functionality.
- **Phase 4:** Voice briefings and live real-time graph animations.
