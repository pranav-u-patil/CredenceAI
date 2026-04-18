"""
verification_agent/agent.py
============================
Main orchestrator. Receives a claim JSON, fans out to four parallel
pipelines, aggregates evidence via log-odds Bayesian fusion, and returns
a single explainable verdict JSON.

Usage:
    python agent.py --claim claim_sample.json
    # or import and call run_agent(claim_dict) programmatically
"""

import asyncio
import json
import time
import argparse
from importlib import import_module
from typing import Any, Callable

try:
    from .config.settings import AgentSettings
    from .scoring.aggregator import aggregate_evidence
    from .scoring.classifier import classify_score
except ImportError:
    from config.settings import AgentSettings
    from scoring.aggregator import aggregate_evidence
    from scoring.classifier import classify_score

try:
    from CredenceAI.backend.app.models.schema import ScraperInput as ClaimInput
except ImportError:
    try:
        from ..app.models.schema import ScraperInput as ClaimInput
    except ImportError:
        from app.models.schema import ScraperInput as ClaimInput

try:
    from CredenceAI.backend.utils.log import get_logger
except ImportError:
    try:
        from ..utils.log import get_logger
    except ImportError:
        from utils.log import get_logger

logger = get_logger(__name__)


def _load_symbol(module_names: tuple[str, ...], symbol_name: str) -> Callable[..., Any]:
    last_error: Exception | None = None
    for module_name in module_names:
        try:
            module = import_module(module_name)
            return getattr(module, symbol_name)
        except Exception as exc:
            last_error = exc
    raise ImportError(f"Unable to import {symbol_name} from {module_names}") from last_error


async def run_multi_search(*args: Any, **kwargs: Any) -> dict[str, Any]:
    impl = _load_symbol(
        (
            "CredenceAI.backend.agent.pipelines.multi_search",
            "pipelines.multi_search",
        ),
        "run_multi_search",
    )
    return await impl(*args, **kwargs)


async def run_social_sentiment(*args: Any, **kwargs: Any) -> dict[str, Any]:
    impl = _load_symbol(
        (
            "CredenceAI.backend.agent.pipelines.social_sentiment",
            "pipelines.social_sentiment",
        ),
        "run_social_sentiment",
    )
    return await impl(*args, **kwargs)


async def run_model_validation(*args: Any, **kwargs: Any) -> dict[str, Any]:
    impl = _load_symbol(
        (
            "CredenceAI.backend.agent.pipelines.model_validation",
            "pipelines.model_validation",
        ),
        "run_model_validation",
    )
    return await impl(*args, **kwargs)


async def run_source_behavior(*args: Any, **kwargs: Any) -> dict[str, Any]:
    impl = _load_symbol(
        (
            "CredenceAI.backend.agent.pipelines.source_behavior",
            "pipelines.source_behavior",
        ),
        "run_source_behavior",
    )
    return await impl(*args, **kwargs)


def build_output(
    *,
    claim_id: str,
    p_true: float,
    credibility_score: int,
    bucket: str,
    ci: list[float],
    explanation: str,
    evidence_units: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    risk_proxy: float | None,
    meta: dict[str, Any],
) -> dict[str, Any]:
    output = {
        "claim_id": claim_id,
        "p_true": p_true,
        "credibility_score": credibility_score,
        "bucket": bucket,
        "confidence_interval": ci,
        "explanation": explanation,
        "evidence_units": evidence_units,
        "actions": actions,
        "risk_proxy": risk_proxy,
        "meta": meta,
        "zero_trust_mode": True,
    }
    return output


from typing import Any

from backend.agent.pipelines.multi_search     import run_multi_search
from backend.agent.pipelines.social_sentiment import run_social_sentiment
from backend.agent.pipelines.model_validation  import run_model_validation
from backend.agent.pipelines.source_behavior   import run_source_behavior
from backend.agent.scoring.aggregator          import aggregate_evidence
from backend.agent.scoring.classifier          import classify_score
from backend.agent.config.settings             import AgentSettings
from backend.agent.utils.logger                import get_logger
from backend.agent.utils.schema                import ClaimInput, AgentOutput, build_output

logger = get_logger(__name__)

async def run_agent(claim: dict[str, Any], settings: AgentSettings | None = None) -> dict[str, Any]:
    """
    Orchestrate all four pipelines in parallel, aggregate, classify, return verdict.

    Parameters
    ----------
    claim    : parsed claim JSON matching ClaimInput schema
    settings : optional override of AgentSettings

    Returns
    -------
    dict matching AgentOutput schema
    """
    if settings is None:
        settings = AgentSettings()

    t0 = time.monotonic()
    plan_trace: list[dict] = []

    # ── Validate input ──────────────────────────────────────────────────────
    try:
        claim_input = ClaimInput(**claim)
    except Exception as exc:
        raise ValueError(f"Invalid claim input: {exc}") from exc

    plan_trace.append({"step": "input_validated", "claim_id": claim_input.claim_id})
    logger.info("Starting verification for claim_id=%s", claim_input.claim_id)

    # ── Fan out four pipelines concurrently ─────────────────────────────────
    plan_trace.append({"step": "pipelines_start", "pipelines": [
        "multi_search", "social_sentiment", "model_validation", "source_behavior"
    ]})

    (
        multi_search_result,
        social_result,
        model_result,
        source_result,
    ) = await asyncio.gather(
        run_multi_search(claim_input, settings),
        run_social_sentiment(claim_input, settings),
        run_model_validation(claim_input, settings),
        run_source_behavior(claim_input, settings),
        return_exceptions=True,
    )

    # Gracefully handle pipeline failures (don't crash the whole agent)
    pipeline_results = {}
    for name, result in zip(
        ["multi_search", "social_sentiment", "model_validation", "source_behavior"],
        [multi_search_result, social_result, model_result, source_result],
    ):
        if isinstance(result, Exception):
            logger.warning("Pipeline %s failed: %s", name, result)
            plan_trace.append({"step": f"pipeline_error", "pipeline": name, "error": str(result)})
            pipeline_results[name] = None
        else:
            pipeline_results[name] = result
            plan_trace.append({"step": f"pipeline_complete", "pipeline": name,
                                "evidence_units": len(result.get("evidence_units", []))})

    # ── Adaptive re-search if evidence is thin ──────────────────────────────
    retries = 0
    all_units = _collect_all_units(pipeline_results)
    independent_clusters = _count_independent_clusters(all_units)
    ci_width_estimate = _rough_ci_width(all_units)

    while (
        retries < settings.max_retries
        and (independent_clusters < 2 or ci_width_estimate > 0.4)
        and (time.monotonic() - t0) * 1000 < settings.max_elapsed_ms * 0.8
    ):
        retries += 1
        plan_trace.append({"step": "re_search", "retry": retries,
                           "reason": f"clusters={independent_clusters}, ci_width≈{ci_width_estimate:.2f}"})
        logger.info("Re-search triggered (retry %d)", retries)

        try:
            expanded = await run_multi_search(claim_input, settings, retry=retries)
        except Exception as exc:
            logger.warning("Retry multi_search failed: %s", exc)
            plan_trace.append({"step": "pipeline_error", "pipeline": "multi_search_retry", "error": str(exc)})
            break

        if not isinstance(expanded, Exception) and expanded:
            pipeline_results["multi_search_retry"] = expanded
            all_units = _collect_all_units(pipeline_results)
            independent_clusters = _count_independent_clusters(all_units)
            ci_width_estimate = _rough_ci_width(all_units)

    # ── Aggregate evidence → P_true ─────────────────────────────────────────
    plan_trace.append({"step": "aggregation_start", "total_units": len(all_units)})
    aggregation = aggregate_evidence(all_units, prior=settings.prior_p_true)
    p_true     = aggregation["p_true"]
    ci         = aggregation["confidence_interval"]
    explanation= aggregation["explanation"]

    plan_trace.append({"step": "aggregation_complete", "p_true": p_true, "ci": ci})

    # ── Classify and build actions ───────────────────────────────────────────
    market_signals = _extract_market_signals(pipeline_results.get("model_validation"))

    credibility_score, bucket, actions = classify_score(
        p_true=p_true,
        ci=ci,
        entities=claim_input.entities,
        market_signals=market_signals,
        social_signals=pipeline_results.get("social_sentiment", {}) or {},
        independent_clusters=independent_clusters,
    )

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    plan_trace.append({"step": "done", "elapsed_ms": elapsed_ms})

    # ── Build and return output ──────────────────────────────────────────────
    output = build_output(
        claim_id=claim_input.claim_id,
        p_true=p_true,
        credibility_score=credibility_score,
        bucket=bucket,
        ci=ci,
        explanation=explanation,
        evidence_units=all_units,
        actions=actions,
        risk_proxy=market_signals.get("risk_proxy"),
        meta={
            "searches_performed": _count_searches(pipeline_results),
            "retries": retries,
            "elapsed_ms": elapsed_ms,
            "plan_trace": plan_trace,
            "zero_trust_mode": True,
        },
    )

    logger.info(
        "Verdict for claim_id=%s: P_true=%.3f, score=%d, bucket=%s",
        claim_input.claim_id, p_true, credibility_score, bucket,
    )
    return output


# ── Helpers ──────────────────────────────────────────────────────────────────

def _collect_all_units(pipeline_results: dict) -> list[dict]:
    units = []
    for result in pipeline_results.values():
        if result and isinstance(result, dict):
            units.extend(result.get("evidence_units", []))
    return units


def _count_independent_clusters(units: list[dict]) -> int:
    clusters = set()
    for u in units:
        cid = u.get("cluster_id")
        if cid:
            clusters.add(cid)
    return max(len(clusters), 1 if units else 0)


def _rough_ci_width(units: list[dict]) -> float:
    """Quick heuristic: fewer high-LR units → wider CI."""
    if not units:
        return 1.0
    high_lr = sum(1 for u in units if abs(_coerce_float(u.get("lr", 1.0), 1.0) - 1.0) > 0.5)
    if high_lr == 0:
        return 0.8
    return max(0.1, 0.9 - high_lr * 0.15)


def _count_searches(pipeline_results: dict) -> int:
    total = 0
    for result in pipeline_results.values():
        if result and isinstance(result, dict):
            total += result.get("searches_performed", 0)
    return total


def _extract_market_signals(model_validation_result: dict[str, Any] | None) -> dict[str, Any]:
    if not model_validation_result or not isinstance(model_validation_result, dict):
        return {}

    market_signals = model_validation_result.get("market_signals")
    merged: dict[str, Any] = dict(market_signals) if isinstance(market_signals, dict) else {}

    if "risk_proxy" in model_validation_result and "risk_proxy" not in merged:
        merged["risk_proxy"] = model_validation_result.get("risk_proxy")

    return merged


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default


# ── CLI entry point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the verification agent on a claim JSON file.")
    parser.add_argument("--claim", required=True, help="Path to claim JSON file")
    parser.add_argument("--output", default=None, help="Optional path to write output JSON")
    args = parser.parse_args()

    with open(args.claim) as f:
        claim_data = json.load(f)

    result = asyncio.run(run_agent(claim_data))

    output_str = json.dumps(result, indent=2, default=str)
    if args.output:
        with open(args.output, "w") as f:
            f.write(output_str)
        print(f"Output written to {args.output}")
    else:
        print(output_str)
