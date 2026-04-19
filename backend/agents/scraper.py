"""
News Scraper Agent
Combines crawl4ai (web scraping) + NewsAPI (structured news) for comprehensive coverage.
Free-tier aware: batches requests, respects rate limits, caches results.
"""

import asyncio
import hashlib
import json
import logging
import time
from typing import Optional
from urllib.parse import urlencode, urlparse

import httpx

logger = logging.getLogger(__name__)

# In-memory cache (resets on restart — good enough for free-tier)
_cache: dict[str, tuple[float, list]] = {}
CACHE_TTL = 900  # 15 minutes


def _cache_get(key: str) -> Optional[list]:
    if key in _cache:
        ts, data = _cache[key]
        if time.time() - ts < CACHE_TTL:
            return data
    return None


def _cache_set(key: str, data: list):
    _cache[key] = (time.time(), data)


class NewsScraperAgent:
    """
    Multi-source scraper:
    1. NewsAPI — structured, fast, free-tier: 100 req/day
    2. crawl4ai — raw web scraping for any URL, no API key needed
    3. Google News RSS — free, no key, good coverage
    """

    def __init__(self, news_api_key: str = ""):
        self.news_api_key = news_api_key
        self.news_api_base = "https://newsapi.org/v2"

    async def scrape(
        self,
        query: str,
        sources: Optional[list[str]] = None,
        max_results: int = 5,
    ) -> list[dict]:
        """
        Unified scraping: NewsAPI + RSS fallback + crawl4ai enrichment.
        Returns normalized article dicts.
        """
        cache_key = hashlib.md5(f"{query}:{sources}:{max_results}".encode()).hexdigest()
        cached = _cache_get(cache_key)
        if cached is not None:
            logger.info(f"Cache hit for '{query}'")
            return cached

        articles = []

        # ── Source 1: NewsAPI ─────────────────────────────────────
        if self.news_api_key:
            try:
                news_articles = await self._fetch_newsapi(query, max_results)
                articles.extend(news_articles)
                logger.info(f"NewsAPI: {len(news_articles)} articles for '{query}'")
            except Exception as e:
                logger.warning(f"NewsAPI failed: {e}")

        # ── Source 2: Google News RSS (free fallback) ─────────────
        if len(articles) < max_results:
            try:
                rss_articles = await self._fetch_google_news_rss(query, max_results - len(articles))
                articles.extend(rss_articles)
                logger.info(f"Google RSS: {len(rss_articles)} articles")
            except Exception as e:
                logger.warning(f"Google RSS failed: {e}")

        # ── Source 3: crawl4ai enrichment (top 2 articles) ───────
        enriched = []
        for article in articles[:2]:
            try:
                enriched_article = await self._crawl4ai_enrich(article)
                enriched.append(enriched_article)
            except Exception as e:
                logger.warning(f"crawl4ai enrich failed for {article.get('url')}: {e}")
                enriched.append(article)

        # Replace with enriched versions
        for i, enriched_article in enumerate(enriched):
            if i < len(articles):
                articles[i] = enriched_article

        _cache_set(cache_key, articles)
        return articles

    # ── NewsAPI ───────────────────────────────────────────────────

    async def _fetch_newsapi(self, query: str, max_results: int) -> list[dict]:
        params = {
            "q": query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": min(max_results, 10),
            "apiKey": self.news_api_key,
        }
        url = f"{self.news_api_base}/everything?{urlencode(params)}"

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

        articles = []
        for raw in data.get("articles", []):
            articles.append(self._normalize_newsapi(raw))
        return articles

    def _normalize_newsapi(self, raw: dict) -> dict:
        return {
            "title": raw.get("title", ""),
            "description": raw.get("description", ""),
            "content": raw.get("content", ""),
            "url": raw.get("url", ""),
            "published_at": raw.get("publishedAt", ""),
            "source": raw.get("source", {}).get("name", "Unknown"),
            "author": raw.get("author", ""),
            "image_url": raw.get("urlToImage", ""),
            "scrape_method": "newsapi",
        }

    # ── Google News RSS ───────────────────────────────────────────

    async def _fetch_google_news_rss(self, query: str, max_results: int) -> list[dict]:
        encoded_query = query.replace(" ", "+")
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"

        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content = resp.text

        articles = self._parse_rss(content, max_results)
        return articles

    def _parse_rss(self, xml: str, max_results: int) -> list[dict]:
        """Simple RSS parser without external deps."""
        import re
        articles = []

        items = re.findall(r'<item>(.*?)</item>', xml, re.DOTALL)
        for item in items[:max_results]:
            title_match = re.search(r'<title>(.*?)</title>', item, re.DOTALL)
            link_match = re.search(r'<link>(.*?)</link>', item, re.DOTALL)
            desc_match = re.search(r'<description>(.*?)</description>', item, re.DOTALL)
            pub_match = re.search(r'<pubDate>(.*?)</pubDate>', item, re.DOTALL)
            source_match = re.search(r'<source[^>]*>(.*?)</source>', item, re.DOTALL)

            title = self._clean_html(title_match.group(1) if title_match else "")
            link = link_match.group(1).strip() if link_match else ""
            description = self._clean_html(desc_match.group(1) if desc_match else "")
            source = self._clean_html(source_match.group(1) if source_match else urlparse(link).netloc)

            if title and link:
                articles.append({
                    "title": title,
                    "description": description,
                    "content": description,
                    "url": link,
                    "published_at": pub_match.group(1).strip() if pub_match else "",
                    "source": source,
                    "author": "",
                    "image_url": "",
                    "scrape_method": "google_rss",
                })

        return articles

    def _clean_html(self, text: str) -> str:
        import re
        text = re.sub(r'<[^>]+>', '', text)
        text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"').replace('&#39;', "'")
        return text.strip()

    # ── crawl4ai Enrichment ───────────────────────────────────────

    async def _crawl4ai_enrich(self, article: dict) -> dict:
        """
        Use crawl4ai to extract full article content.
        crawl4ai is a local Python library — no API calls, no cost.
        Falls back gracefully if not installed.
        """
        url = article.get("url", "")
        if not url or "google.com" in url:
            return article

        try:
            from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
            from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
            import json as _json

            browser_config = BrowserConfig(headless=True, verbose=False)
            run_config = CrawlerRunConfig(
                cache_mode=CacheMode.ENABLED,
                word_count_threshold=50,
                excluded_tags=["nav", "footer", "header", "aside", "script", "style"],
                exclude_external_links=True,
                remove_overlay_elements=True,
                wait_for="body",
                page_timeout=15000,
            )

            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=url, config=run_config)

            if result.success and result.markdown:
                content = result.markdown[:4000]  # Token budget
                article = {**article, "content": content, "scrape_method": "crawl4ai"}
                logger.info(f"crawl4ai enriched: {url[:60]}")

        except ImportError:
            logger.warning("crawl4ai not installed — using description as content")
        except Exception as e:
            logger.warning(f"crawl4ai failed for {url}: {e}")

        return article

    async def scrape_url_direct(self, url: str) -> dict:
        """Directly scrape a specific URL using crawl4ai."""
        article = {"url": url, "title": "", "description": "", "content": "", "source": urlparse(url).netloc}
        return await self._crawl4ai_enrich(article)
