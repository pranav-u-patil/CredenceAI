# backend/agent/pipelines/model_validation.py
from __future__ import annotations
import asyncio
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import os
try:
    import httpx
except ImportError:
    httpx = None

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args: Any, **kwargs: Any) -> bool:
        return False

try:
    from CredenceAI.backend.app.models.schema import ScraperInput as ClaimInput
except ImportError:
    try:
        from ...app.models.schema import ScraperInput as ClaimInput
    except ImportError:
        from app.models.schema import ScraperInput as ClaimInput

try:
    from CredenceAI.backend.utils.log import get_logger
except ImportError:
    try:
        from ...utils.log import get_logger
    except ImportError:
        from utils.log import get_logger

# Load .env from repo root
ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / ".env"
if ENV_PATH.exists():
    load_dotenv(dotenv_path=str(ENV_PATH))

logger = get_logger(__name__)

# ── Environment (exact keys you have) ────────────────────────────────────────
FINHUB_API_KEY   = os.getenv("FINHUB_API")
NEWS_API_KEY     = os.getenv("NEWS_API")
FACT_CHECK_KEY   = os.getenv("FACT_CHECK_API")
GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY")
MONGO_URI        = os.getenv("MONGO_URI")

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


async def _noop_result() -> dict[str, Any]:
    return {}


async def run_model_validation(claim: ClaimInput, settings, plan: Any | None = None) -> dict:
    is_financial = _is_financial_claim(claim.claim_text, claim.entities)
    searches_performed = 0

    # --- Fact-check ----------------------------------------------------------
    fc_google_task = _query_google_factcheck(claim, plan=plan)
    if FACT_CHECK_KEY:
        searches_performed += 1

    # --- News ----------------------------------------------------------------
    news_task = _query_newsapi(claim, plan=plan)
    if NEWS_API_KEY:
        searches_performed += 1

    # --- RAG -----------------------------------------------------------------
    rag_task = _run_rag(claim)
    if GEMINI_API_KEY and MONGO_URI:
        searches_performed += 1

    # --- Market --------------------------------------------------------------
    if is_financial:
        market_task = _query_finnhub(claim)
        if FINHUB_API_KEY:
            searches_performed += 1
    else:
        market_task = _noop_result()

    results = await asyncio.gather(
        fc_google_task, news_task, rag_task, market_task,
        return_exceptions=True,
    )
    fc_google, news_result, rag_result, market_result = results

    fc_google     = fc_google     if not isinstance(fc_google,     Exception) else {}
    news_result   = news_result   if not isinstance(news_result,   Exception) else {}
    rag_result    = rag_result    if not isinstance(rag_result,    Exception) else {}
    market_result = market_result if not isinstance(market_result, Exception) else {}

    evidence_units: list[dict] = []

    # ── Fact-check hits (conservative LRs) ──────────────────────────────────
    for hit in fc_google.get("hits", []):
        evidence_units.append(_factcheck_to_unit(hit, "google_factcheck"))

    # ── News coverage (filtered, deduped, relevance-ranked) ─────────────────
    raw_articles = news_result.get("articles", []) or []
    raw_articles = _deduplicate_by_url(raw_articles)

    scored_articles = []
    for article in raw_articles:
        text = f"{article.get('title', '')} {article.get('description', '')}"
        rel = _relevance_score(claim.claim_text, text)
        if rel >= 0.12:                     # relevance floor
            article["_relevance"] = rel
            scored_articles.append(article)

    scored_articles.sort(key=lambda x: x["_relevance"], reverse=True)
    top_articles = scored_articles[:3]      # hard cap

    logger.info(
        "NewsAPI: %d raw → %d relevant → %d kept",
        len(raw_articles), len(scored_articles), len(top_articles),
    )

    fin_sentiments = []
    for article in top_articles:
        text = article.get("description") or article.get("title") or ""
        sentiment = _finbert_sentiment(text)
        fin_sentiments.append(sentiment)
        evidence_units.append(
            _news_to_unit(article, finbert_score=sentiment, relevance=article["_relevance"])
        )

    # ── RAG units ───────────────────────────────────────────────────────────
    for unit in rag_result.get("evidence_units", []):
        evidence_units.append(unit)

    # ── Market anomaly (neutral context) ────────────────────────────────────
    market_signals = market_result if isinstance(market_result, dict) else {}

    if fin_sentiments:
        avg_sent = sum(fin_sentiments) / len(fin_sentiments)
        market_signals["avg_finbert_sentiment"] = round(avg_sent, 3)
        if avg_sent < -0.4 and abs(market_signals.get("price_change_pct", 0)) > 3:
            market_signals["anomaly"] = True

    if market_signals.get("anomaly"):
        evidence_units.append(_market_to_unit(market_signals, claim.entities))

    # Risk proxy
    risk_proxy: float | None = None
    if is_financial:
        price_move = abs(market_signals.get("price_change_pct", 0.0))
        sentiment_adj = 1.0
        if market_signals.get("avg_finbert_sentiment") is not None:
            sentiment_adj += max(0.0, -market_signals["avg_finbert_sentiment"])
        risk_proxy = min(1.0, (price_move / 20.0) * sentiment_adj)

    fact_check_hits = fc_google.get("hits", [])
    primary_docs    = [h for h in fact_check_hits if h.get("is_primary")]

    return {
        "evidence_units":     evidence_units,
        "searches_performed": searches_performed,
        "fact_check_hits":    fact_check_hits,
        "primary_documents":  primary_docs,
        "market_signals":     market_signals,
        "risk_proxy":         risk_proxy,
    }


# ── Fact-check APIs ───────────────────────────────────────────────────────────

async def _query_google_factcheck(claim: ClaimInput, plan: Any | None = None) -> dict:
    key = FACT_CHECK_KEY or ""
    if not key or httpx is None:
        return {"hits": []}

    queries = list(getattr(plan, "fact_check_queries", []) or [])
    if not queries:
        queries = [claim.claim_text[:200]]
        if claim.entities:
            queries.append(" ".join(claim.entities[:3])[:200])

    all_hits: list[dict] = []
    seen_urls: set[str] = set()

    for q in queries:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://factchecktools.googleapis.com/v1alpha1/claims:search",
                    params={"query": q, "key": key, "pageSize": 5},
                )
            data = resp.json()
            for item in data.get("claims", []):
                review = (item.get("claimReview") or [{}])[0]
                url = review.get("url", "")
                if url and url in seen_urls:
                    continue
                seen_urls.add(url)
                all_hits.append({
                    "source":     review.get("publisher", {}).get("site", ""),
                    "rating":     review.get("textualRating", ""),
                    "url":        url,
                    "title":      review.get("title", ""),
                    "is_primary": True,
                    "claim_text": item.get("text", ""),
                })
        except Exception as exc:
            logger.warning("Google FactCheck query '%s...' failed: %s", q[:40], exc)
            continue

    return {"hits": all_hits}

# ── NewsAPI ───────────────────────────────────────────────────────────────────

async def _query_newsapi(claim: ClaimInput, plan: Any | None = None) -> dict:
    key = NEWS_API_KEY or ""
    if not key or httpx is None:
        return {"articles": []}

    try:
        articles = []
        seen_urls: set[str] = set()
        queries = list(getattr(plan, "news_queries", []) or [])
        if not queries:
            queries = [" OR ".join(claim.entities[:3]) or claim.claim_text[:80]]
        async with httpx.AsyncClient(timeout=10) as client:
            for query in queries[:3]:
                resp = await client.get(
                    "https://newsapi.org/v2/everything",
                    params={
                        "q":        query,
                        "apiKey":   key,
                        "pageSize": 10,
                        "sortBy":   "publishedAt",
                        "language": "en",
                    },
                )
                data = resp.json()
                for a in data.get("articles", []):
                    url = a.get("url", "")
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    articles.append({
                        "title":        a.get("title", ""),
                        "url":          url,
                        "domain":       (a.get("source") or {}).get("id", "") or (a.get("source") or {}).get("name", ""),
                        "published_at": a.get("publishedAt"),
                        "description":  a.get("description", ""),
                    })
        return {"articles": articles}
    except Exception as exc:
        logger.warning("NewsAPI failed: %s", exc)
        return {"articles": []}


# ── Finnhub ───────────────────────────────────────────────────────────────────

async def _query_finnhub(claim: ClaimInput) -> dict:
    key = FINHUB_API_KEY or ""
    if not key or httpx is None:
        return {}
    ticker = _resolve_ticker(claim.entities)
    if not ticker:
        return {}

    to_date = datetime.utcnow().date()
    from_date = to_date - timedelta(days=14)
    from_str, to_str = from_date.isoformat(), to_date.isoformat()

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
                params={"symbol": ticker, "from": from_str, "to": to_str, "token": key},
            )
        profile = profile_resp.json()
        quote   = quote_resp.json()
        news_raw = news_resp.json()
        news    = news_raw if isinstance(news_raw, list) else []

        prev_close = quote.get("pc", 1)
        curr_price = quote.get("c", prev_close)
        price_change_pct = ((curr_price - prev_close) / prev_close * 100) if prev_close else 0

        return {
            "ticker":           ticker,
            "company_name":     profile.get("name", ticker),
            "price_change_pct": round(price_change_pct, 2),
            "current_price":    curr_price,
            "anomaly":          abs(price_change_pct) > 5,
            "news_count":       len(news),
            "profile":          profile,
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
        clean_words = re.sub(r"[^\w\s]", "", e.lower()).split()
        for word in clean_words:
            t = common.get(word)
            if t:
                return t
    return None


# ── RAG (MongoDB + Gemini) ──────────────────────────────────────────────────

async def _run_rag(claim: ClaimInput) -> dict:
    api_key = GEMINI_API_KEY or ""
    mongo_uri = MONGO_URI or ""
    if not api_key or not mongo_uri:
        return {"evidence_units": []}

    try:
        from pymongo import MongoClient
    except ImportError:
        logger.info("pymongo not installed; skipping RAG")
        return {"evidence_units": []}

    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        db = client.get_default_database()
        if db is None:
            db = client["credence_db"]
        collection = db["documents"]

        # Ensure text index exists (idempotent if already indexed)
        # In production, create this ahead of time; here we silently pass if it fails
        try:
            collection.create_index([("text", "text")])
        except Exception:
            pass

        query_text = claim.claim_text[:200]
        cursor = collection.find(
            {"$text": {"$search": query_text}},
            {"score": {"$meta": "textScore"}, "text": 1, "source": 1, "url": 1, "timestamp": 1}
        ).sort([("score", {"$meta": "textScore"})]).limit(5)

        docs = list(cursor)
        if not docs:
            return {"evidence_units": []}

        # Summarize via Gemini
        context = "\n\n".join([d.get("text", "")[:600] for d in docs])
        summary = await _call_gemini_summary(claim.claim_text, context, api_key)

        units = []
        for d in docs:
            rel = min(d.get("score", 0.5), 1.0)
            units.append({
                "id": str(uuid.uuid4()),
                "type": "neutral",
                "domain": d.get("source", "mongodb"),
                "url": d.get("url", ""),
                "timestamp": d.get("timestamp"),
                "similarity": round(rel, 3),
                "lr": 1.0,
                "independence_weight": 0.9,
                "cluster_id": "rag_retrievals",
                "provenance": "rag",
                "raw_snippet": d.get("text", "")[:300],
            })

        units.append({
            "id": str(uuid.uuid4()),
            "type": "neutral",
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

    except Exception as exc:
        logger.warning("RAG pipeline failed: %s", exc)
        return {"evidence_units": []}


async def _call_gemini_summary(claim_text: str, context: str, api_key: str) -> str:
    if not httpx:
        return "RAG summary unavailable"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                (
                    "https://generativelanguage.googleapis.com/v1beta/models/"
                    "gemini-1.5-flash:generateContent?key=" + api_key
                ),
                json={
                    "contents": [{
                        "parts": [{
                            "text": (
                                f"Claim: {claim_text}\n\n"
                                f"Retrieved Context:\n{context}\n\n"
                                "In 1-2 sentences, state whether the context supports, "
                                "contradicts, or is neutral regarding the claim."
                            )
                        }]
                    }]
                },
            )
            data = resp.json()
            candidates = data.get("candidates", [])
            if candidates:
                return candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "No summary")
            return "No summary"
    except Exception as exc:
        logger.warning("Gemini summary failed: %s", exc)
        return "RAG summary unavailable"


# ── Converters ───────────────────────────────────────────────────────────────

def _factcheck_to_unit(hit: dict, provenance: str) -> dict:
    rating = hit.get("rating", "").lower()
    true_terms  = {"true", "correct", "accurate", "mostly true", "confirmed"}
    false_terms = {"false", "incorrect", "inaccurate", "pants on fire", "mostly false", "debunked"}
    mixed_terms = {"mixed", "partly", "half true", "half false", "misleading", "unproven", "inconclusive"}

    if any(t in rating for t in true_terms):
        unit_type, lr = "support", 2.0
    elif any(t in rating for t in false_terms):
        unit_type, lr = "contradict", 0.5
    elif any(t in rating for t in mixed_terms):
        unit_type, lr = "neutral", 1.0
    else:
        unit_type, lr = "neutral", 0.95

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


def _news_to_unit(article: dict, finbert_score: float | None = None, relevance: float = 0.0) -> dict:
    if finbert_score is not None:
        if finbert_score > 0.3:
            base_type, base_lr = "support", 1.2
        elif finbert_score < -0.3:
            base_type, base_lr = "contradict", 0.83
        else:
            base_type, base_lr = "neutral", 1.0
    else:
        base_type, base_lr = "neutral", 1.05

    # Dampen LR toward 1.0 as relevance drops
    if base_lr != 1.0:
        lr = 1.0 + (base_lr - 1.0) * relevance
    else:
        lr = 1.0

    domain = article.get("domain", "newsapi")
    return {
        "id":                  str(uuid.uuid4()),
        "type":                base_type,
        "domain":              domain,
        "url":                 article.get("url", ""),
        "timestamp":           article.get("published_at"),
        "similarity":          round(relevance, 3),
        "lr":                  round(lr, 3),
        "independence_weight": 0.5,
        "cluster_id":          f"newsapi_{domain}",
        "provenance":          "newsapi",
        "raw_snippet":         article.get("description", "")[:300],
    }


def _market_to_unit(signals: dict, entities: list[str]) -> dict:
    change = signals.get("price_change_pct", 0)
    return {
        "id":                  str(uuid.uuid4()),
        "type":                "context",
        "domain":              "finnhub",
        "url":                 "",
        "timestamp":           None,
        "similarity":          min(abs(change) / 20, 1.0),
        "lr":                  1.1 if signals.get("anomaly") else 1.0,
        "independence_weight": 1.0,
        "cluster_id":          "market_signals",
        "provenance":          "finnhub",
        "raw_snippet":         f"Price change {change:+.2f}% for {signals.get('ticker','')}",
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_financial_claim(text: str, entities: list[str]) -> bool:
    words = set(re.findall(r"\w+", text.lower()))
    entity_words = {w for e in entities for w in re.findall(r"\w+", e.lower())}
    has_ticker = _resolve_ticker(entities) is not None
    return bool((words | entity_words) & _FINANCE_KEYWORDS) or has_ticker


def _finbert_sentiment(text: str) -> float:
    if not text or _FINBERT_MODEL is None or _FINBERT_TOKENIZER is None:
        return 0.0
    try:
        inputs = _FINBERT_TOKENIZER(text, return_tensors="pt", truncation=True, max_length=512)
        with torch.no_grad():
            logits = _FINBERT_MODEL(**inputs).logits
            probs = torch.softmax(logits, dim=1).squeeze().tolist()
            neg, neu, pos = probs
            return float(pos - neg)
    except Exception as exc:
        logger.warning("FinBERT sentiment failed: %s", exc)
        return 0.0


def _relevance_score(claim_text: str, article_text: str) -> float:
    """Jaccard similarity over content words (≥3 chars)."""
    claim_words = set(re.findall(r"\b[a-z]{3,}\b", claim_text.lower()))
    article_words = set(re.findall(r"\b[a-z]{3,}\b", article_text.lower()))
    if not claim_words:
        return 0.0
    intersection = claim_words & article_words
    union = claim_words | article_words
    return len(intersection) / len(union) if union else 0.0


def _deduplicate_by_url(articles: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for a in articles:
        url = a.get("url", "")
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(a)
    return out
