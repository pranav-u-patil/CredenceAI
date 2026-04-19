"""
verification_agent/pipelines/model_validation.py
==================================================
Pipeline 3 — Fact-check APIs + NewsAPI + Finnhub market signals.

PLACEHOLDERS
------------
  FACTCHECK_API_KEY    — Google Fact Check Tools API
  CLAIMBUSTER_API_KEY  — ClaimBuster API
  NEWSAPI_KEY          — NewsAPI.org
  FINNHUB_API_KEY      — Finnhub.io
"""

from __future__ import annotations
import asyncio
import re
import uuid
from datetime import datetime
from typing import Any

import httpx

from config.settings import AgentSettings
from utils.schema    import ClaimInput
from utils.logger    import get_logger

logger = get_logger(__name__)

# Naive list of keywords that hint at a financial claim
_FINANCE_KEYWORDS = {
    "stock", "shares", "earnings", "revenue", "profit", "loss", "ipo",
    "merger", "acquisition", "sec", "filing", "dividend", "quarter",
    "fiscal", "market", "valuation", "price", "nasdaq", "nyse",
}


async def run_model_validation(claim: ClaimInput, settings: AgentSettings) -> dict:
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
    is_financial = _is_financial_claim(claim.claim_text, claim.entities)

    tasks: list[Any] = [
        _query_google_factcheck(claim, settings),
        _query_claimbuster(claim, settings),
        _query_newsapi(claim, settings),
    ]
    if is_financial:
        tasks.append(_query_finnhub(claim, settings))
    else:
        tasks.append(asyncio.coroutine(lambda: {})())   # no-op

    results = await asyncio.gather(*tasks, return_exceptions=True)
    fc_google, fc_claimbuster, news_result, market_result = results

    # Graceful degradation
    fc_google      = fc_google      if not isinstance(fc_google,      Exception) else {}
    fc_claimbuster = fc_claimbuster if not isinstance(fc_claimbuster, Exception) else {}
    news_result    = news_result    if not isinstance(news_result,    Exception) else {}
    market_result  = market_result  if not isinstance(market_result,  Exception) else {}

    evidence_units: list[dict] = []

    # Fact-check hits
    for hit in fc_google.get("hits", []):
        evidence_units.append(_factcheck_to_unit(hit, "google_factcheck"))
    for hit in fc_claimbuster.get("hits", []):
        evidence_units.append(_factcheck_to_unit(hit, "claimbuster"))

    # News coverage units
    for article in news_result.get("articles", []):
        evidence_units.append(_news_to_unit(article))

    # Market anomaly units
    market_signals = market_result if isinstance(market_result, dict) else {}
    if market_signals.get("anomaly"):
        evidence_units.append(_market_to_unit(market_signals, claim.entities))

    # Risk proxy (simple heuristic)
    risk_proxy: float | None = None
    if is_financial:
        price_move = abs(market_signals.get("price_change_pct", 0.0))
        risk_proxy = min(1.0, price_move / 20.0)

    fact_check_hits  = fc_google.get("hits", []) + fc_claimbuster.get("hits", [])
    primary_docs     = [h for h in fact_check_hits if h.get("is_primary")]

    return {
        "evidence_units":     evidence_units,
        "searches_performed": 3 + int(is_financial),
        "fact_check_hits":    fact_check_hits,
        "primary_documents":  primary_docs,
        "market_signals":     market_signals,
        "risk_proxy":         risk_proxy,
    }


# ── Fact-check APIs ───────────────────────────────────────────────────────────

async def _query_google_factcheck(claim: ClaimInput, settings: AgentSettings) -> dict:
    """
    Google Fact Check Tools API.
    Docs: https://developers.google.com/fact-check/tools/api/reference/rest/v1alpha1/claims/search
    # ← PLACEHOLDER: requires FACTCHECK_API_KEY
    """
    key = settings.factcheck_api_key
    if key.startswith("YOUR_"):
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


async def _query_claimbuster(claim: ClaimInput, settings: AgentSettings) -> dict:
    """
    ClaimBuster API — scores check-worthiness + searches known claims.
    Docs: https://idir.uta.edu/claimbuster/api
    # ← PLACEHOLDER: requires CLAIMBUSTER_API_KEY
    """
    key = settings.claimbuster_api_key
    if key.startswith("YOUR_"):
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

async def _query_newsapi(claim: ClaimInput, settings: AgentSettings) -> dict:
    """
    Queries NewsAPI for recent coverage of the claim entities.
    # ← PLACEHOLDER: requires NEWSAPI_KEY (free tier = dev only)
    """
    key = settings.newsapi_key
    if key.startswith("YOUR_"):
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
                "domain":      (a.get("source") or {}).get("id", ""),
                "published_at": a.get("publishedAt"),
                "description": a.get("description", ""),
            })
        return {"articles": articles}
    except Exception as exc:
        logger.warning("NewsAPI failed: %s", exc)
        return {"articles": []}


# ── Finnhub ───────────────────────────────────────────────────────────────────

async def _query_finnhub(claim: ClaimInput, settings: AgentSettings) -> dict:
    """
    Queries Finnhub for price data, company news, and SEC filings.
    # ← PLACEHOLDER: requires FINNHUB_API_KEY
    # ← PLACEHOLDER: entity → ticker resolution is naive; plug in a real NER
    """
    key = settings.finnhub_api_key
    if key.startswith("YOUR_"):
        logger.info("Finnhub API key not set; skipping market signals")
        return {}

    ticker = _resolve_ticker(claim.entities)
    if not ticker:
        return {}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Company profile
            profile_resp = await client.get(
                "https://finnhub.io/api/v1/stock/profile2",
                params={"symbol": ticker, "token": key},
            )
            # Quote
            quote_resp = await client.get(
                "https://finnhub.io/api/v1/quote",
                params={"symbol": ticker, "token": key},
            )
            # Company news
            news_resp = await client.get(
                "https://finnhub.io/api/v1/company-news",
                params={
                    "symbol": ticker,
                    "from":   "2026-04-01",   # ← PLACEHOLDER: derive from claim.timestamp
                    "to":     "2026-04-18",   # ← PLACEHOLDER: derive from claim.timestamp
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
            "anomaly":           abs(price_change_pct) > 5,  # ← PLACEHOLDER: tune threshold
            "news_count":        len(news),
            "profile":           profile,
        }
    except Exception as exc:
        logger.warning("Finnhub failed for %s: %s", ticker, exc)
        return {}


def _resolve_ticker(entities: list[str]) -> str | None:
    """
    Extremely naive entity → ticker resolver.
    PLACEHOLDER: replace with a real NER + ticker lookup service.
    """
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
    words = set(text.lower().split())
    entity_words = {w for e in entities for w in e.lower().split()}
    return bool((words | entity_words) & _FINANCE_KEYWORDS)