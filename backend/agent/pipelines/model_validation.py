# backend/agent/pipelines/model_validation.py
from __future__ import annotations
import asyncio
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import os
from dotenv import load_dotenv
from utils.schema    import ClaimInput
from utils.logger    import get_logger

# Load .env from repo root (sibling of backend)
ROOT = Path(__file__).resolve().parents[2]  # backend/agent/pipelines -> parents[2] -> repo root
ENV_PATH = ROOT / ".env"
if ENV_PATH.exists():
    load_dotenv(dotenv_path=str(ENV_PATH))

logger = get_logger(__name__)

# Environment keys (map your .env names)
FINNHUB_API_KEY = os.getenv("FINHUB_API")
NEWSAPI_KEY     = os.getenv("NEWS_API")
FACTCHECK_KEY   = os.getenv("FACT_CHECK_API")
GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY")

# Naive list of keywords that hint at a financial claim
_FINANCE_KEYWORDS = {
    "stock", "shares", "earnings", "revenue", "profit", "loss", "ipo",
    "merger", "acquisition", "sec", "filing", "dividend", "quarter",
    "fiscal", "market", "valuation", "price", "nasdaq", "nyse",
}

# Optional: lazy import for FinBERT
try:
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    import torch
    _FINBERT_TOKENIZER = AutoTokenizer.from_pretrained("yiyanghkust/finbert-tone")
    _FINBERT_MODEL = AutoModelForSequenceClassification.from_pretrained("yiyanghkust/finbert-tone")
except Exception:
    _FINBERT_TOKENIZER = None
    _FINBERT_MODEL = None


async def run_model_validation(claim: ClaimInput, settings) -> dict:
    """
    Returns:
        {
          "evidence_units":    [...],
          "searches_performed": int,
          "fact_check_hits":   list,
          "primary_documents": list,
          "market_signals":    dict,
          "risk_proxy":        float | None,
        }
    """
    # Determine financialness using claim text + entities
    is_financial = _is_financial_claim(claim.claim_text, claim.entities)

    tasks: list[Any] = [
        _query_google_factcheck(claim),
        _query_claimbuster(claim),
        _query_newsapi(claim),
        _run_rag(claim),  # RAG retrieval + LLM summary (always run; will be no-op if not configured)
    ]
    if is_financial:
        tasks.append(_query_finnhub(claim))
    else:
        tasks.append(asyncio.coroutine(lambda: {})())   # no-op

    results = await asyncio.gather(*tasks, return_exceptions=True)
    fc_google, fc_claimbuster, news_result, rag_result, market_result = results

    # Graceful degradation
    fc_google      = fc_google      if not isinstance(fc_google,      Exception) else {}
    fc_claimbuster = fc_claimbuster if not isinstance(fc_claimbuster, Exception) else {}
    news_result    = news_result    if not isinstance(news_result,    Exception) else {}
    rag_result     = rag_result     if not isinstance(rag_result,     Exception) else {}
    market_result  = market_result  if not isinstance(market_result,  Exception) else {}

    evidence_units: list[dict] = []

    # Fact-check hits
    for hit in fc_google.get("hits", []):
        evidence_units.append(_factcheck_to_unit(hit, "google_factcheck"))
    for hit in fc_claimbuster.get("hits", []):
        evidence_units.append(_factcheck_to_unit(hit, "claimbuster"))

    # News coverage units (and FinBERT sentiment)
    news_articles = news_result.get("articles", []) or []
    fin_sentiments = []
    for article in news_articles:
        # compute finbert sentiment if available
        sentiment = _finbert_sentiment(article.get("description") or article.get("title") or "")
        fin_sentiments.append(sentiment)
        unit = _news_to_unit(article)
        unit["finbert_sentiment"] = sentiment
        evidence_units.append(unit)

    # RAG units (retrieved docs + LLM summary)
    for unit in rag_result.get("evidence_units", []):
        evidence_units.append(unit)

    # Market anomaly units
    market_signals = market_result if isinstance(market_result, dict) else {}
    # If FinBERT sentiment is available, aggregate and fold into market_signals
    if fin_sentiments:
        avg_sent = sum(fin_sentiments) / len(fin_sentiments)
        market_signals["avg_finbert_sentiment"] = round(avg_sent, 3)
        # adjust anomaly threshold: if strongly negative sentiment, amplify anomaly flag
        if avg_sent < -0.4 and abs(market_signals.get("price_change_pct", 0)) > 3:
            market_signals["anomaly"] = True

    if market_signals.get("anomaly"):
        evidence_units.append(_market_to_unit(market_signals, claim.entities))

    # Risk proxy (simple heuristic)
    risk_proxy: float | None = None
    if is_financial:
        price_move = abs(market_signals.get("price_change_pct", 0.0))
        # incorporate sentiment: negative sentiment increases risk
        sentiment_adj = 1.0
        if market_signals.get("avg_finbert_sentiment") is not None:
            sentiment_adj += max(0.0, -market_signals["avg_finbert_sentiment"])  # negative sentiment increases risk
        risk_proxy = min(1.0, (price_move / 20.0) * sentiment_adj)

    fact_check_hits  = fc_google.get("hits", []) + fc_claimbuster.get("hits", [])
    primary_docs     = [h for h in fact_check_hits if h.get("is_primary")]

    return {
        "evidence_units":     evidence_units,
        "searches_performed": 4 + int(is_financial),  # added RAG as an extra search
        "fact_check_hits":    fact_check_hits,
        "primary_documents":  primary_docs,
        "market_signals":     market_signals,
        "risk_proxy":         risk_proxy,
    }


# ── Fact-check APIs ───────────────────────────────────────────────────────────

async def _query_google_factcheck(claim: ClaimInput) -> dict:
    key = FACTCHECK_KEY or ""
    if not key:
        logger.info("Google FactCheck API key not set; skipping")
        return {"hits": []}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://factchecktools.googleapis.com/v1alpha1/claims:search",
                params={"query": claim.claim_text[:200], "key": key, "pageSize": 10},
            )
        data = resp.json()
        hits = []
        for item in data.get("claims", []):
            review = (item.get("claimReview") or [{}])[0]
            hits.append({
                "source":     review.get("publisher", {}).get("site", ""),
                "rating":     review.get("textualRating", ""),
                "url":        review.get("url", ""),
                "title":      review.get("title", ""),
                "is_primary": True,
                "claim_text": item.get("text", ""),
            })
        return {"hits": hits}
    except Exception as exc:
        logger.warning("Google FactCheck failed: %s", exc)
        return {"hits": []}


async def _query_claimbuster(claim: ClaimInput) -> dict:
    key = os.getenv("CLAIMBUSTER_API") or ""
    if not key:
        logger.info("ClaimBuster API key not set; skipping")
        return {"hits": []}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://idir.uta.edu/factcheck/api/score/",
                headers={"x-api-key": key},
                params={"input_claim": claim.claim_text[:500]},
            )
        data = resp.json()
        score = data.get("results", [{}])[0].get("score", 0.5)
        return {
            "hits": [{
                "source":     "claimbuster",
                "rating":     f"check_worthiness={score:.2f}",
                "url":        "",
                "is_primary": False,
                "cb_score":   score,
            }]
        }
    except Exception as exc:
        logger.warning("ClaimBuster failed: %s", exc)
        return {"hits": []}


# ── NewsAPI ───────────────────────────────────────────────────────────────────

async def _query_newsapi(claim: ClaimInput) -> dict:
    key = NEWSAPI_KEY or ""
    if not key:
        logger.info("NewsAPI key not set; skipping")
        return {"articles": []}
    query = " OR ".join(claim.entities[:3]) or claim.claim_text[:80]
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q":        query,
                    "apiKey":   key,
                    "pageSize": 20,
                    "sortBy":   "publishedAt",
                    "language": "en",
                },
            )
        data = resp.json()
        articles = []
        for a in data.get("articles", []):
            articles.append({
                "title":       a.get("title", ""),
                "url":         a.get("url", ""),
                "domain":      (a.get("source") or {}).get("id", "") or (a.get("source") or {}).get("name",""),
                "published_at": a.get("publishedAt"),
                "description": a.get("description", ""),
            })
        return {"articles": articles}
    except Exception as exc:
        logger.warning("NewsAPI failed: %s", exc)
        return {"articles": []}


# ── Finnhub ───────────────────────────────────────────────────────────────────

async def _query_finnhub(claim: ClaimInput) -> dict:
    key = FINNHUB_API_KEY or ""
    if not key:
        logger.info("Finnhub API key not set; skipping market signals")
        return {}

    ticker = _resolve_ticker(claim.entities)
    if not ticker:
        return {}

    # derive date window from claim timestamp if available
    try:
        to_date = datetime.utcnow().date()
        from_date = to_date - timedelta(days=14)
        from_str = from_date.isoformat()
        to_str = to_date.isoformat()
    except Exception:
        from_str, to_str = "2026-04-01", "2026-04-18"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            profile_resp = await client.get(
                "https://finnhub.io/api/v1/stock/profile2",
                params={"symbol": ticker, "token": key},
            )
            quote_resp = await client.get(
                "https://finnhub.io/api/v1/quote",
                params={"symbol": ticker, "token": key},
            )
            news_resp = await client.get(
                "https://finnhub.io/api/v1/company-news",
                params={
                    "symbol": ticker,
                    "from":   from_str,
                    "to":     to_str,
                    "token":  key,
                },
            )

        profile = profile_resp.json()
        quote   = quote_resp.json()
        news    = news_resp.json() if isinstance(news_resp.json(), list) else []

        prev_close = quote.get("pc", 1)
        curr_price = quote.get("c", prev_close)
        price_change_pct = ((curr_price - prev_close) / prev_close * 100) if prev_close else 0

        return {
            "ticker":            ticker,
            "company_name":      profile.get("name", ticker),
            "price_change_pct":  round(price_change_pct, 2),
            "current_price":     curr_price,
            "anomaly":           abs(price_change_pct) > 5,
            "news_count":        len(news),
            "profile":           profile,
        }
    except Exception as exc:
        logger.warning("Finnhub failed for %s: %s", ticker, exc)
        return {}


def _resolve_ticker(entities: list[str]) -> str | None:
    common = {
        "apple": "AAPL", "microsoft": "MSFT", "google": "GOOGL",
        "alphabet": "GOOGL", "amazon": "AMZN", "meta": "META",
        "tesla": "TSLA", "nvidia": "NVDA",
    }
    for e in entities:
        t = common.get(e.lower())
        if t:
            return t
    return None


# ── RAG (lightweight) ───────────────────────────────────────────────────────

async def _run_rag(claim: ClaimInput) -> dict:
    """
    Lightweight RAG:
    - Retrieve top-k docs from a vectorstore (FAISS / Milvus / Pinecone) using claim text.
    - Call LLM (placeholder using GEMINI_API_KEY) to produce a short evidence summary.
    - Return evidence_units list compatible with pipeline.
    """
    api_key = GEMINI_API_KEY or ""
    # If no vectorstore or LLM key, skip
    if not api_key:
        logger.info("GEMINI_API_KEY not set; skipping RAG")
        return {"evidence_units": []}

    # Placeholder retrieval: in prod, replace with real vectorstore query
    # Example: docs = vectorstore.search(claim.claim_text, top_k=5)
    docs = []  # TODO: plug in your vectorstore retrieval

    # If no docs found, return empty
    if not docs:
        return {"evidence_units": []}

    # Placeholder LLM call: summarize retrieved docs + claim
    # In production, call your LLM endpoint (Gemini or other) with api_key
    summary = "RAG summary placeholder"  # TODO: call LLM

    units = []
    for d in docs:
        units.append({
            "id": str(uuid.uuid4()),
            "type": "support",
            "domain": d.get("source", "vectorstore"),
            "url": d.get("url", ""),
            "timestamp": d.get("timestamp"),
            "similarity": d.get("score", 0.7),
            "lr": 1.2,
            "independence_weight": 0.9,
            "cluster_id": "rag_retrievals",
            "provenance": "rag",
            "raw_snippet": d.get("text", "")[:300],
        })

    # also include a synthetic unit for the LLM summary
    units.append({
        "id": str(uuid.uuid4()),
        "type": "support",
        "domain": "llm_rag",
        "url": "",
        "timestamp": None,
        "similarity": 0.5,
        "lr": 1.0,
        "independence_weight": 0.6,
        "cluster_id": "rag_summary",
        "provenance": "rag",
        "raw_snippet": summary,
    })

    return {"evidence_units": units}


# ── Converters ────────────────────────────────────────────────────────────────

def _factcheck_to_unit(hit: dict, provenance: str) -> dict:
    rating = hit.get("rating", "").lower()
    true_terms  = {"true", "correct", "accurate", "mostly true", "confirmed"}
    false_terms = {"false", "incorrect", "inaccurate", "pants on fire", "mostly false", "debunked"}
    if any(t in rating for t in true_terms):
        unit_type, lr = "support", 3.5
    elif any(t in rating for t in false_terms):
        unit_type, lr = "contradict", 0.2
    else:
        unit_type, lr = "anomaly", 0.85

    return {
        "id":                  str(uuid.uuid4()),
        "type":                unit_type,
        "domain":              hit.get("source", provenance),
        "url":                 hit.get("url", ""),
        "timestamp":           None,
        "similarity":          0.9 if hit.get("is_primary") else 0.7,
        "lr":                  lr,
        "independence_weight": 1.0,
        "cluster_id":          f"factcheck_{provenance}",
        "provenance":          provenance,
        "raw_snippet":         hit.get("title", ""),
    }


def _news_to_unit(article: dict) -> dict:
    return {
        "id":                  str(uuid.uuid4()),
        "type":                "support",
        "domain":              article.get("domain", "newsapi"),
        "url":                 article.get("url", ""),
        "timestamp":           article.get("published_at"),
        "similarity":          0.6,
        "lr":                  1.4,
        "independence_weight": 0.8,
        "cluster_id":          f"newsapi_{article.get('domain','x')}",
        "provenance":          "newsapi",
        "raw_snippet":         article.get("description", "")[:300],
    }


def _market_to_unit(signals: dict, entities: list[str]) -> dict:
    change = signals.get("price_change_pct", 0)
    unit_type = "support" if change > 0 else "contradict"
    return {
        "id":                  str(uuid.uuid4()),
        "type":                unit_type,
        "domain":              "finnhub",
        "url":                 "",
        "timestamp":           None,
        "similarity":          min(abs(change) / 20, 1.0),
        "lr":                  1.5 if change > 5 else (0.6 if change < -5 else 1.0),
        "independence_weight": 1.0,
        "cluster_id":          "market_signals",
        "provenance":          "finnhub",
        "raw_snippet":         f"Price change {change:+.2f}% for {signals.get('ticker','')}",
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_financial_claim(text: str, entities: list[str]) -> bool:
    words = set(re.findall(r"\w+", text.lower()))
    entity_words = {w for e in entities for w in re.findall(r"\w+", e.lower())}
    return bool((words | entity_words) & _FINANCE_KEYWORDS)


def _finbert_sentiment(text: str) -> float:
    """
    Returns sentiment score in [-1, 1] where negative is bearish, positive bullish.
    If FinBERT not available, returns 0.0 (neutral).
    """
    if not text or _FINBERT_MODEL is None or _FINBERT_TOKENIZER is None:
        return 0.0
    try:
        inputs = _FINBERT_TOKENIZER(text, return_tensors="pt", truncation=True, max_length=512)
        with torch.no_grad():
            logits = _FINBERT_MODEL(**inputs).logits
            # model outputs 3 classes: negative, neutral, positive
            probs = torch.softmax(logits, dim=1).squeeze().tolist()
            neg, neu, pos = probs
            score = pos - neg  # in [-1,1]
            return float(score)
    except Exception as exc:
        logger.warning("FinBERT sentiment failed: %s", exc)
        return 0.0
