"""
Simplified MultiSearch Engine (Production Clean v1)
- Single embedding system
- No token overlap fallback
- No fake clustering
- Minimal velocity metric
"""

from __future__ import annotations

import asyncio
import uuid
import re
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

try:
    from ddgs import DDGS
except ImportError:
    DDGS = None

from datetime import datetime

from utils.embeddings import get_embeddings, cosine_similarity
from utils.log import get_logger

logger = get_logger(__name__)


# ----------------------------
# MAIN ENTRY
# ----------------------------

async def run_multi_search(claim, settings, retry=0, plan=None):
    queries = _generate_queries(claim.claim_text, claim.entities, settings.max_searches, retry)

    search_results = []
    for q in queries:
        search_results.extend(await _search(q))

    pages = await _fetch_pages(search_results[:15])

    units = _score_pages(claim, pages, settings)

    return {
        "evidence_units": units,
        "searches_performed": len(queries),
        "independent_clusters": len(units),
        "propagation_velocity": _simple_velocity(units, claim.timestamp),
    }


# ----------------------------
# QUERY GENERATION (CLEAN)
# ----------------------------

def _generate_queries(text: str, entities: list[str], limit: int, retry: int):
    base = text[:120]
    entity = " ".join(entities[:3])

    queries = [
        base,
        entity,
        f"{base} fact check",
        f"{base} latest news",
    ]

    if retry:
        queries.append(f"{base} confirmed OR denied")

    return list(dict.fromkeys(queries))[:limit]


# ----------------------------
# SEARCH (DDG)
# ----------------------------

async def _search(query: str):
    if DDGS is None:
        return []

    def run():
        out = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=5):
                url = r.get("href") or r.get("url")
                if url:
                    out.append({
                        "url": url,
                        "title": r.get("title", ""),
                        "snippet": r.get("body", ""),
                        "domain": urlparse(url).hostname or ""
                    })
        return out

    return await asyncio.to_thread(run)


# ----------------------------
# FETCH
# ----------------------------

async def _fetch_pages(results):
    tasks = [_fetch(r) for r in results]
    pages = await asyncio.gather(*tasks)
    return [p for p in pages if p]


async def _fetch(result):
    try:
        req = Request(result["url"], headers={"User-Agent": "Mozilla/5.0"})
        html = urlopen(req, timeout=8).read().decode("utf-8", errors="ignore")

        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()

        return {
            "url": result["url"],
            "domain": result["domain"],
            "text": text[:3000],
        }
    except:
        return None


# ----------------------------
# SCORING (CLEAN CORE)
# ----------------------------

def _score_pages(claim, pages, settings):
    if not pages:
        return []

    texts = [p["text"] for p in pages]
    vectors = get_embeddings([claim.claim_text] + texts, settings)

    claim_vec = vectors[0]
    page_vecs = vectors[1:]

    units = []

    for i, page in enumerate(pages):
        sim = cosine_similarity(claim_vec, page_vecs[i])

        units.append({
            "id": str(uuid.uuid4()),
            "type": "support" if sim > 0.6 else "neutral",
            "domain": page["domain"],
            "url": page["url"],
            "similarity": round(sim, 4),
            "lr": _lr(sim),
            "provenance": "multi_search",
            "raw_snippet": page["text"][:400],
        })

    return sorted(units, key=lambda x: x["similarity"], reverse=True)


# ----------------------------
# SIMPLE LR MODEL
# ----------------------------

def _lr(sim):
    if sim > 0.8:
        return 2.5
    if sim > 0.6:
        return 1.6
    if sim > 0.4:
        return 1.1
    return 0.9


# ----------------------------
# SIMPLE VELOCITY
# ----------------------------

def _simple_velocity(units, claim_time):
    return len([u for u in units if u["similarity"] > 0.7]) / max(len(units), 1)