from typing import List, Dict, Optional
from datetime import datetime, timezone
from urllib.parse import urlparse
import asyncio
from concurrent.futures import ThreadPoolExecutor

from newspaper import Article

# =========================
# CONFIG
# =========================
MAX_SNIPPET = 5000
EXECUTOR = ThreadPoolExecutor(max_workers=5)


# =========================
# HELPERS
# =========================
def _extract_domain(url: str) -> str:
    try:
        return urlparse(url).hostname or ""
    except Exception:
        return ""


def _clean_text(text: str) -> str:
    if not text:
        return ""
    return " ".join(text.split())


# =========================
# CORE SCRAPER (BLOCKING)
# =========================
def _fetch_with_newspaper(url: str) -> Dict:
    try:
        article = Article(url)
        article.download()
        article.parse()

        text = _clean_text(article.text)

        return {
            "url": url,
            "domain": _extract_domain(url),
            "text_snippet": text[:MAX_SNIPPET],
            "fetched_at": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        return {
            "url": url,
            "domain": _extract_domain(url),
            "text_snippet": "",
            "fetched_at": None,
            "error": str(e)
        }


# =========================
# ASYNC WRAPPER
# =========================
async def scrape_urls(urls: List[str]) -> List[Dict]:
    loop = asyncio.get_event_loop()

    tasks = [
        loop.run_in_executor(EXECUTOR, _fetch_with_newspaper, url)
        for url in urls
    ]

    results = await asyncio.gather(*tasks)
    return results


# =========================
# PAYLOAD BUILDER
# =========================
def build_scraper_payload(
    claim_id: str,
    claim_text: str,
    scraped_sources: List[Dict],
    entities: Optional[List[str]] = None,
    context: Optional[Dict] = None
) -> Dict:

    return {
        "claim_id": claim_id,
        "claim_text": claim_text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "initial_urls": [
            {
                "url": s.get("url"),
                "domain": s.get("domain"),
                "snippet": s.get("text_snippet"),
                "fetched_at": s.get("fetched_at"),
                "metadata": {}
            }
            for s in scraped_sources
        ],
        "entities": entities or [],
        "context": context or {},
        "source_meta": {
            "producer": "scraper_newspaper4k_v2",
            "scrape_time": datetime.now(timezone.utc).isoformat()
        }
    }


# =========================
# HIGH LEVEL PIPELINE
# =========================
async def scrape_and_build(
    claim_id: str,
    claim_text: str,
    candidate_urls: List[str],
    entities: Optional[List[str]] = None,
    context: Optional[Dict] = None
) -> Dict:

    scraped = await scrape_urls(candidate_urls)

    return build_scraper_payload(
        claim_id,
        claim_text,
        scraped,
        entities=entities,
        context=context
    )


# =========================
# OPTIONAL: DIRECT AGENT HOOK
# =========================
async def scrape_and_send_to_agent(
    claim_id: str,
    claim_text: str,
    candidate_urls: List[str],
    agent_callable=None,
    entities: Optional[List[str]] = None,
    context: Optional[Dict] = None
) -> Dict:
    """
    Optional convenience function:
    scrape → build → send to agent
    """

    payload = await scrape_and_build(
        claim_id,
        claim_text,
        candidate_urls,
        entities,
        context
    )

    if agent_callable:
        return await agent_callable(payload)

    return payload