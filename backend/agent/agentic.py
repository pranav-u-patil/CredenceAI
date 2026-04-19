from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class QueryBundle:
    primary: list[str] = field(default_factory=list)
    fallback: list[str] = field(default_factory=list)
    retry: list[str] = field(default_factory=list)


@dataclass
class AgentPlan:
    claim_id: str
    claim_text: str
    entities: list[str]
    intent: str
    risk_flags: list[str] = field(default_factory=list)
    source_priority: list[str] = field(default_factory=list)
    search: QueryBundle = field(default_factory=QueryBundle)
    fact_check_queries: list[str] = field(default_factory=list)
    news_queries: list[str] = field(default_factory=list)
    reasoning_notes: list[str] = field(default_factory=list)

    def to_meta(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReviewDecision:
    status: str
    should_retry: bool
    focus: str
    missing_signals: list[str] = field(default_factory=list)
    next_queries: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_meta(self) -> dict[str, Any]:
        return asdict(self)


def build_initial_plan(claim: Any, settings: Any) -> AgentPlan:
    claim_text = (getattr(claim, "claim_text", "") or "").strip()
    entities = list(getattr(claim, "entities", []) or [])
    text_lower = claim_text.lower()

    risk_flags: list[str] = []
    if any(word in text_lower for word in ("acquisition", "merger", "earnings", "stock", "sec", "price", "valuation")):
        risk_flags.append("financial")
    if any(word in text_lower for word in ("election", "minister", "president", "government", "policy")):
        risk_flags.append("political")
    if any(word in text_lower for word in ("breaking", "live", "urgent", "explosion", "earthquake", "war")):
        risk_flags.append("breaking_news")

    intent = "high_risk_verification" if risk_flags else "general_verification"
    source_priority = ["multi_search", "model_validation", "social_sentiment", "source_behavior"]
    if "financial" in risk_flags:
        source_priority = ["model_validation", "multi_search", "source_behavior", "social_sentiment"]

    return AgentPlan(
        claim_id=getattr(claim, "claim_id", ""),
        claim_text=claim_text,
        entities=entities,
        intent=intent,
        risk_flags=risk_flags,
        source_priority=source_priority,
        search=QueryBundle(
            primary=_build_base_queries(claim_text, entities)[: settings.max_searches],
            fallback=_build_base_queries(claim_text, entities)[1: settings.max_searches],
            retry=_build_retry_queries(claim_text, entities)[: settings.max_searches],
        ),
        fact_check_queries=_build_factcheck_queries(claim_text, entities),
        news_queries=_build_news_queries(claim_text, entities),
        reasoning_notes=[
            "Preserve Bayesian aggregation and classifier semantics.",
            "Prefer deterministic evidence collection before generative synthesis.",
            "Use retries to cover missing evidence dimensions, not to maximize raw volume.",
        ],
    )


def review_pipeline_results(
    *,
    plan: AgentPlan,
    pipeline_results: dict[str, Any],
    independent_clusters: int,
    ci_width_estimate: float,
    retries: int,
    settings: Any,
) -> ReviewDecision:
    missing_signals: list[str] = []
    notes: list[str] = []

    multi = pipeline_results.get("multi_search") or {}
    model = pipeline_results.get("model_validation") or {}
    social = pipeline_results.get("social_sentiment") or {}
    source = pipeline_results.get("source_behavior") or {}

    if not multi.get("evidence_units"):
        missing_signals.append("web_confirmation")
    if not model.get("fact_check_hits"):
        missing_signals.append("fact_check")
    if not social.get("evidence_units"):
        missing_signals.append("social_context")
    if not source.get("source_behavior_metrics"):
        missing_signals.append("source_history")

    if independent_clusters < getattr(settings, "min_independent_clusters", 3):
        notes.append(f"Only {independent_clusters} independent clusters collected.")
    if ci_width_estimate > 0.4:
        notes.append(f"Confidence interval estimate remains wide ({ci_width_estimate:.2f}).")

    should_retry = (
        retries < settings.max_retries
        and (independent_clusters < getattr(settings, "min_independent_clusters", 3) or ci_width_estimate > 0.4)
    )

    focus = "broaden_web_search"
    if "fact_check" in missing_signals:
        focus = "seek_fact_checks"
    elif "social_context" in missing_signals and "breaking_news" in plan.risk_flags:
        focus = "capture_social_propagation"

    next_queries = list(plan.search.retry)
    if focus == "seek_fact_checks":
        next_queries = list(dict.fromkeys(plan.fact_check_queries + plan.search.retry))
    elif focus == "capture_social_propagation":
        next_queries = list(dict.fromkeys(plan.search.retry + [f"{plan.claim_text[:64]} reaction", f"{plan.claim_text[:64]} eyewitness"]))

    return ReviewDecision(
        status="retry_recommended" if should_retry else "sufficient_for_aggregation",
        should_retry=should_retry,
        focus=focus,
        missing_signals=missing_signals,
        next_queries=next_queries[: settings.max_searches],
        notes=notes,
    )


def build_retry_plan(plan: AgentPlan, review: ReviewDecision) -> AgentPlan:
    return AgentPlan(
        claim_id=plan.claim_id,
        claim_text=plan.claim_text,
        entities=list(plan.entities),
        intent=plan.intent,
        risk_flags=list(plan.risk_flags),
        source_priority=list(plan.source_priority),
        search=QueryBundle(
            primary=list(plan.search.primary),
            fallback=list(plan.search.fallback),
            retry=list(dict.fromkeys(review.next_queries or plan.search.retry)),
        ),
        fact_check_queries=list(plan.fact_check_queries),
        news_queries=list(plan.news_queries),
        reasoning_notes=list(plan.reasoning_notes) + [f"Retry focus: {review.focus}"],
    )


def _build_base_queries(claim_text: str, entities: list[str]) -> list[str]:
    clean = claim_text.strip()
    entity_phrase = " ".join(entities[:4]).strip()
    without_fillers = " ".join(
        token for token in clean.split()
        if token.lower() not in {"the", "a", "an", "is", "are", "was", "were", "to", "of", "and"}
    )
    queries = [
        clean,
        entity_phrase,
        without_fillers,
        f"{clean[:80]} fact check",
        f"{clean[:80]} confirmed",
        f"{clean[:80]} official statement",
    ]
    return [query for query in dict.fromkeys(q.strip() for q in queries) if query]


def _build_retry_queries(claim_text: str, entities: list[str]) -> list[str]:
    entity_phrase = " ".join(entities[:3]).strip()
    queries = [
        f"{claim_text[:90]} latest update",
        f"{claim_text[:90]} denied OR confirmed",
        f"{claim_text[:90]} rebuttal",
        f"{entity_phrase} statement" if entity_phrase else "",
        f"{entity_phrase} sec filing" if entity_phrase else "",
    ]
    return [query for query in dict.fromkeys(q.strip() for q in queries) if query]


def _build_factcheck_queries(claim_text: str, entities: list[str]) -> list[str]:
    queries = [claim_text[:180], f"{claim_text[:120]} rumor"]
    if entities:
        queries.append(" ".join(entities[:3]) + " fact check")
    return [q for q in dict.fromkeys(query.strip() for query in queries) if q]


def _build_news_queries(claim_text: str, entities: list[str]) -> list[str]:
    queries = [claim_text[:120], f"{claim_text[:100]} latest"]
    if entities:
        queries.insert(0, " OR ".join(entities[:3]))
    return [q for q in dict.fromkeys(query.strip() for query in queries) if q]
