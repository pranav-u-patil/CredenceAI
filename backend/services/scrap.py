from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
from urllib.parse import urlparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
import hashlib

from newspaper import Article

# =========================
# CONFIG
# =========================
MAX_SNIPPET = 3000
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


def _iso_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    try:
        return str(value)
    except Exception:
        return None


# =========================
# CORE SCRAPER (BLOCKING)
# =========================
def _fetch_with_newspaper(url: str) -> Dict:
    try:
        article = Article(url)
        article.download()
        article.parse()

        text = _clean_text(article.text)
        title = _clean_text(article.title)
        summary = _clean_text(" ".join((article.summary or "").split())) if getattr(article, "summary", None) else ""
        authors = [author for author in (article.authors or []) if author]
        top_image = getattr(article, "top_image", None) or None
        published_at = _iso_or_none(getattr(article, "publish_date", None))
        content_hash = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16] if text else None

        return {
            "url": url,
            "domain": _extract_domain(url),
            "title": title,
            "content": text,
            "snippet": text[:MAX_SNIPPET],
            "summary": summary or text[:420],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "published_at": published_at,
            "authors": authors,
            "top_image": top_image,
            "content_hash": content_hash,
            "status": "success",
            "error": None,
            "length": len(text),
        }

    except Exception as e:
        return {
            "url": url,
            "domain": _extract_domain(url),
            "title": "",
            "content": "",
            "snippet": "",
            "summary": "",
            "fetched_at": None,
            "published_at": None,
            "authors": [],
            "top_image": None,
            "content_hash": None,
            "status": "failed",
            "error": str(e),
            "length": 0,
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


async def scrape_article_preview(url: str) -> Dict:
    results = await scrape_urls([url])
    return results[0] if results else {
        "url": url,
        "domain": _extract_domain(url),
        "title": "",
        "content": "",
        "snippet": "",
        "summary": "",
        "fetched_at": None,
        "published_at": None,
        "authors": [],
        "top_image": None,
        "content_hash": None,
        "status": "failed",
        "error": "Unable to scrape article",
        "length": 0,
    }


def build_claim_from_preview(
    url: str,
    preview: Dict,
    claim_id: str,
    claim_text: Optional[str] = None,
    entities: Optional[List[str]] = None,
    context: Optional[Dict] = None,
) -> Dict:
    effective_claim = (claim_text or preview.get("title") or preview.get("summary") or preview.get("snippet") or url).strip()

    return {
        "claim_id": claim_id,
        "claim_text": effective_claim,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "initial_urls": [
            {
                "url": url,
                "domain": preview.get("domain"),
                "snippet": preview.get("snippet") or preview.get("summary") or "",
                "fetched_at": preview.get("fetched_at"),
                "metadata": {
                    "title": preview.get("title"),
                    "summary": preview.get("summary"),
                    "published_at": preview.get("published_at"),
                    "authors": preview.get("authors", []),
                    "top_image": preview.get("top_image"),
                    "content_hash": preview.get("content_hash"),
                    "content_length": preview.get("length", 0),
                },
            }
        ],
        "entities": entities or [],
        "context": context or {},
        "source_meta": {
            "producer": "frontend_url_preview",
            "preview_title": preview.get("title"),
        },
    }


# =========================
# VERIFICATION PAYLOAD
# =========================
def build_verification_payload(
    claim_id: str,
    claim_text: str,
    scraped_sources: List[Dict],
    entities: Optional[List[str]] = None,
    context: Optional[Dict] = None
) -> Dict:

    successful = [s for s in scraped_sources if s["status"] == "success"]
    failed = [s for s in scraped_sources if s["status"] == "failed"]

    return {
        "claim_id": claim_id,
        "claim_text": claim_text,
        "timestamp": datetime.now(timezone.utc).isoformat(),

        # 🔥 Core data for frontend
        "sources": [
            {
                "url": s["url"],
                "domain": s["domain"],
                "snippet": s["snippet"],
                "fetched_at": s["fetched_at"],
                "length": s["length"]
            }
            for s in successful
        ],

        # ⚠️ Debug / observability
        "failed_sources": failed,

        # 📊 Useful for scoring / ML later
        "meta": {
            "total_sources": len(scraped_sources),
            "successful_sources": len(successful),
            "failed_sources": len(failed),
            "success_rate": (
                len(successful) / len(scraped_sources)
                if scraped_sources else 0
            )
        },

        # 🧠 For downstream agent
        "entities": entities or [],
        "context": context or {},

        "producer": "scraper_newspaper4k_v3"
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

    if not candidate_urls:
        return {
            "claim_id": claim_id,
            "claim_text": claim_text,
            "sources": [],
            "failed_sources": [],
            "meta": {
                "total_sources": 0,
                "successful_sources": 0,
                "failed_sources": 0,
                "success_rate": 0
            },
            "error": "No URLs provided"
        }

    scraped = await scrape_urls(candidate_urls)

    return build_verification_payload(
        claim_id,
        claim_text,
        scraped,
        entities=entities,
        context=context
    )


# =========================
# OPTIONAL: AGENT HOOK
# =========================
async def scrape_and_send_to_agent(
    claim_id: str,
    claim_text: str,
    candidate_urls: List[str],
    agent_callable=None,
    entities: Optional[List[str]] = None,
    context: Optional[Dict] = None
) -> Dict:

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
