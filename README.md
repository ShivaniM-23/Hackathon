# ShadowTrace AI

"The AI That Detects Fake Vendors, Scam Companies, and Risky Clients Before You Do."

ShadowTrace AI is a powerful fraud detection platform that leverages Small Language Models (SLMs) and web scraping to automatically cross-reference a company's claims against its actual digital footprint.

This repository implements **Phase 0 (Foundation)** and **Phase 1 (Basic MVP)**.

## Technical Flow
1. **User Input:** User submits a URL and optional details (LinkedIn, GST).
2. **Multi-Source Scraper:** The Python backend scrapes the company website, WHOIS database, and other available sources to build a ground-truth context.
3. **Entity Extractor (SLM):** The raw text is passed to an SLM (e.g., Phi-3 Mini via Ollama), which extracts structured entities like employee counts, founding year, and claims.
4. **Risk Analyzer:** The system compares the claims against the scraped ground-truth evidence to build a Contradiction Table.
5. **Trust Score:** A weighted score (0-100) is generated, indicating whether the company is LOW, MEDIUM, or HIGH RISK.
6. **Dashboard Output:** The results are presented in a sleek Next.js UI.

---

## Setup Instructions

### Prerequisites
- Node.js (v18+)
- Python (3.10+)
- Docker & Docker Compose
- (Optional) Ollama installed locally with `phi3:mini`

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

## Demo Steps (For the Hackathon Presentation)

1. Open `http://localhost:3000`.
2. Enter a suspicious startup URL (e.g., `https://example-scam-site.com`).
3. Click **Run Analysis**.
4. The dashboard will populate dynamically with the Trust Score, Risk Level, and the **Digital Footprint Consistency Engine** (Contradiction Table).
5. Highlight to judges how the SLM extracted claims ("50 employees") and the web scraper found contradictions ("Domain created 2 months ago").

---

## Future Phases (2-4)
- **Phase 2:** Graph visualization using D3.js/React Flow and Conversational AI querying.
- **Phase 3:** Guardrails and PDF export functionality.
- **Phase 4:** Voice briefings and live graph animations.
