"""
verification_agent/pipelines/social_sentiment.py
==================================================
Pipeline 2 — Social media sentiment & propagation analysis.

Sources: Reddit, X (Twitter), crawl4ai fallback for public pages.

PLACEHOLDERS
------------
  REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET  — Reddit OAuth2 app
  TWITTER_BEARER_TOKEN                     — X API v2 bearer token
  sentiment_model                          — HuggingFace model name
"""

from __future__ import annotations
import asyncio
import re
import uuid
from datetime import datetime
from typing import Any

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
    from CredenceAI.backend.utils.log import get_logger
except ImportError:
    try:
        from ...utils.log import get_logger
    except ImportError:
        from utils.log import get_logger

logger = get_logger(__name__)


async def run_social_sentiment(claim: ClaimInput, settings: AgentSettings) -> dict:
    """
    Returns:
        {
          "evidence_units": [...],
          "searches_performed": int,
          "social_clusters": list,
          "sentiment_strength": float,   # -1 .. +1
          "bot_score": float,            # 0 .. 1
          "propagation_velocity": float,
        }
    """
    reddit_task  = _fetch_reddit(claim, settings)
    twitter_task = _fetch_twitter(claim, settings)

    reddit_posts, twitter_posts = await asyncio.gather(
        reddit_task, twitter_task, return_exceptions=True
    )
    if isinstance(reddit_posts, Exception):
        logger.warning("Reddit fetch failed: %s", reddit_posts)
        reddit_posts = []
    if isinstance(twitter_posts, Exception):
        logger.warning("Twitter fetch failed: %s", twitter_posts)
        twitter_posts = []

    all_posts: list[dict] = list(reddit_posts) + list(twitter_posts)

    if not all_posts:
        return {
            "evidence_units": [],
            "searches_performed": 2,
            "social_clusters": [],
            "sentiment_strength": 0.0,
            "bot_score": 0.0,
            "propagation_velocity": 0.0,
        }

    # Sentiment analysis
    sentiments = _batch_sentiment([p["text"] for p in all_posts], settings)

    # Bot detection (heuristic)
    bot_scores = [_heuristic_bot_score(p) for p in all_posts]

    # Build evidence units
    units = []
    for i, post in enumerate(all_posts):
        sent_score = sentiments[i]
        bot_sc     = bot_scores[i]
        ind_weight = max(0.1, 1.0 - bot_sc)
        units.append({
            "id":                  str(uuid.uuid4()),
            "type":                "support" if sent_score > 0.1 else ("contradict" if sent_score < -0.1 else "anomaly"),
            "domain":              post.get("platform", "social"),
            "url":                 post.get("url", ""),
            "timestamp":           post.get("created_at"),
            "similarity":          abs(sent_score),
            "lr":                  _sentiment_to_lr(sent_score),
            "independence_weight": round(ind_weight, 3),
            "cluster_id":          post.get("platform", "social"),
            "provenance":          "social_sentiment",
            "raw_snippet":         post["text"][:300],
            "sentiment_score":     round(sent_score, 4),
            "bot_score":           round(bot_sc, 4),
        })

    avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.0
    avg_bot       = sum(bot_scores) / len(bot_scores) if bot_scores else 0.0
    velocity      = _social_velocity(all_posts, claim.timestamp)

    return {
        "evidence_units":        units,
        "searches_performed":    2,
        "social_clusters":       [{"platform": "reddit", "count": len(reddit_posts)},
                                   {"platform": "twitter", "count": len(twitter_posts)}],
        "sentiment_strength":    round(avg_sentiment, 4),
        "bot_score":             round(avg_bot, 4),
        "propagation_velocity":  velocity,
    }


# ── Reddit ────────────────────────────────────────────────────────────────────

async def _fetch_reddit(claim: ClaimInput, settings: AgentSettings) -> list[dict]:
    """
    Uses PRAW (Python Reddit API Wrapper).
    Requires: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET   # ← PLACEHOLDER
    Fallback: crawl4ai to scrape old.reddit.com search results.
    """
    try:
        import praw                                  # pip install praw
        if settings.reddit_client_id.startswith("YOUR_"):
            raise ValueError("Reddit credentials not configured")

        reddit = praw.Reddit(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            user_agent=settings.reddit_user_agent,
        )
        entity_query = " ".join(claim.entities[:3]) or claim.claim_text[:80]
        posts = []
        for submission in reddit.subreddit("all").search(
            entity_query, sort="new", time_filter="week", limit=25
        ):
            posts.append({
                "platform":   "reddit",
                "text":       (submission.title + " " + (submission.selftext or ""))[:600],
                "url":        f"https://reddit.com{submission.permalink}",
                "created_at": datetime.utcfromtimestamp(submission.created_utc),
                "score":      submission.score,
                "author":     str(submission.author),
            })
        return posts

    except (ImportError, ValueError) as exc:
        logger.info("PRAW unavailable (%s); using crawl4ai Reddit fallback", exc)
        return await _reddit_crawl_fallback(claim, settings)


async def _reddit_crawl_fallback(claim: ClaimInput, settings: AgentSettings) -> list[dict]:
    query = "+".join(claim.entities[:2]) or claim.claim_text[:50]
    url   = f"https://www.reddit.com/search/?q={query}&sort=new&t=week"
    try:
        from crawl4ai import AsyncWebCrawler          # pip install crawl4ai
        async with AsyncWebCrawler(headless=settings.crawl4ai_headless) as crawler:
            result = await crawler.arun(url=url, bypass_cache=True,
                                        timeout=settings.crawl4ai_timeout)
            text = result.markdown or ""
            # Very rough extraction of post titles from markdown
            titles = re.findall(r'\*\*(.+?)\*\*', text)[:20]
            return [{"platform": "reddit", "text": t, "url": url, "created_at": None, "score": 0, "author": ""} for t in titles]
    except Exception as exc:
        logger.debug("Reddit crawl fallback failed: %s", exc)
        return []


# ── Twitter / X ───────────────────────────────────────────────────────────────

async def _fetch_twitter(claim: ClaimInput, settings: AgentSettings) -> list[dict]:
    """
    Uses Twitter API v2 via httpx.
    Requires: TWITTER_BEARER_TOKEN   # ← PLACEHOLDER
    """
    if settings.twitter_bearer_token.startswith("YOUR_"):
        logger.info("Twitter bearer token not set; skipping")
        return []
    try:
        import httpx
        query = _build_twitter_query(claim)
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.twitter.com/2/tweets/search/recent",
                headers={"Authorization": f"Bearer {settings.twitter_bearer_token}"},
                params={
                    "query":       query,
                    "max_results": 50,
                    "tweet.fields": "created_at,author_id,public_metrics",
                },
            )
        data = resp.json()
        posts = []
        for tweet in data.get("data", []):
            posts.append({
                "platform":   "twitter",
                "text":       tweet.get("text", ""),
                "url":        f"https://twitter.com/i/web/status/{tweet['id']}",
                "created_at": _parse_twitter_ts(tweet.get("created_at")),
                "score":      tweet.get("public_metrics", {}).get("like_count", 0),
                "author":     tweet.get("author_id", ""),
                "metrics":    tweet.get("public_metrics", {}),
            })
        return posts
    except Exception as exc:
        logger.warning("Twitter fetch failed: %s", exc)
        return []


def _build_twitter_query(claim: ClaimInput) -> str:
    entities = " OR ".join(f'"{e}"' for e in claim.entities[:2]) if claim.entities else ""
    keywords = claim.claim_text.split()[:5]
    base     = " ".join(keywords)
    q        = f"({entities} OR {base}) lang:en -is:retweet"
    return q[:512]


def _parse_twitter_ts(ts_str: str | None) -> datetime | None:
    if not ts_str:
        return None
    try:
        return datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%S.%fZ")
    except Exception:
        return None


# ── Sentiment ─────────────────────────────────────────────────────────────────

def _batch_sentiment(texts: list[str], settings: AgentSettings) -> list[float]:
    """
    Returns a list of floats in [-1, +1].
    Positive = claim-supportive tone, negative = contradicting.

    Uses HuggingFace transformers pipeline.  # ← PLACEHOLDER: requires GPU for speed
    Falls back to VADER (lightweight) if transformers not available.
    """
    if not texts:
        return []
    try:
        from transformers import pipeline as hf_pipeline       # pip install transformers torch
        _pipe = hf_pipeline("sentiment-analysis", model=settings.sentiment_model,
                             truncation=True, max_length=512)
        results = _pipe(texts)
        scores = []
        for r in results:
            label = r.get("label", "").lower()
            score = r.get("score", 0.5)
            # FinBERT labels: positive/negative/neutral
            if "positive" in label:
                scores.append(score)
            elif "negative" in label:
                scores.append(-score)
            else:
                scores.append(0.0)
        return scores
    except ImportError:
        return _vader_sentiment(texts)
    except Exception as exc:
        logger.warning("HuggingFace sentiment failed: %s; using VADER", exc)
        return _vader_sentiment(texts)


def _vader_sentiment(texts: list[str]) -> list[float]:
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer  # pip install vaderSentiment
        analyzer = SentimentIntensityAnalyzer()
        return [analyzer.polarity_scores(t)["compound"] for t in texts]
    except ImportError:
        logger.warning("vaderSentiment not installed; returning neutral sentiment")
        return [0.0] * len(texts)


# ── Bot detection ─────────────────────────────────────────────────────────────

def _heuristic_bot_score(post: dict) -> float:
    """
    Simple heuristic: 0 = human, 1 = bot.
    Production: replace with a trained classifier.  # ← PLACEHOLDER
    Signals:
      - Very high score/karma with zero text (vote manipulation)
      - Account name contains long digit strings
      - Post created_at is None (API gap = often scraped/injected)
    """
    score = 0.0
    author = str(post.get("author", ""))
    if re.search(r'\d{6,}', author):
        score += 0.3
    if post.get("score", 0) > 10_000 and len(post.get("text", "")) < 20:
        score += 0.4
    if post.get("created_at") is None:
        score += 0.1
    return min(score, 1.0)


def _sentiment_to_lr(sentiment: float) -> float:
    """Map sentiment [-1,+1] to likelihood ratio."""
    if sentiment > 0.5:
        return 1.8
    elif sentiment > 0.1:
        return 1.2
    elif sentiment < -0.5:
        return 0.4
    elif sentiment < -0.1:
        return 0.7
    return 1.0


def _social_velocity(posts: list[dict], claim_ts: datetime) -> float:
    if not posts:
        return 0.0
    recent = sum(
        1 for p in posts
        if isinstance(p.get("created_at"), datetime)
        and abs((p["created_at"] - claim_ts).total_seconds()) / 3600 <= 6
    )
    return round(recent / len(posts), 3)
