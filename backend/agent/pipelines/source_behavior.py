"""
verification_agent/pipelines/source_behavior.py
=================================================
Pipeline 4 — Source behavior analysis using historical DB.

Uses a spaced-repetition beacon system to decide which domains need
fresh reliability checks vs. can use cached scores.

PLACEHOLDERS
------------
  EVIDENCE_DB_DSN — database connection string
  domain ownership/syndication data — currently a static heuristic;
    replace with a WHOIS / media-ownership API  # ← PLACEHOLDER
"""

from __future__ import annotations
import uuid
from urllib.parse import urlparse

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
    from CredenceAI.backend.utils.db import get_source_history
except ImportError:
    try:
        from ...utils.db import get_source_history
    except ImportError:
        from utils.db import get_source_history

try:
    from CredenceAI.backend.utils.log import get_logger
except ImportError:
    try:
        from ...utils.log import get_logger
    except ImportError:
        from utils.log import get_logger

logger = get_logger(__name__)

# Known syndication / ownership clusters  # ← PLACEHOLDER: expand or replace with API
_OWNERSHIP_CLUSTERS: dict[str, str] = {
    "reuters.com":       "thomson_reuters",
    "apnews.com":        "associated_press",
    "foxnews.com":       "news_corp",
    "wsj.com":           "news_corp",
    "nytimes.com":       "nyt_group",
    "theatlantic.com":   "atlantic_media",
    "businessinsider.com": "axel_springer",
    "politico.com":      "axel_springer",
}

# Spaced-repetition TTLs (seconds) — how long a domain reliability score is cached
_SPACED_REPETITION_TTL: dict[str, int] = {
    "high_reliability":   7 * 24 * 3600,   # 7 days
    "medium_reliability": 2 * 24 * 3600,   # 2 days
    "low_reliability":    6 * 3600,        # 6 hours
    "unknown":            24 * 3600,       # 1 day default
}


async def run_source_behavior(claim: ClaimInput, settings: AgentSettings) -> dict:
    """
    Returns:
        {
          "evidence_units":          [...],   # adjustments framed as evidence
          "searches_performed":      int,
          "independence_weights":    {domain: weight},
          "source_behavior_metrics": {domain: {...}},
          "recommended_ttls":        {domain: seconds},
        }
    """
    # Collect all domains from initial_urls
    domains = list({urlparse(str(u.url)).netloc for u in claim.initial_urls})
    if not domains:
        return _empty_result()

    # Fetch historical records from DB
    history = get_source_history(domains, settings.db_dsn)

    independence_weights: dict[str, float]  = {}
    source_metrics:       dict[str, dict]   = {}
    recommended_ttls:     dict[str, int]    = {}
    evidence_units:       list[dict]        = []

    for domain in domains:
        records = history.get(domain, [])
        metrics  = _compute_domain_metrics(domain, records)
        weight   = _compute_independence_weight(domain, metrics, domains)
        ttl      = _beacon_ttl(metrics)

        independence_weights[domain] = weight
        source_metrics[domain]       = metrics
        recommended_ttls[domain]     = ttl

        # Emit a lightweight evidence unit encoding source reliability
        if metrics["verdict_count"] >= 3:
            unit_type = "support" if metrics["accuracy_rate"] >= 0.7 else "contradict"
            evidence_units.append({
                "id":                  str(uuid.uuid4()),
                "type":                unit_type,
                "domain":              domain,
                "url":                 f"https://{domain}",
                "timestamp":           None,
                "similarity":          metrics["accuracy_rate"],
                "lr":                  _reliability_to_lr(metrics["accuracy_rate"]),
                "independence_weight": weight,
                "cluster_id":          f"source_behavior_{domain}",
                "provenance":          "source_behavior",
                "raw_snippet":         (
                    f"Domain {domain}: {metrics['verdict_count']} historical verdicts, "
                    f"accuracy={metrics['accuracy_rate']:.2f}, "
                    f"ownership={metrics.get('ownership_cluster','unknown')}"
                ),
            })

    return {
        "evidence_units":          evidence_units,
        "searches_performed":      0,   # DB lookup only
        "independence_weights":    independence_weights,
        "source_behavior_metrics": source_metrics,
        "recommended_ttls":        recommended_ttls,
    }


# ── Domain metrics computation ────────────────────────────────────────────────

def _compute_domain_metrics(domain: str, records: list[dict]) -> dict:
    ownership = _OWNERSHIP_CLUSTERS.get(domain, "unknown")

    if not records:
        return {
            "domain":           domain,
            "verdict_count":    0,
            "accuracy_rate":    0.5,   # uninformative prior
            "false_positive_rate": 0.0,
            "ownership_cluster": ownership,
            "reliability_tier": "unknown",
        }

    correct = sum(1 for r in records if r.get("was_correct") == 1)
    known   = sum(1 for r in records if r.get("was_correct") is not None)
    accuracy = correct / known if known > 0 else 0.5

    tier: str
    if accuracy >= 0.80:
        tier = "high_reliability"
    elif accuracy >= 0.55:
        tier = "medium_reliability"
    else:
        tier = "low_reliability"

    # False-positive rate: cases marked correct but later contradicted
    fp = sum(1 for r in records if r.get("was_correct") == 0 and
             float(r.get("credibility_score") or 0) > 70)
    fp_rate = fp / max(len(records), 1)

    return {
        "domain":             domain,
        "verdict_count":      len(records),
        "accuracy_rate":      round(accuracy, 4),
        "false_positive_rate": round(fp_rate, 4),
        "ownership_cluster":  ownership,
        "reliability_tier":   tier,
        "recent_scores":      [r.get("credibility_score") for r in records[:5]],
    }


def _compute_independence_weight(domain: str, metrics: dict, all_domains: list[str]) -> float:
    """
    Reduce independence weight if:
      1. Multiple domains in this claim share the same ownership cluster.
      2. Source has low historical reliability.
    """
    ownership = metrics.get("ownership_cluster", "unknown")
    if ownership != "unknown":
        siblings = sum(
            1 for d in all_domains
            if _OWNERSHIP_CLUSTERS.get(d) == ownership and d != domain
        )
        ownership_penalty = min(siblings * 0.2, 0.7)
    else:
        ownership_penalty = 0.0

    accuracy      = metrics.get("accuracy_rate", 0.5)
    reliability_w = max(0.2, accuracy)

    weight = (1.0 - ownership_penalty) * reliability_w
    return round(max(0.1, min(1.0, weight)), 3)


# ── Spaced-repetition beacon ──────────────────────────────────────────────────

def _beacon_ttl(metrics: dict) -> int:
    """
    Higher-reliability domains need re-probing less frequently → longer TTL.
    """
    tier = metrics.get("reliability_tier", "unknown")
    return _SPACED_REPETITION_TTL.get(tier, _SPACED_REPETITION_TTL["unknown"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _reliability_to_lr(accuracy: float) -> float:
    """Convert historical accuracy to likelihood ratio."""
    if accuracy >= 0.80:
        return 1.6
    elif accuracy >= 0.60:
        return 1.1
    elif accuracy < 0.40:
        return 0.6
    return 0.9


def _empty_result() -> dict:
    return {
        "evidence_units":          [],
        "searches_performed":      0,
        "independence_weights":    {},
        "source_behavior_metrics": {},
        "recommended_ttls":        {},
    }
