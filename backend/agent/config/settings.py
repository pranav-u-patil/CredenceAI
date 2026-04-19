"""
verification_agent/config/settings.py
=======================================
Central configuration. Every value marked  # ← PLACEHOLDER  must be
replaced before production use. See docs/PLACEHOLDERS.md for a full guide.
"""

from __future__ import annotations
import os
from dataclasses import dataclass, field


@dataclass
class AgentSettings:
    # ── Budget / runtime limits ───────────────────────────────────────────────
    max_searches:   int   = 6
    max_elapsed_ms: int   = 30_000   # 30 s wall-clock budget per claim
    max_retries:    int   = 2
    agentic_mode:   str   = "scratch"
    enable_generative_review: bool = False

    # ── Bayesian prior ────────────────────────────────────────────────────────
    # 0.5 = maximum uncertainty (uninformative prior).
    # Tune upward (e.g. 0.6) if your scraper already pre-filters high-quality
    # sources, or downward (e.g. 0.35) for adversarial/rumour datasets.
    prior_p_true: float = 0.5       # ← PLACEHOLDER (domain-tune this)

    # ── Minimum independence threshold ───────────────────────────────────────
    min_independent_clusters: int = 3

    # ── Search back-end ───────────────────────────────────────────────────────
    # Options: "duckduckgo" | "serper" | "google_cse"
    search_backend: str = "duckduckgo"   # ← PLACEHOLDER if you want Serper/Google

    # Serper / Google CSE credentials (only used when search_backend != duckduckgo)
    serper_api_key:     str = os.getenv("SERPER_API_KEY", "YOUR_SERPER_API_KEY")         # ← PLACEHOLDER
    google_cse_id:      str = os.getenv("GOOGLE_CSE_ID",  "YOUR_GOOGLE_CSE_ID")          # ← PLACEHOLDER
    google_cse_api_key: str = os.getenv("GOOGLE_CSE_API_KEY", "YOUR_GOOGLE_API_KEY")     # ← PLACEHOLDER

    # ── Social media credentials ──────────────────────────────────────────────
    # Reddit: create app at https://www.reddit.com/prefs/apps
    reddit_client_id:     str = os.getenv("REDDIT_CLIENT_ID",     "YOUR_REDDIT_CLIENT_ID")      # ← PLACEHOLDER
    reddit_client_secret: str = os.getenv("REDDIT_CLIENT_SECRET", "YOUR_REDDIT_CLIENT_SECRET")  # ← PLACEHOLDER
    reddit_user_agent:    str = os.getenv("REDDIT_USER_AGENT",    "verification-agent/1.0")      # ← PLACEHOLDER

    # X (Twitter) API v2: https://developer.twitter.com/
    twitter_bearer_token: str = os.getenv("TWITTER_BEARER_TOKEN", "YOUR_TWITTER_BEARER_TOKEN")  # ← PLACEHOLDER

    # ── Fact-check APIs ───────────────────────────────────────────────────────
    # Google Fact Check Tools API: https://developers.google.com/fact-check/tools/api
    factcheck_api_key: str = os.getenv("FACTCHECK_API_KEY", "YOUR_FACTCHECK_API_KEY")   # ← PLACEHOLDER

    # ClaimBuster API: https://idir.uta.edu/claimbuster/
    claimbuster_api_key: str = os.getenv("CLAIMBUSTER_API_KEY", "YOUR_CLAIMBUSTER_KEY") # ← PLACEHOLDER

    # ── News API ──────────────────────────────────────────────────────────────
    # https://newsapi.org/  (free tier: 100 req/day, no production use)
    newsapi_key: str = os.getenv("NEWSAPI_KEY", "YOUR_NEWSAPI_KEY")                     # ← PLACEHOLDER

    # ── Market / financial data ───────────────────────────────────────────────
    # Finnhub: https://finnhub.io/  (free tier available)
    finnhub_api_key: str = os.getenv("FINNHUB_API_KEY", "YOUR_FINNHUB_API_KEY")         # ← PLACEHOLDER

    # ── Embedding service ─────────────────────────────────────────────────────
    # Options: "openai" | "sentence_transformers" | "cohere"
    embedding_backend: str = "sentence_transformers"   # ← PLACEHOLDER (switch to openai for production)
    openai_api_key:    str = os.getenv("OPENAI_API_KEY", "YOUR_OPENAI_API_KEY")         # ← PLACEHOLDER
    embedding_model:   str = "all-MiniLM-L6-v2"        # ← PLACEHOLDER (sentence-transformers local model)
    # For OpenAI: "text-embedding-3-small"

    # ── Evidence database ─────────────────────────────────────────────────────
    # PostgreSQL DSN or SQLite path for source-behavior history
    db_dsn: str = os.getenv(
        "EVIDENCE_DB_DSN",
        "sqlite:///./evidence.db"       # ← PLACEHOLDER — use PostgreSQL in production
    )

    # ── crawl4ai ─────────────────────────────────────────────────────────────
    # crawl4ai runs locally; set a custom browser executable if needed
    crawl4ai_headless: bool = True
    crawl4ai_timeout:  int  = 15       # seconds per page fetch

    # ── Sentiment model ───────────────────────────────────────────────────────
    # "finbert" for financial claims, "distilbert-sst2" for general
    sentiment_model: str = "ProsusAI/finbert"  # ← PLACEHOLDER (needs HuggingFace access)

    # ── LR mapping table ─────────────────────────────────────────────────────
    # Maps semantic similarity buckets → likelihood ratios.
    # Tune on your held-out labelled dataset.
    lr_mapping: dict = field(default_factory=lambda: {
        "high":   3.0,    # similarity ≥ 0.85   # ← PLACEHOLDER (calibrate empirically)
        "medium": 1.8,    # similarity 0.65–0.85 # ← PLACEHOLDER
        "low":    1.1,    # similarity 0.40–0.65 # ← PLACEHOLDER
        "noise":  0.9,    # similarity < 0.40    # ← PLACEHOLDER
    })

    # ── Trusted domains list (UI convenience only — zero-trust in scoring) ────
    # These are shown in dashboards but NEVER used to boost LR automatically.
    trusted_domains_display: list = field(default_factory=lambda: [
        "reuters.com", "apnews.com", "bbc.co.uk", "sec.gov",
        # ← PLACEHOLDER: add/remove as needed; has NO scoring effect
    ])
