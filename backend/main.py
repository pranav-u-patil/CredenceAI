# main.py (place next to run.py)
import asyncio
import logging
from datetime import datetime, timezone
from importlib import import_module
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import importlib
from pydantic import BaseModel, Field, HttpUrl

from app.models.schema import ScraperInput  # your Pydantic models
from services.scrap import build_claim_from_preview, scrape_article_preview

app = FastAPI(title="CredenceAI")
logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ArticleRequest(BaseModel):
    url: HttpUrl
    claim_text: Optional[str] = Field(default=None, description="Optional custom claim text for deeper analysis")
    entities: Optional[List[str]] = Field(default_factory=list)
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)


def _load_run_agent():
    try:
        module = import_module("agent.agent")
    except ModuleNotFoundError:
        module = import_module("CredenceAI.backend.agent.agent")
    return getattr(module, "run_agent")

@app.on_event("startup")
async def startup():
    # Create queue and start optional worker if available.
    app.state.agent_queue = asyncio.Queue(maxsize=1000)
    app.state.agent_task = None
    try:
        agent = importlib.import_module("agent.worker")
        app.state.agent_task = asyncio.create_task(
            agent.start_agent(asyncio.get_event_loop(), app.state.agent_queue)
        )
    except ModuleNotFoundError:
        logger.warning("Optional module 'agent.worker' not found; running without background worker")

@app.on_event("shutdown")
async def shutdown():
    try:
        agent = importlib.import_module("agent.worker")
        stop = getattr(agent, "stop_agent", None)
        if stop:
            maybe = stop()
            if asyncio.iscoroutine(maybe):
                await maybe
    except ModuleNotFoundError:
        pass

    if getattr(app.state, "agent_task", None):
        app.state.agent_task.cancel()
        try:
            await app.state.agent_task
        except asyncio.CancelledError:
            pass

@app.post("/ingest/scraper", status_code=202)
async def ingest(payload: ScraperInput, request: Request):
    q = request.app.state.agent_queue
    await q.put(payload.dict())
    return {"status":"accepted", "claim_id": payload.claim_id}


@app.post("/preview/article")
async def preview_article(payload: ArticleRequest):
    preview = await scrape_article_preview(str(payload.url))
    if preview.get("status") != "success":
        raise HTTPException(status_code=422, detail=preview.get("error") or "Unable to scrape article")

    return {
        "status": "preview_ready",
        "preview": preview,
        "claim_text": payload.claim_text or preview.get("title") or preview.get("summary") or preview.get("snippet") or str(payload.url),
    }


@app.post("/analyze/article")
async def analyze_article(payload: ArticleRequest):
    preview = await scrape_article_preview(str(payload.url))
    if preview.get("status") != "success":
        raise HTTPException(status_code=422, detail=preview.get("error") or "Unable to scrape article")

    claim_id = f"claim_{int(datetime.now(timezone.utc).timestamp() * 1000)}"
    claim_payload = build_claim_from_preview(
        url=str(payload.url),
        preview=preview,
        claim_id=claim_id,
        claim_text=payload.claim_text,
        entities=payload.entities,
        context=payload.context,
    )

    run_agent = _load_run_agent()
    analysis = await run_agent(claim_payload)

    return {
        "status": "analysis_complete",
        "preview": preview,
        "analysis": analysis,
    }


@app.post("/analyze/claim")
async def analyze_claim(payload: ScraperInput):
    """Run the full agent pipeline on a plain-text claim (no URL needed)."""
    claim_id = payload.claim_id or f"claim_{int(datetime.now(timezone.utc).timestamp() * 1000)}"

    claim_payload = {
        "claim_id": claim_id,
        "claim_text": payload.claim_text,
        "timestamp": payload.timestamp.isoformat() if payload.timestamp else datetime.now(timezone.utc).isoformat(),
        "initial_urls": [u.dict() for u in payload.initial_urls] if payload.initial_urls else [],
        "entities": payload.entities or [],
        "context": payload.context or {},
        "source_meta": payload.source_meta or {},
    }

    run_agent = _load_run_agent()
    analysis = await run_agent(claim_payload)

    return {
        "status": "analysis_complete",
        "claim_id": claim_id,
        "claim_text": payload.claim_text,
        "analysis": analysis,
    }
