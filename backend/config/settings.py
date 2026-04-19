"""
Configuration and settings for the News Intelligence Platform.
Token-budget aware settings for free-tier API usage.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Settings:
    # ── Server ────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True

    # ── Free-Tier Token Budget Guards ────────────────────────────
    # Gemini free: 15 req/min, 1M tokens/day
    GEMINI_MAX_TOKENS_PER_REQUEST: int = 2048     # keep responses concise
    GEMINI_MODEL: str = "gemini-1.5-flash"        # flash = cheapest, fastest
    GEMINI_RPM_LIMIT: int = 14                    # stay under 15 rpm
    GEMINI_REQUESTS_COOLDOWN: float = 4.5         # seconds between calls

    # NewsAPI free: 100 req/day
    NEWS_API_MAX_ARTICLES: int = 5                # per query
    NEWS_API_COOLDOWN: float = 2.0

    # Finnhub free: 60 req/min
    FINNHUB_COOLDOWN: float = 1.1

    # ── Crawl4AI ─────────────────────────────────────────────────
    CRAWL4AI_MAX_PAGES_PER_QUERY: int = 3
    CRAWL4AI_TIMEOUT: int = 15
    CRAWL4AI_MAX_CONTENT_CHARS: int = 4000        # truncate to save tokens

    # ── Caching ──────────────────────────────────────────────────
    CACHE_TTL_SECONDS: int = 900                   # 15 min cache

    # ── Risk Engine ──────────────────────────────────────────────
    RISK_THRESHOLDS: dict = field(default_factory=lambda: {
        "critical": 80,
        "high": 60,
        "medium": 40,
        "low": 0
    })

    # ── Sentiment ────────────────────────────────────────────────
    SENTIMENT_BATCH_SIZE: int = 10


# Singleton-like access
_settings: Optional[Settings] = None

def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
