# CredenceAI

CredenceAI is a multi-service credibility verification platform that helps evaluate claims using evidence aggregation, source behavior signals, and model-assisted analysis.

The repository includes:
1. A Python backend ingestion and orchestration service (FastAPI).
2. A Java verification service (Spring Boot) with Gemini integration.
3. A React frontend (Vite) for interactive claim submission and result visualization.

## System Architecture

Upload your two architecture images and place them in a folder such as docs/images, then update the paths below if needed.

### Architecture Diagram 1

![System Architecture](..\CredenceAI\docs\images\System_Architechture1.png)

### Architecture Diagram 2

![System Architecture](../CredenceAI\docs\images\System_Architechture2.jpeg)

## Repository Structure

```text
CredenceAi/
	backend/               # FastAPI ingestion and Python verification pipeline logic
	backend-java/           # Spring Boot verification API with Gemini call + risk classifier
	frontend/              # React + Vite user interface
```

---

## Free-Tier Token Budget Strategy

The system is carefully designed to stay within free limits:

### Gemini Flash (gemini-1.5-flash)
- **Model choice**: Flash is ~20× cheaper than Pro, still excellent for synthesis
- **Rate limiter**: Built-in 4.5s cooldown between calls (stays under 15 RPM)
- **Max tokens**: 2048 per response — concise, bullet-pointed outputs
- **Call count per analysis**: Exactly 2 Gemini calls (planning + synthesis)
- **Context pruning**: Only top 8 articles sent to Gemini, truncated to 150 chars each

### NewsAPI (100 req/day)
- Max 5 articles per query
- Query cap: 3 queries maximum
- 15-minute response cache (prevents duplicate calls on re-runs)

### Finnhub (60 req/min)
- Only called if ticker symbol detected in queries
- 5-minute cache on market data
- Maximum 2 calls per analysis session

### crawl4ai
- **Zero API cost** — local browser-based scraper
- Only enriches top 2 articles per run (saves time + resources)
- 15-minute response cache enabled

---

---

## Extending the System

### Add a new news source to the credibility database
Edit `backend/agents/source_analyzer.py` → `KNOWN_SOURCES` dict:
```python
"yourdomain.com": {"credibility": 75, "lean": 0, "type": "tech", "fact_check": "medium"},
```

### Add new risk keywords
Edit `backend/agents/risk_engine.py`:
```python
HIGH_RISK_KEYWORDS = [..., "your_keyword"]
```

### Add more Gemini analysis stages
Extend the `run_full_pipeline` generator in `backend/agents/orchestrator.py`.
Each `yield` sends an SSE event to the frontend in real-time.

### Adjust token budget
All limits in `backend/config/settings.py`:
```python
GEMINI_MAX_TOKENS_PER_REQUEST = 2048                       # increase for richer synthesis
NEWS_API_MAX_ARTICLES = 5              # increase for more coverage
CRAWL4AI_MAX_PAGES_PER_QUERY = 3 # increase for deeper scraping
```

---


## Core Components

### 1) Python Backend (FastAPI)

- Entry points: backend/main.py, backend/run.py
- Primary endpoint: POST /ingest/scraper
- Main responsibilities:
	- Accept claims from UI/clients
	- Queue requests for agent processing
	- Coordinate ingestion and pipeline handoff

### 2) Java Backend (Spring Boot)

- Entry point: backend-java/src/main/java/com/CredenAI/hack/HackApplication.java
- Primary endpoint: POST /verify
- Main responsibilities:
	- Call Gemini for claim analysis
	- Convert LLM output into a risk category response

### 3) Frontend (React + Vite)

- Entry point: frontend/src/App.jsx
- Main responsibilities:
	- Capture user claim input
	- Send claim payloads to backend ingestion API
	- Display accepted status and evidence visualization UI

## Tech Stack

- Frontend: React, Vite, Tailwind CSS, Framer Motion
- Python services: FastAPI, Uvicorn, Motor (MongoDB), Pydantic
- Java services: Spring Boot, Maven
- Data and infra: MongoDB

## Prerequisites

- Python 3.9+
- Node.js 18+
- Java 17+
- Maven 3.9+
- MongoDB (local or remote)

## Quick Start

### 1) Clone and enter repository

```bash
git clone <your-repository-url>
cd CredenceAi
```

### 2) Configure environment variables

Create a root .env file for the Python backend:

```env
MONGO_URI=mongodb://localhost:27017
APP_HOST=0.0.0.0
APP_PORT=8000
APP_RELOAD=true
APP_LOG_LEVEL=info
```

Create backend-java/src/main/resources/application.properties:



### 3) Run the Python backend

```bash
pip install -r requirements.txt
cd backend
python run.py
```

Service default URL: http://localhost:8000

### 4) Run the Java backend

```bash
cd backend-java
./mvnw spring-boot:run
```

On Windows PowerShell:

```powershell
.\mvnw.cmd spring-boot:run
```

Default URL: http://localhost:8080

### 5) Run the frontend

```bash
cd frontend
npm install
npm run dev
```

Default URL: http://localhost:5173

Optional frontend environment variable (frontend/.env):

```env
VITE_API_BASE_URL=http://localhost:8000
```

## API Reference

### Python backend endpoint

POST /ingest/scraper

Request body example:

```json
{
	"claim_id": "claim_1713500000",
	"claim_text": "Company X announced acquisition of Company Y",
	"timestamp": "2026-04-19T10:00:00Z",
	"initial_urls": [],
	"entities": ["Company X", "Company Y"],
	"context": {},
	"source_meta": {}
}
```


## Testing

Python integration tests:

```bash
cd backend/agent
pytest tests/test_agent_integration.py -v
```

Java tests:

```bash
cd backend-java
./mvnw test
```

## Development Notes

- The frontend currently submits claims to the Python ingestion endpoint.
- The Java service can be used as a separate verification path via /verify.
- Keep service ports explicit in local setup to avoid CORS and routing confusion.

## Roadmap Suggestions

- Add docker-compose for one-command local startup.
- Add OpenAPI documentation for all services.
- Add CI workflows for Python and Java test suites.
- Add architecture images and keep them versioned in docs/images.

## License

This project is licensed under the terms in the LICENSE file.