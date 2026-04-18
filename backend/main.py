# main.py (place next to run.py)
import asyncio
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import importlib
from app.models.schema import ScraperInput

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
