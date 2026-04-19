"""
verification_agent/pipelines/multi_search.py
=============================================
Agent-directed web search and page sampling.
"""

from __future__ import annotations

import asyncio
import re
import uuid
from datetime import datetime
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

try:
    from ddgs import DDGS
except ImportError:
    DDGS = None

try:
    from ..config.settings import AgentSettings
except ImportError:
    from config.settings import AgentSettings

try:
    from CredenceAI.backend.app.models.schema import ScraperInput as ClaimInput
except ImportError:
    try:
        from ...app.models.schema import ScraperInput as ClaimInput
    except ImportError:
        from app.models.schema import ScraperInput as ClaimInput

try:
    from CredenceAI.backend.utils.embeddings import cosine_similarity, get_embeddings
except ImportError:
    try:
        from ...utils.embeddings import cosine_similarity, get_embeddings
    except ImportError:
        from utils.embeddings import cosine_similarity, get_embeddings

try:
    from CredenceAI.backend.utils.log import get_logger
except ImportError:
    try:
        from ...utils.log import get_logger
    except ImportError:
        from utils.log import get_logger

logger = get_logger(__name__)


async def run_multi_search(
    claim: ClaimInput,
    settings: AgentSettings,
    retry: int = 0,
    plan: Any | None = None,
) -> dict[str, Any]:
    queries = _resolve_queries(claim, settings, retry=retry, plan=plan)
    logger.info("MultiSearch: generated %d queries for claim_id=%s", len(queries), claim.claim_id)

    results: list[dict[str, Any]] = []
    for query in queries:
        results.extend(await _search(query))

    seen_urls = {str(item.url) for item in claim.initial_urls}
    deduped_results: list[dict[str, Any]] = []
    for item in results:
        url = item.get("url", "")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        deduped_results.append(item)

    fetched = await _fetch_pages(deduped_results[:20])
    units = _score_pages(claim, fetched, settings)
    velocity = _estimate_velocity(units, claim.timestamp)

    return {
        "evidence_units": units,
        "searches_performed": len(queries),
        "independent_clusters": len({u["cluster_id"] for u in units if u.get("cluster_id")}),
        "propagation_velocity": velocity,
    }


def _resolve_queries(claim: ClaimInput, settings: AgentSettings, retry: int = 0, plan: Any | None = None) -> list[str]:
    if plan is not None:
        search_plan = getattr(plan, "search", None)
        if retry > 0 and getattr(search_plan, "retry", None):
            return list(search_plan.retry)[: settings.max_searches]
        if getattr(search_plan, "primary", None):
            return list(search_plan.primary)[: settings.max_searches]
    return _generate_queries(claim.claim_text, claim.entities, settings.max_searches, retry)


def _generate_queries(claim_text: str, entities: list[str], limit: int, retry: int) -> list[str]:
    entity_phrase = " ".join(entities[:4]).strip()
    clean = claim_text.strip()
    queries = [
        clean,
        entity_phrase,
        f"{clean[:80]} fact check",
        f"{clean[:80]} official statement",
        f"{clean[:80]} latest",
    ]
    if retry > 0:
        queries.extend([
            f"{clean[:80]} denied OR confirmed",
            f"{clean[:80]} rebuttal",
        ])
    return [q for q in dict.fromkeys(query.strip() for query in queries) if q][:limit]


async def _search(query: str) -> list[dict[str, Any]]:
    if DDGS is None:
        logger.warning("ddgs not installed; returning empty results")
        return []

    def _run() -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        with DDGS() as ddgs:
            for result in ddgs.text(query, max_results=8):
                href = result.get("href") or result.get("url") or result.get("link") or ""
                if not href:
                    continue
                items.append(
                    {
                        "url": href,
                        "domain": (urlparse(href).hostname or "").removeprefix("www."),
                        "title": result.get("title", ""),
                        "snippet": result.get("body") or result.get("snippet") or "",
                    }
                )
        return items

    try:
        return await asyncio.wait_for(asyncio.to_thread(_run), timeout=15)
    except asyncio.TimeoutError:
        logger.warning("DDG search timed out for query: %s", query)
        return []
    except Exception as exc:
        logger.warning("DDG search failed for query '%s': %s", query, exc)
        return []


async def _fetch_pages(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fetched = await asyncio.gather(*[_fetch_one(result) for result in results], return_exceptions=True)
    return [item for item in fetched if isinstance(item, dict) and item.get("text")]


async def _fetch_one(result: dict[str, Any]) -> dict[str, Any] | None:
    url = result.get("url", "")
    if not url:
        return None

    def _download() -> dict[str, Any] | None:
        try:
            request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(request, timeout=10) as response:
                html = response.read().decode("utf-8", errors="ignore")
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text).strip()
            return {
                "url": url,
                "domain": result.get("domain") or (urlparse(url).hostname or "").removeprefix("www."),
                "published_at": None,
                "text": text,
            }
        except Exception as exc:
            logger.debug("Fetch failed for %s: %s", url, exc)
            return None

    return await asyncio.to_thread(_download)


def _score_pages(claim: ClaimInput, pages: list[dict[str, Any]], settings: AgentSettings) -> list[dict[str, Any]]:
    if not pages:
        return []

    snippets = [page["text"][:1000] for page in pages]
    vectors = get_embeddings([claim.claim_text] + snippets, settings)
    claim_vec = vectors[0]
    page_vecs = vectors[1:]

    units: list[dict[str, Any]] = []
    best_by_cluster: dict[str, dict[str, Any]] = {}

    for index, page in enumerate(pages):
        similarity = cosine_similarity(claim_vec, page_vecs[index]) if page_vecs else _token_overlap(claim.claim_text, page["text"])
        lr = _sim_to_lr(similarity, settings)
        unit = {
            "id": str(uuid.uuid4()),
            "type": "support" if similarity > 0.55 else "neutral",
            "domain": page.get("domain", ""),
            "url": page.get("url", ""),
            "timestamp": page.get("published_at"),
            "similarity": round(similarity, 4),
            "lr": lr,
            "independence_weight": 1.0,
            "cluster_id": page.get("domain") or page.get("url"),
            "provenance": "multi_search",
            "raw_snippet": page["text"][:500],
        }
        cluster_id = unit["cluster_id"]
        current = best_by_cluster.get(cluster_id)
        if current is None or abs(float(unit["lr"]) - 1.0) > abs(float(current["lr"]) - 1.0):
            best_by_cluster[cluster_id] = unit

    units = list(best_by_cluster.values())
    units.sort(key=lambda item: item["similarity"], reverse=True)
    return units


def _estimate_velocity(units: list[dict[str, Any]], claim_timestamp: Any) -> float:
    if not units or not claim_timestamp:
        return 0.0
    try:
        claim_dt = _parse_datetime(claim_timestamp)
    except Exception:
        return 0.0

    close = 0
    dated = 0
    for unit in units:
        timestamp = unit.get("timestamp")
        if not timestamp:
            continue
        try:
            unit_dt = _parse_datetime(timestamp)
        except Exception:
            continue
        dated += 1
        if abs((unit_dt - claim_dt).total_seconds()) <= 6 * 3600:
            close += 1
    return round(close / dated, 4) if dated else 0.0


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _token_overlap(left: str, right: str) -> float:
    left_tokens = set(re.findall(r"\w+", left.lower()))
    right_tokens = set(re.findall(r"\w+", right.lower()))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _sim_to_lr(similarity: float, settings: AgentSettings) -> float:
    mapping = settings.lr_mapping
    if similarity >= 0.85:
        return float(mapping.get("high", 3.0))
    if similarity >= 0.65:
        return float(mapping.get("medium", 1.8))
    if similarity >= 0.40:
        return float(mapping.get("low", 1.1))
    return float(mapping.get("noise", 0.9))
