"""
News Intelligence Platform - Main Backend Server
FastAPI server with Gemini orchestration, crawl4ai scraping,
sentiment analysis, risk engine, and multi-source intelligence.
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from typing import Any, AsyncGenerator, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agents.orchestrator import GeminiOrchestrator
from agents.scraper import NewsScraperAgent
from agents.sentiment import SentimentAnalyzer
from agents.risk_engine import RiskEngine
from agents.source_analyzer import SourceBehaviorAnalyzer
from agents.fact_checker import FactCheckerAgent
from config.settings import Settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="News Intelligence Platform",
    description="AI-powered news analysis with Gemini orchestration",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

settings = Settings()

# ─── Request Models ─────────────────────────────────────────────────────────

class AnalysisRequest(BaseModel):
    queries: list[str]
    sources: Optional[list[str]] = None
    depth: Optional[str] = "standard"  # standard | deep | quick
    gemini_api_key: str
    finnhub_api_key: Optional[str] = ""
    news_api_key: Optional[str] = ""
    fact_check_api_key: Optional[str] = ""

class QuickAnalysisRequest(BaseModel):
    query: str
    gemini_api_key: str
    finnhub_api_key: Optional[str] = ""
    news_api_key: Optional[str] = ""

# ─── Routes ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    return {"status": "operational", "timestamp": datetime.utcnow().isoformat()}


@app.post("/analyze/stream")
async def analyze_stream(request: AnalysisRequest):
    """
    Full pipeline: scrape → source analysis → sentiment → risk → Gemini synthesis
    Streams progress events back to client (SSE).
    Free-tier friendly: batched requests, rate-limited, caches where possible.
    """
    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            orchestrator = GeminiOrchestrator(
                gemini_api_key=request.gemini_api_key,
                finnhub_api_key=request.finnhub_api_key,
                news_api_key=request.news_api_key,
                fact_check_api_key=request.fact_check_api_key,
            )

            async for event in orchestrator.run_full_pipeline(
                queries=request.queries,
                sources=request.sources,
                depth=request.depth,
            ):
                yield f"data: {json.dumps(event)}\n\n"
                await asyncio.sleep(0.01)

        except Exception as e:
            logger.exception("Pipeline error")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@app.post("/analyze/quick")
async def quick_analyze(request: QuickAnalysisRequest):
    """
    Lightweight single-query analysis. Conserves API tokens for free-tier users.
    """
    try:
        orchestrator = GeminiOrchestrator(
            gemini_api_key=request.gemini_api_key,
            finnhub_api_key=request.finnhub_api_key,
            news_api_key=request.news_api_key,
        )
        result = await orchestrator.quick_analyze(request.query)
        return result
    except Exception as e:
        logger.exception("Quick analysis error")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sources/behavior/{domain}")
async def source_behavior(domain: str):
    """Return cached behavior profile for a news source domain."""
    analyzer = SourceBehaviorAnalyzer()
    profile = await analyzer.get_profile(domain)
    return profile


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
