"""
Sentiment Analyzer — Local NLP, Zero API Cost
Uses VADER + TextBlob + custom financial lexicon for news-specific sentiment.
No external API calls — runs entirely local. Free forever.
"""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ── Financial / News Lexicon ──────────────────────────────────────────────────
# Custom weights for news-domain terms VADER misses

FINANCIAL_LEXICON = {
    # Strongly negative
    "bankrupt": -3.5, "bankruptcy": -3.5, "default": -2.8, "fraud": -3.2,
    "scandal": -2.9, "collapse": -3.0, "crash": -2.8, "plunge": -2.5,
    "crisis": -2.7, "recession": -2.5, "layoffs": -2.2, "laid off": -2.3,
    "investigation": -1.8, "lawsuit": -1.9, "fine": -1.5, "penalty": -1.7,
    "downgrade": -2.0, "miss": -1.5, "below expectations": -2.2,
    "war": -3.0, "attack": -2.5, "conflict": -2.2, "sanctions": -2.0,
    "inflation": -1.8, "debt": -1.5, "deficit": -1.7, "shortage": -1.9,

    # Strongly positive
    "record high": 3.0, "record profit": 3.2, "breakthrough": 2.8,
    "acquisition": 1.5, "merger": 1.2, "partnership": 1.5, "deal": 1.2,
    "beat expectations": 2.5, "outperform": 2.2, "upgrade": 2.0,
    "growth": 1.8, "surge": 2.2, "rally": 2.0, "boom": 2.3,
    "innovation": 2.0, "approval": 2.0, "launch": 1.5, "expansion": 1.8,
    "profit": 1.8, "revenue up": 2.2, "earnings beat": 2.5,

    # Risk signals
    "warning": -1.8, "risk": -1.5, "concern": -1.3, "uncertainty": -1.5,
    "volatile": -1.7, "instability": -1.9, "threat": -2.0,
}

# Emotion categories
EMOTION_KEYWORDS = {
    "fear": ["fear", "afraid", "panic", "terror", "alarming", "danger", "threat", "warning"],
    "anger": ["outrage", "angry", "furious", "condemn", "blame", "dispute", "clash"],
    "hope": ["hope", "optimistic", "promise", "potential", "opportunity", "confident"],
    "uncertainty": ["uncertain", "unclear", "unknown", "question", "doubt", "speculation"],
    "urgency": ["urgent", "emergency", "critical", "immediate", "breaking", "alert"],
}


class SentimentAnalyzer:
    """
    Multi-layered sentiment analysis:
    Layer 1: VADER (fast, general)
    Layer 2: Custom financial lexicon overlay
    Layer 3: Emotion detection
    Layer 4: Subjectivity scoring
    """

    def __init__(self):
        self._vader = None
        self._textblob_available = False
        self._init_models()

    def _init_models(self):
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
            self._vader = SentimentIntensityAnalyzer()
            # Inject custom lexicon
            self._vader.lexicon.update(FINANCIAL_LEXICON)
            logger.info("VADER initialized with financial lexicon")
        except ImportError:
            logger.warning("vaderSentiment not installed — using rule-based fallback")

        try:
            from textblob import TextBlob
            self._textblob_available = True
        except ImportError:
            logger.warning("TextBlob not installed — skipping subjectivity")

    def analyze(self, text: str) -> dict:
        """Analyze sentiment of a single text. Returns score dict."""
        if not text or len(text.strip()) < 10:
            return self._empty_result()

        text = text[:2000]  # Limit for performance
        result = {}

        # ── Layer 1: VADER ────────────────────────────────────────
        if self._vader:
            scores = self._vader.polarity_scores(text)
            compound = scores["compound"]
            result["vader_compound"] = round(compound, 4)
            result["vader_pos"] = round(scores["pos"], 3)
            result["vader_neg"] = round(scores["neg"], 3)
            result["vader_neu"] = round(scores["neu"], 3)
        else:
            compound = self._rule_based_score(text)
            result["vader_compound"] = round(compound, 4)

        # ── Layer 2: Sentiment label ──────────────────────────────
        compound = result["vader_compound"]
        if compound >= 0.15:
            label = "positive"
        elif compound <= -0.15:
            label = "negative"
        else:
            label = "neutral"

        result["sentiment"] = label
        result["score"] = compound

        # ── Layer 3: Intensity ────────────────────────────────────
        abs_score = abs(compound)
        if abs_score >= 0.7:
            intensity = "strong"
        elif abs_score >= 0.35:
            intensity = "moderate"
        else:
            intensity = "mild"
        result["intensity"] = intensity

        # ── Layer 4: Emotions ─────────────────────────────────────
        text_lower = text.lower()
        emotions_detected = {}
        for emotion, keywords in EMOTION_KEYWORDS.items():
            count = sum(1 for kw in keywords if kw in text_lower)
            if count > 0:
                emotions_detected[emotion] = min(count / 3, 1.0)  # normalize 0-1
        result["emotions"] = emotions_detected

        # ── Layer 5: Subjectivity (TextBlob) ─────────────────────
        if self._textblob_available:
            try:
                from textblob import TextBlob
                tb = TextBlob(text[:500])
                result["subjectivity"] = round(tb.sentiment.subjectivity, 3)
            except:
                result["subjectivity"] = 0.5
        else:
            result["subjectivity"] = self._estimate_subjectivity(text)

        # ── Layer 6: Financial signal keywords ───────────────────
        fin_signals = []
        for term, weight in FINANCIAL_LEXICON.items():
            if term.lower() in text_lower:
                fin_signals.append({"term": term, "weight": weight})
        result["financial_signals"] = sorted(fin_signals, key=lambda x: abs(x["weight"]), reverse=True)[:5]

        return result

    def aggregate(self, results: list[dict]) -> dict:
        """Aggregate sentiment across multiple articles."""
        if not results:
            return {"overall": "neutral", "positive_pct": 0, "negative_pct": 0, "neutral_pct": 1}

        scores = [r.get("score", 0) for r in results]
        labels = [r.get("sentiment", "neutral") for r in results]
        n = len(results)

        pos_count = labels.count("positive")
        neg_count = labels.count("negative")
        neu_count = labels.count("neutral")

        avg_score = sum(scores) / n if n > 0 else 0

        # Aggregate emotions
        all_emotions: dict[str, float] = {}
        for r in results:
            for emotion, strength in r.get("emotions", {}).items():
                all_emotions[emotion] = all_emotions.get(emotion, 0) + strength
        top_emotions = sorted(all_emotions.items(), key=lambda x: x[1], reverse=True)[:3]

        # Overall label
        if avg_score >= 0.1:
            overall = "positive"
        elif avg_score <= -0.1:
            overall = "negative"
        else:
            overall = "neutral"

        return {
            "overall": overall,
            "average_score": round(avg_score, 4),
            "positive_pct": round(pos_count / n, 3),
            "negative_pct": round(neg_count / n, 3),
            "neutral_pct": round(neu_count / n, 3),
            "article_count": n,
            "top_emotions": dict(top_emotions),
            "volatility": round(self._std_dev(scores), 4),
            "trend": self._detect_trend(scores),
        }

    def _detect_trend(self, scores: list[float]) -> str:
        """Detect sentiment trend across time-ordered articles."""
        if len(scores) < 3:
            return "stable"
        first_half = sum(scores[:len(scores)//2]) / (len(scores)//2)
        second_half = sum(scores[len(scores)//2:]) / (len(scores) - len(scores)//2)
        diff = second_half - first_half
        if diff > 0.15:
            return "improving"
        elif diff < -0.15:
            return "deteriorating"
        return "stable"

    def _std_dev(self, values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5

    def _rule_based_score(self, text: str) -> float:
        """Fallback when VADER not available."""
        text_lower = text.lower()
        score = 0.0
        count = 0
        for term, weight in FINANCIAL_LEXICON.items():
            if term in text_lower:
                score += weight
                count += 1
        if count == 0:
            return 0.0
        # Normalize to -1..1 range
        return max(-1.0, min(1.0, score / (count * 3.5)))

    def _estimate_subjectivity(self, text: str) -> float:
        """Rough subjectivity estimate without TextBlob."""
        subjective_words = [
            "amazing", "terrible", "great", "awful", "best", "worst",
            "excellent", "horrible", "wonderful", "devastating", "brilliant"
        ]
        text_lower = text.lower()
        count = sum(1 for w in subjective_words if w in text_lower)
        words = len(text.split())
        return min(count / max(words / 50, 1), 1.0)

    def _empty_result(self) -> dict:
        return {
            "sentiment": "neutral",
            "score": 0.0,
            "intensity": "mild",
            "emotions": {},
            "subjectivity": 0.5,
            "financial_signals": [],
        }
