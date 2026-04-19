"""
Fact Checker Agent
Uses Google Fact Check API (free, 10k req/day) to verify claims in articles.
Gracefully degrades when API key not provided.
"""

import asyncio
import logging
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)


class FactCheckerAgent:
    """
    Integrates Google Fact Check Tools API.
    Free tier: ~10,000 requests/day with API key.
    Falls back to pattern-based plausibility checks without key.
    """

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.enabled = bool(api_key)
        self.base_url = "https://factchecktools.googleapis.com/v1alpha1/claims:search"

    async def check_claims(self, claims: list[str]) -> list[dict]:
        """Check multiple claims. Returns list of fact-check results."""
        results = []

        for claim in claims[:5]:  # Cap at 5 to conserve quota
            if not claim or len(claim) < 10:
                continue
            try:
                if self.enabled:
                    result = await self._api_check(claim)
                else:
                    result = self._pattern_check(claim)
                results.append(result)
                await asyncio.sleep(0.2)  # Gentle rate limiting
            except Exception as e:
                logger.warning(f"Fact check failed for '{claim[:50]}': {e}")
                results.append({
                    "claim": claim[:100],
                    "verified": None,
                    "rating": "unchecked",
                    "error": str(e),
                })

        return results

    async def _api_check(self, claim: str) -> dict:
        """Use Google Fact Check API."""
        params = {
            "query": claim[:200],
            "key": self.api_key,
            "languageCode": "en",
            "pageSize": 3,
        }
        url = f"{self.base_url}?{urlencode(params)}"

        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

        fact_claims = data.get("claims", [])

        if not fact_claims:
            return {
                "claim": claim[:100],
                "verified": None,
                "rating": "no_data",
                "source": None,
                "matches": 0,
            }

        # Take highest-confidence match
        best = fact_claims[0]
        reviews = best.get("claimReview", [])
        rating = reviews[0].get("textualRating", "unrated") if reviews else "unrated"
        publisher = reviews[0].get("publisher", {}).get("name", "") if reviews else ""

        # Normalize rating to boolean where possible
        verified = self._normalize_rating(rating)

        return {
            "claim": claim[:100],
            "matched_claim": best.get("text", "")[:150],
            "rating": rating,
            "verified": verified,
            "fact_checker": publisher,
            "matches": len(fact_claims),
            "source": "google_fact_check_api",
        }

    def _pattern_check(self, claim: str) -> dict:
        """
        Heuristic plausibility check without API.
        Checks for common misinformation patterns.
        """
        claim_lower = claim.lower()

        red_flags = []
        plausibility = 70  # Default to somewhat credible

        # Absolute/extreme language often signals misinformation
        absolutes = ["always", "never", "100%", "proven fact", "doctors hate", "secret cure"]
        for word in absolutes:
            if word in claim_lower:
                plausibility -= 15
                red_flags.append(f"Absolute language: '{word}'")

        # Conspiracy signals
        conspiracy_terms = ["they don't want you to know", "mainstream media won't", "suppressed", "cover-up"]
        for term in conspiracy_terms:
            if term in claim_lower:
                plausibility -= 25
                red_flags.append("Conspiracy framing detected")
                break

        # Sensationalist capitalization
        import re
        caps_words = re.findall(r'\b[A-Z]{4,}\b', claim)
        if len(caps_words) > 2:
            plausibility -= 10
            red_flags.append("Excessive capitalization")

        # Numeric claims without context are lower trust
        has_specific_number = bool(re.search(r'\b\d+%|\d+ million|\d+ billion', claim))
        if has_specific_number and len(claim) < 50:
            plausibility -= 5

        plausibility = max(10, min(90, plausibility))

        return {
            "claim": claim[:100],
            "verified": None,
            "rating": "heuristic_analysis",
            "plausibility_score": plausibility,
            "plausibility_label": "likely credible" if plausibility >= 60 else "questionable" if plausibility >= 40 else "suspicious",
            "red_flags": red_flags,
            "source": "heuristic",
            "note": "Provide FACT_CHECK_API key for authoritative fact-checking",
        }

    def _normalize_rating(self, rating: str) -> bool | None:
        """Convert textual rating to boolean."""
        rating_lower = rating.lower()
        true_signals = ["true", "correct", "accurate", "verified", "confirmed"]
        false_signals = ["false", "incorrect", "misleading", "inaccurate", "fake", "pants on fire", "wrong"]

        if any(s in rating_lower for s in true_signals):
            return True
        if any(s in rating_lower for s in false_signals):
            return False
        return None
