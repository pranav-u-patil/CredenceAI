"""
Source Behavior Analyzer
Tracks and profiles news source behavior patterns:
- Credibility scoring
- Political lean detection
- Sensationalism index
- Historical accuracy signals
- Update frequency patterns
No external API needed — all local analysis.
"""

import hashlib
import logging
import re
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ── Known Source Database ────────────────────────────────────────────────────
# Curated credibility profiles. Scores: 0-100 (higher = more credible)
# Lean: -2 (far left) to +2 (far right), 0 = center
# These are approximate and based on media literacy research.

KNOWN_SOURCES: dict[str, dict] = {
    # International Wire Services
    "reuters.com": {"credibility": 92, "lean": 0, "type": "wire", "fact_check": "high"},
    "apnews.com": {"credibility": 91, "lean": 0, "type": "wire", "fact_check": "high"},
    "bloomberg.com": {"credibility": 88, "lean": 0, "type": "financial", "fact_check": "high"},

    # Major US Publications
    "wsj.com": {"credibility": 85, "lean": 1, "type": "newspaper", "fact_check": "high"},
    "nytimes.com": {"credibility": 84, "lean": -1, "type": "newspaper", "fact_check": "high"},
    "washingtonpost.com": {"credibility": 82, "lean": -1, "type": "newspaper", "fact_check": "high"},
    "ft.com": {"credibility": 87, "lean": 0, "type": "newspaper", "fact_check": "high"},
    "economist.com": {"credibility": 88, "lean": 0, "type": "magazine", "fact_check": "high"},

    # Financial Specific
    "cnbc.com": {"credibility": 75, "lean": 0, "type": "financial_tv", "fact_check": "medium"},
    "marketwatch.com": {"credibility": 74, "lean": 0, "type": "financial", "fact_check": "medium"},
    "seekingalpha.com": {"credibility": 60, "lean": 0, "type": "investment", "fact_check": "low"},

    # Broadcast
    "bbc.com": {"credibility": 86, "lean": -1, "type": "broadcast", "fact_check": "high"},
    "bbc.co.uk": {"credibility": 86, "lean": -1, "type": "broadcast", "fact_check": "high"},
    "npr.org": {"credibility": 82, "lean": -1, "type": "broadcast", "fact_check": "high"},
    "cnn.com": {"credibility": 70, "lean": -1, "type": "tv_news", "fact_check": "medium"},
    "foxnews.com": {"credibility": 55, "lean": 2, "type": "tv_news", "fact_check": "medium"},

    # Tech
    "techcrunch.com": {"credibility": 72, "lean": -1, "type": "tech", "fact_check": "medium"},
    "theverge.com": {"credibility": 71, "lean": -1, "type": "tech", "fact_check": "medium"},
    "wired.com": {"credibility": 74, "lean": -1, "type": "tech", "fact_check": "medium"},

    # India
    "thehindu.com": {"credibility": 80, "lean": -1, "type": "newspaper", "fact_check": "high"},
    "livemint.com": {"credibility": 78, "lean": 0, "type": "financial", "fact_check": "medium"},
    "economictimes.com": {"credibility": 76, "lean": 0, "type": "financial", "fact_check": "medium"},
    "ndtv.com": {"credibility": 72, "lean": -1, "type": "tv_news", "fact_check": "medium"},
    "timesofindia.com": {"credibility": 70, "lean": 0, "type": "newspaper", "fact_check": "medium"},
    "hindustantimes.com": {"credibility": 69, "lean": 0, "type": "newspaper", "fact_check": "medium"},

    # Default for unknown
    "_default": {"credibility": 50, "lean": 0, "type": "unknown", "fact_check": "unknown"},
}

# Sensationalism markers in headlines
SENSATIONAL_PATTERNS = [
    r'\b(BREAKING|URGENT|EXCLUSIVE|SHOCK|BOMBSHELL|EXPLOSIVE)\b',
    r'you won\'t believe',
    r'shocking truth',
    r'must see',
    r'secret (revealed|exposed)',
    r'\?\?+',
    r'!{2,}',
    r'(100|completely|totally|absolutely) (fake|wrong|false)',
    r'(destroying|obliterating|crushing)',
]

# Clickbait patterns
CLICKBAIT_PATTERNS = [
    r'(here\'s why|this is why|that\'s why)',
    r'(what happens next|what you need to know)',
    r'(everything you need)',
    r'\d+ (things|ways|reasons|facts)',
    r'(nobody is talking about)',
]


class SourceBehaviorAnalyzer:
    """
    Profiles news sources dynamically:
    1. Known source database lookup
    2. URL pattern analysis for unknowns
    3. Headline sensationalism scoring
    4. Behavior pattern tracking
    """

    def __init__(self):
        self._runtime_profiles: dict[str, dict] = {}

    async def get_profile(self, domain: str) -> dict:
        """Get complete behavior profile for a domain."""
        domain = domain.lower().replace("www.", "")

        # Check runtime cache first
        if domain in self._runtime_profiles:
            return self._runtime_profiles[domain]

        # Look up known sources
        known = KNOWN_SOURCES.get(domain, KNOWN_SOURCES["_default"])

        # Build full profile
        profile = {
            "domain": domain,
            "credibility_score": known["credibility"],
            "political_lean": known["lean"],
            "lean_label": self._lean_label(known["lean"]),
            "source_type": known["type"],
            "fact_check_rating": known["fact_check"],
            "credibility_label": self._credibility_label(known["credibility"]),
            "is_known_source": domain in KNOWN_SOURCES,
            "warnings": self._generate_warnings(domain, known),
            "analysis_method": "database" if domain in KNOWN_SOURCES else "heuristic",
        }

        # Heuristic analysis for unknown sources
        if not profile["is_known_source"]:
            heuristics = self._heuristic_analysis(domain)
            profile.update(heuristics)

        self._runtime_profiles[domain] = profile
        return profile

    def analyze_headline(self, headline: str, domain: str = "") -> dict:
        """Analyze a single headline for sensationalism, bias, etc."""
        result = {
            "sensationalism_score": 0.0,
            "clickbait_score": 0.0,
            "contains_caps_abuse": False,
            "signals": [],
        }

        if not headline:
            return result

        # Check sensationalism
        sens_score = 0
        for pattern in SENSATIONAL_PATTERNS:
            if re.search(pattern, headline, re.IGNORECASE):
                sens_score += 20
                match = re.search(pattern, headline, re.IGNORECASE)
                if match:
                    result["signals"].append(f"Sensational: '{match.group()}'")

        # Check clickbait
        click_score = 0
        for pattern in CLICKBAIT_PATTERNS:
            if re.search(pattern, headline, re.IGNORECASE):
                click_score += 15
                result["signals"].append(f"Clickbait pattern detected")

        # ALL CAPS abuse (more than 3 all-caps words)
        caps_words = [w for w in headline.split() if len(w) > 3 and w.isupper()]
        if len(caps_words) >= 3:
            result["contains_caps_abuse"] = True
            result["signals"].append(f"Excessive caps: {', '.join(caps_words[:3])}")
            sens_score += 15

        result["sensationalism_score"] = min(100, sens_score)
        result["clickbait_score"] = min(100, click_score)
        result["headline_quality"] = self._headline_quality(sens_score + click_score)

        return result

    def score_source_mix(self, source_profiles: dict) -> dict:
        """Score the overall quality of a mix of sources."""
        if not source_profiles:
            return {"mix_quality": "unknown", "diversity_score": 0, "avg_credibility": 50}

        profiles = list(source_profiles.values())
        credibilities = [p.get("credibility_score", 50) for p in profiles]
        leans = [p.get("political_lean", 0) for p in profiles]

        avg_cred = sum(credibilities) / len(credibilities)
        lean_variance = self._variance(leans)

        # Higher lean variance = better political diversity
        diversity = min(100, lean_variance * 25)

        # Source type diversity
        types = {p.get("source_type", "unknown") for p in profiles}
        type_diversity = len(types) * 10

        return {
            "mix_quality": "good" if avg_cred > 70 else "moderate" if avg_cred > 50 else "poor",
            "avg_credibility": round(avg_cred, 1),
            "political_diversity": round(diversity, 1),
            "source_type_diversity": len(types),
            "source_types": list(types),
            "high_credibility_count": sum(1 for c in credibilities if c >= 75),
            "low_credibility_count": sum(1 for c in credibilities if c < 50),
        }

    # ── Private Helpers ───────────────────────────────────────────

    def _heuristic_analysis(self, domain: str) -> dict:
        """Estimate credibility for unknown domains using URL patterns."""
        credibility = 50  # Start neutral
        signals = []

        # TLD signals
        if domain.endswith(".gov"):
            credibility += 20
            signals.append("Government domain")
        elif domain.endswith(".edu"):
            credibility += 15
            signals.append("Educational institution")
        elif domain.endswith(".ac.uk") or domain.endswith(".edu.au"):
            credibility += 12
            signals.append("Academic domain")

        # Suspicious patterns
        if any(x in domain for x in ["truth", "real", "expose", "uncensored", "freedom"]):
            credibility -= 20
            signals.append("Potentially partisan domain name")

        if re.search(r'\d{4,}', domain):
            credibility -= 10
            signals.append("Unusual numeric patterns in domain")

        if domain.count("-") >= 3:
            credibility -= 5
            signals.append("Complex hyphenated domain")

        return {
            "credibility_score": max(10, min(90, credibility)),
            "heuristic_signals": signals,
            "credibility_label": self._credibility_label(max(10, min(90, credibility))),
        }

    def _lean_label(self, lean: float) -> str:
        if lean <= -2: return "Far Left"
        if lean < -0.5: return "Left-Leaning"
        if lean <= 0.5: return "Center"
        if lean < 1.5: return "Right-Leaning"
        return "Far Right"

    def _credibility_label(self, score: float) -> str:
        if score >= 85: return "Highly Credible"
        if score >= 70: return "Generally Credible"
        if score >= 55: return "Mixed Credibility"
        if score >= 40: return "Low Credibility"
        return "Very Low Credibility"

    def _headline_quality(self, combined_score: float) -> str:
        if combined_score >= 60: return "poor"
        if combined_score >= 30: return "moderate"
        return "good"

    def _generate_warnings(self, domain: str, profile: dict) -> list[str]:
        warnings = []
        if profile["credibility"] < 50:
            warnings.append("Low credibility source — verify with primary sources")
        if profile["lean"] >= 2:
            warnings.append("Strong right-wing lean — may lack balance")
        if profile["lean"] <= -2:
            warnings.append("Strong left-wing lean — may lack balance")
        if profile["fact_check"] == "low":
            warnings.append("Poor fact-checking record")
        return warnings

    def _variance(self, values: list) -> float:
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        return sum((v - mean) ** 2 for v in values) / len(values)
