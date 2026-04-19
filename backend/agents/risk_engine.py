"""
Risk Engine — Multi-Factor News Risk Assessment
Combines: narrative risk scoring + Finnhub market data + sentiment + source credibility.
Free-tier aware: Finnhub free = 60 req/min, caches aggressively.
"""

import asyncio
import hashlib
import logging
import re
import time
from typing import Optional

import httpx

from config.settings import Settings

logger = logging.getLogger(__name__)
settings = Settings()

# In-memory cache
_finhub_cache: dict[str, tuple[float, dict]] = {}

# ── Risk Factor Keyword Banks ─────────────────────────────────────────────────

CRITICAL_RISK_KEYWORDS = [
    "nuclear", "bioweapon", "pandemic", "market crash", "systemic collapse",
    "bank run", "sovereign default", "hyperinflation", "coup", "martial law",
    "catastrophic", "existential", "mass casualty",
]

HIGH_RISK_KEYWORDS = [
    "recession", "bankruptcy", "fraud", "investigation", "sanctions",
    "war", "conflict", "attack", "hack", "breach", "crisis",
    "collapse", "default", "contagion", "outbreak", "protest",
    "assassination", "explosion", "terrorist",
]

MEDIUM_RISK_KEYWORDS = [
    "concern", "warning", "risk", "volatile", "uncertainty", "decline",
    "drop", "fall", "dispute", "tension", "pressure", "challenge",
    "shortage", "disruption", "delay", "downgrade",
]

GEOPOLITICAL_KEYWORDS = [
    "china", "russia", "iran", "north korea", "taiwan", "ukraine",
    "middle east", "nato", "sanctions", "trade war", "tariff",
]

MARKET_RISK_KEYWORDS = [
    "fed", "interest rate", "inflation", "earnings miss", "guidance cut",
    "layoffs", "restructuring", "ipo canceled", "deal collapse",
]


class RiskEngine:
    """
    Risk scoring algorithm:
    1. Keyword density analysis (0-40 pts)
    2. Sentiment correlation (0-20 pts)
    3. Source credibility impact (0-20 pts)
    4. Market data overlay via Finnhub (0-20 pts)
    5. Geopolitical amplifier
    Total: 0-100 risk score → low/medium/high/critical
    """

    def __init__(self, finnhub_api_key: str = ""):
        self.finnhub_key = finnhub_api_key
        self.finnhub_base = "https://finnhub.io/api/v1"
        self._last_finnhub_call = 0.0

    async def assess(
        self,
        articles: list[dict],
        queries: list[str],
        risk_keywords: list[str],
        sentiment_summary: dict,
        source_profiles: dict,
    ) -> dict:
        """Full risk assessment. Returns risk report dict."""

        all_text = " ".join([
            f"{a.get('title','')} {a.get('description','')}"
            for a in articles
        ]).lower()

        # ── Component 1: Keyword Risk (0-40) ─────────────────────
        keyword_score, triggered_keywords = self._score_keywords(
            all_text, risk_keywords
        )

        # ── Component 2: Sentiment Risk (0-20) ───────────────────
        sentiment_score = self._score_sentiment(sentiment_summary)

        # ── Component 3: Source Credibility (0-20) ───────────────
        credibility_score = self._score_credibility(source_profiles)

        # ── Component 4: Market Data (0-20) ──────────────────────
        market_score = 0
        market_data = {}
        if self.finnhub_key:
            market_data = await self._fetch_market_signals(queries)
            market_score = self._score_market(market_data)

        # ── Component 5: Geopolitical Amplifier ──────────────────
        geo_amplifier = self._geopolitical_amplifier(all_text)

        # ── Total Score ───────────────────────────────────────────
        base_score = keyword_score + sentiment_score + credibility_score + market_score
        total_score = min(100, int(base_score * geo_amplifier))

        # ── Risk Level ────────────────────────────────────────────
        thresholds = settings.RISK_THRESHOLDS
        if total_score >= thresholds["critical"]:
            level = "critical"
        elif total_score >= thresholds["high"]:
            level = "high"
        elif total_score >= thresholds["medium"]:
            level = "medium"
        else:
            level = "low"

        # ── Risk Factors ──────────────────────────────────────────
        risk_factors = self._extract_risk_factors(
            all_text, triggered_keywords, sentiment_summary, market_data
        )

        # ── Recommendations ───────────────────────────────────────
        recommendations = self._generate_recommendations(level, risk_factors, sentiment_summary)

        return {
            "overall_risk": level,
            "risk_score": total_score,
            "components": {
                "keyword_risk": round(keyword_score, 1),
                "sentiment_risk": round(sentiment_score, 1),
                "credibility_risk": round(credibility_score, 1),
                "market_risk": round(market_score, 1),
                "geopolitical_multiplier": round(geo_amplifier, 2),
            },
            "risk_factors": risk_factors,
            "triggered_keywords": triggered_keywords[:10],
            "market_data": market_data,
            "recommendations": recommendations,
            "methodology": "Keyword density + Sentiment correlation + Source credibility + Market signals",
        }

    # ── Scoring Components ────────────────────────────────────────

    def _score_keywords(self, text: str, extra_keywords: list[str]) -> tuple[float, list[str]]:
        """Score 0-40 based on risk keyword presence."""
        triggered = []
        score = 0.0

        for kw in CRITICAL_RISK_KEYWORDS:
            if kw in text:
                score += 8.0
                triggered.append(f"[CRITICAL] {kw}")

        for kw in HIGH_RISK_KEYWORDS:
            if kw in text:
                score += 3.5
                triggered.append(f"[HIGH] {kw}")

        for kw in MEDIUM_RISK_KEYWORDS:
            if kw in text:
                score += 1.5
                triggered.append(f"[MEDIUM] {kw}")

        for kw in extra_keywords:
            if kw.lower() in text:
                score += 2.0
                triggered.append(f"[CUSTOM] {kw}")

        return min(40.0, score), triggered

    def _score_sentiment(self, sentiment_summary: dict) -> float:
        """Score 0-20. More negative sentiment → higher risk."""
        avg_score = sentiment_summary.get("average_score", 0)
        neg_pct = sentiment_summary.get("negative_pct", 0)
        volatility = sentiment_summary.get("volatility", 0)

        # Negative sentiment contributes to risk
        sentiment_risk = max(0, -avg_score) * 10  # 0-10
        # High negativity ratio
        ratio_risk = neg_pct * 7  # 0-7
        # High volatility = uncertainty = risk
        vol_risk = volatility * 5  # 0-5 (approx)

        return min(20.0, sentiment_risk + ratio_risk + vol_risk)

    def _score_credibility(self, source_profiles: dict) -> float:
        """Score 0-20. Low credibility sources amplify risk perception."""
        if not source_profiles:
            return 5.0  # Unknown sources = moderate risk

        credibility_scores = [
            p.get("credibility_score", 50) for p in source_profiles.values()
        ]
        avg_cred = sum(credibility_scores) / len(credibility_scores)

        # Low credibility = potential misinformation risk
        low_cred_count = sum(1 for s in credibility_scores if s < 40)
        low_cred_penalty = low_cred_count * 3

        # Inverse: low credibility → higher risk score
        base = (100 - avg_cred) / 10  # 0-10
        return min(20.0, base + low_cred_penalty)

    def _score_market(self, market_data: dict) -> float:
        """Score 0-20 based on Finnhub market signals."""
        if not market_data:
            return 0.0

        score = 0.0

        # News sentiment from Finnhub
        fin_sentiment = market_data.get("finnhub_sentiment", {})
        fin_score = fin_sentiment.get("companyNewsScore", 0)
        if isinstance(fin_score, (int, float)):
            # Finnhub: 0=bearish, 1=bullish. Convert to risk
            if fin_score < 0.3:
                score += 12.0  # bearish = high risk
            elif fin_score < 0.5:
                score += 6.0

        # Market cap and volatility signals
        quote = market_data.get("quote", {})
        change_pct = quote.get("dp", 0)  # daily % change
        if isinstance(change_pct, (int, float)) and abs(change_pct) > 5:
            score += 8.0  # Big moves = risk

        return min(20.0, score)

    def _geopolitical_amplifier(self, text: str) -> float:
        """Multiplier 1.0-1.5 based on geopolitical keyword density."""
        count = sum(1 for kw in GEOPOLITICAL_KEYWORDS if kw in text)
        if count >= 5:
            return 1.5
        elif count >= 3:
            return 1.3
        elif count >= 1:
            return 1.15
        return 1.0

    def _extract_risk_factors(self, text, triggered_keywords, sentiment_summary, market_data) -> list[str]:
        """Human-readable risk factor descriptions."""
        factors = []

        if any("[CRITICAL]" in k for k in triggered_keywords):
            factors.append("Critical-severity risk keywords detected in coverage")

        if sentiment_summary.get("negative_pct", 0) > 0.6:
            factors.append(f"High negative sentiment ratio: {sentiment_summary['negative_pct']:.0%}")

        if "fear" in sentiment_summary.get("top_emotions", {}):
            factors.append("Fear emotion dominant in news narrative")

        if "urgency" in sentiment_summary.get("top_emotions", {}):
            factors.append("High urgency signals detected across sources")

        geo_count = sum(1 for kw in GEOPOLITICAL_KEYWORDS if kw in text)
        if geo_count >= 3:
            factors.append(f"Strong geopolitical exposure ({geo_count} indicators)")

        if market_data.get("quote", {}).get("dp", 0) and abs(market_data["quote"]["dp"]) > 5:
            factors.append(f"Significant market movement: {market_data['quote']['dp']:.1f}% daily change")

        if sentiment_summary.get("trend") == "deteriorating":
            factors.append("Sentiment trending negative over time")

        if sentiment_summary.get("volatility", 0) > 0.4:
            factors.append("High sentiment volatility — conflicting narratives detected")

        return factors[:8]

    def _generate_recommendations(self, level: str, factors: list[str], sentiment: dict) -> list[str]:
        recs = {
            "critical": [
                "Immediate escalation to risk management team required",
                "Activate crisis communication protocols",
                "Monitor situation in real-time, review every 30 minutes",
                "Consider defensive positions if market exposure exists",
                "Cross-reference with primary sources immediately",
            ],
            "high": [
                "Increase monitoring frequency to every 2 hours",
                "Review exposure to entities mentioned in coverage",
                "Prepare contingency communications",
                "Verify claims with authoritative sources",
            ],
            "medium": [
                "Monitor for escalation in next 24 hours",
                "Review coverage from multiple source perspectives",
                "Document developing situation for audit trail",
            ],
            "low": [
                "Routine monitoring continues",
                "Flag for next scheduled review",
            ],
        }
        return recs.get(level, ["Continue standard monitoring"])

    # ── Finnhub Integration ───────────────────────────────────────

    async def _rate_limited_finnhub(self) -> None:
        elapsed = time.time() - self._last_finnhub_call
        if elapsed < settings.FINNHUB_COOLDOWN:
            await asyncio.sleep(settings.FINNHUB_COOLDOWN - elapsed)
        self._last_finnhub_call = time.time()

    async def _fetch_market_signals(self, queries: list[str]) -> dict:
        """Fetch Finnhub market data relevant to queries. Cached."""
        cache_key = hashlib.md5(str(sorted(queries)).encode()).hexdigest()
        if cache_key in _finhub_cache:
            ts, data = _finhub_cache[cache_key]
            if time.time() - ts < 300:  # 5 min cache
                return data

        result = {}

        # Try to extract ticker symbols from queries
        tickers = self._extract_tickers(queries)

        if tickers:
            try:
                await self._rate_limited_finnhub()
                ticker = tickers[0]  # Just fetch first to conserve quota
                async with httpx.AsyncClient(timeout=8) as client:
                    # Get quote
                    resp = await client.get(
                        f"{self.finnhub_base}/quote",
                        params={"symbol": ticker, "token": self.finnhub_key}
                    )
                    if resp.status_code == 200:
                        result["quote"] = resp.json()
                        result["ticker"] = ticker

                    await self._rate_limited_finnhub()
                    # Get company news sentiment
                    resp2 = await client.get(
                        f"{self.finnhub_base}/news-sentiment",
                        params={"symbol": ticker, "token": self.finnhub_key}
                    )
                    if resp2.status_code == 200:
                        result["finnhub_sentiment"] = resp2.json()

            except Exception as e:
                logger.warning(f"Finnhub fetch failed: {e}")

        # Always fetch general market news sentiment
        try:
            await self._rate_limited_finnhub()
            async with httpx.AsyncClient(timeout=8) as client:
                resp = await client.get(
                    f"{self.finnhub_base}/news",
                    params={"category": "general", "token": self.finnhub_key}
                )
                if resp.status_code == 200:
                    news = resp.json()[:3]  # Just top 3
                    result["market_headlines"] = [
                        {"headline": n.get("headline", ""), "source": n.get("source", "")}
                        for n in news
                    ]
        except Exception as e:
            logger.warning(f"Finnhub news fetch failed: {e}")

        _finhub_cache[cache_key] = (time.time(), result)
        return result

    def _extract_tickers(self, queries: list[str]) -> list[str]:
        """Extract potential stock ticker symbols from queries."""
        # Common patterns: all-caps 1-5 letter words, or $ prefix
        tickers = []
        for q in queries:
            # $TSLA pattern
            dollar_matches = re.findall(r'\$([A-Z]{1,5})', q)
            tickers.extend(dollar_matches)
            # ALL-CAPS word 2-5 chars
            caps_matches = re.findall(r'\b([A-Z]{2,5})\b', q)
            tickers.extend(caps_matches)

        # Filter out common non-ticker caps words
        exclude = {"AI", "US", "UK", "EU", "CEO", "CFO", "IPO", "GDP", "FBI", "CIA", "SEC", "NYSE", "AND", "THE"}
        return [t for t in tickers if t not in exclude][:3]
