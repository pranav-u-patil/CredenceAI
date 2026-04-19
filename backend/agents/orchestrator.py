"""
Gemini Orchestrator — Agentic AI Brain
Uses Gemini 1.5 Flash (free-tier friendly) to:
 - Plan multi-step analysis strategies
 - Synthesize scraped content
 - Generate final intelligence reports
 - Self-correct with tool calls
Token budget: ~2048 tokens per call, batched intelligently.
"""

import asyncio
import json
import logging
import time
from typing import Any, AsyncGenerator, Optional

import google.generativeai as genai

from agents.scraper import NewsScraperAgent
from agents.sentiment import SentimentAnalyzer
from agents.risk_engine import RiskEngine
from agents.source_analyzer import SourceBehaviorAnalyzer
from agents.fact_checker import FactCheckerAgent
from config.settings import Settings

logger = logging.getLogger(__name__)
settings = Settings()


SYSTEM_PROMPT = """You are an elite news intelligence analyst AI. Your job is to:
1. Synthesize scraped news articles into actionable intelligence
2. Identify patterns, contradictions, and emerging narratives
3. Assess credibility and source bias
4. Generate concise, high-signal intelligence reports

CRITICAL CONSTRAINTS (free-tier mode):
- Be CONCISE. Max 300 words per section.
- Use bullet points over prose.
- Flag confidence levels: [HIGH/MED/LOW]
- Never hallucinate — only cite provided data.

Output valid JSON matching the report schema when asked."""


class GeminiOrchestrator:
    def __init__(
        self,
        gemini_api_key: str,
        finnhub_api_key: str = "",
        news_api_key: str = "",
        fact_check_api_key: str = "",
    ):
        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL,
            system_instruction=SYSTEM_PROMPT,
        )
        self.scraper = NewsScraperAgent(news_api_key=news_api_key)
        self.sentiment = SentimentAnalyzer()
        self.risk_engine = RiskEngine(finnhub_api_key=finnhub_api_key)
        self.source_analyzer = SourceBehaviorAnalyzer()
        self.fact_checker = FactCheckerAgent(api_key=fact_check_api_key)
        self._last_gemini_call = 0.0

    # ── Rate-limiter ─────────────────────────────────────────────

    async def _gemini_call(self, prompt: str, json_mode: bool = False) -> str:
        """Rate-limited Gemini call. Respects free-tier 15 RPM."""
        elapsed = time.time() - self._last_gemini_call
        if elapsed < settings.GEMINI_REQUESTS_COOLDOWN:
            await asyncio.sleep(settings.GEMINI_REQUESTS_COOLDOWN - elapsed)

        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    max_output_tokens=settings.GEMINI_MAX_TOKENS_PER_REQUEST,
                    temperature=0.3,
                )
            )
            self._last_gemini_call = time.time()
            return response.text
        except Exception as e:
            logger.error(f"Gemini call failed: {e}")
            raise

    # ── Full Pipeline ─────────────────────────────────────────────

    async def run_full_pipeline(
        self,
        queries: list[str],
        sources: Optional[list[str]] = None,
        depth: str = "standard",
    ) -> AsyncGenerator[dict, None]:
        """
        Agentic pipeline with SSE progress events.
        Stages: plan → scrape → source analysis → sentiment → risk → synthesize → report
        """

        yield {"type": "stage", "stage": "planning", "message": "Gemini planning analysis strategy..."}

        # ── Stage 1: Planning ────────────────────────────────────
        plan_prompt = f"""Plan a news intelligence analysis for these queries: {json.dumps(queries)}
Return JSON: {{"search_terms": [...], "key_angles": [...], "risk_keywords": [...]}}
Max 5 items per list. Be specific."""

        plan_text = await self._gemini_call(plan_prompt)
        plan = self._safe_json(plan_text, {
            "search_terms": queries,
            "key_angles": [],
            "risk_keywords": []
        })

        yield {"type": "stage", "stage": "planning", "plan": plan, "message": "Strategy ready"}

        # ── Stage 2: Scraping ────────────────────────────────────
        yield {"type": "stage", "stage": "scraping", "message": "Crawling news sources..."}

        all_articles = []
        for query in queries[:3]:  # cap at 3 queries to save API budget
            articles = await self.scraper.scrape(
                query=query,
                sources=sources,
                max_results=settings.NEWS_API_MAX_ARTICLES,
            )
            all_articles.extend(articles)
            yield {
                "type": "progress",
                "stage": "scraping",
                "query": query,
                "count": len(articles),
                "message": f"Found {len(articles)} articles for '{query}'"
            }
            await asyncio.sleep(0.5)

        # Deduplicate by URL
        seen_urls = set()
        unique_articles = []
        for a in all_articles:
            if a.get("url") not in seen_urls:
                seen_urls.add(a.get("url"))
                unique_articles.append(a)

        yield {
            "type": "stage",
            "stage": "scraping",
            "total_articles": len(unique_articles),
            "message": f"Collected {len(unique_articles)} unique articles"
        }

        if not unique_articles:
            yield {"type": "error", "message": "No articles found. Check your API keys."}
            return

        # ── Stage 3: Source Behavior Analysis ───────────────────
        yield {"type": "stage", "stage": "source_analysis", "message": "Analyzing source behavior patterns..."}

        source_profiles = {}
        domains = list({self._extract_domain(a.get("url", "")) for a in unique_articles})
        for domain in domains[:8]:
            if domain:
                profile = await self.source_analyzer.get_profile(domain)
                source_profiles[domain] = profile

        yield {
            "type": "stage",
            "stage": "source_analysis",
            "profiles": source_profiles,
            "message": f"Profiled {len(source_profiles)} sources"
        }

        # ── Stage 4: Sentiment Analysis ──────────────────────────
        yield {"type": "stage", "stage": "sentiment", "message": "Running sentiment analysis..."}

        sentiment_results = []
        for article in unique_articles:
            text = article.get("content", article.get("description", ""))[:1000]
            if text:
                score = self.sentiment.analyze(text)
                sentiment_results.append({
                    "url": article.get("url"),
                    "title": article.get("title"),
                    "source": article.get("source"),
                    **score
                })

        sentiment_summary = self.sentiment.aggregate(sentiment_results)

        yield {
            "type": "stage",
            "stage": "sentiment",
            "results": sentiment_results[:10],
            "summary": sentiment_summary,
            "message": "Sentiment analysis complete"
        }

        # ── Stage 5: Risk Engine ─────────────────────────────────
        yield {"type": "stage", "stage": "risk", "message": "Risk engine processing..."}

        risk_report = await self.risk_engine.assess(
            articles=unique_articles,
            queries=queries,
            risk_keywords=plan.get("risk_keywords", []),
            sentiment_summary=sentiment_summary,
            source_profiles=source_profiles,
        )

        yield {
            "type": "stage",
            "stage": "risk",
            "report": risk_report,
            "message": f"Risk level: {risk_report.get('overall_risk', 'unknown').upper()}"
        }

        # ── Stage 6: Fact Checking (if key provided) ─────────────
        fact_results = []
        if self.fact_checker.enabled:
            yield {"type": "stage", "stage": "fact_check", "message": "Cross-referencing claims..."}
            claims = [a.get("title", "") for a in unique_articles[:5]]
            fact_results = await self.fact_checker.check_claims(claims)
            yield {
                "type": "stage",
                "stage": "fact_check",
                "results": fact_results,
                "message": f"Fact-checked {len(fact_results)} claims"
            }

        # ── Stage 7: Gemini Synthesis ─────────────────────────────
        yield {"type": "stage", "stage": "synthesis", "message": "Gemini synthesizing intelligence report..."}

        # Build compact context (token-budget aware)
        context = self._build_context(
            queries=queries,
            articles=unique_articles,
            sentiment_summary=sentiment_summary,
            risk_report=risk_report,
            source_profiles=source_profiles,
            fact_results=fact_results,
        )

        synthesis_prompt = f"""Analyze this news intelligence data and produce a structured report.

DATA:
{context}

Respond with valid JSON matching this schema:
{{
  "executive_summary": "2-3 sentence summary",
  "key_findings": ["finding1", "finding2", ...],
  "narrative_patterns": ["pattern1", ...],
  "contradictions": ["contradiction1", ...],
  "credibility_assessment": "brief assessment",
  "recommended_actions": ["action1", ...],
  "confidence": "HIGH|MED|LOW",
  "analyst_note": "one insight a human might miss"
}}"""

        synthesis_text = await self._gemini_call(synthesis_prompt)
        synthesis = self._safe_json(synthesis_text, {
            "executive_summary": synthesis_text[:500],
            "key_findings": [],
            "confidence": "MED"
        })

        yield {
            "type": "stage",
            "stage": "synthesis",
            "synthesis": synthesis,
            "message": "Intelligence synthesis complete"
        }

        # ── Final Report ──────────────────────────────────────────
        final_report = {
            "type": "final_report",
            "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
            "queries": queries,
            "plan": plan,
            "articles_analyzed": len(unique_articles),
            "articles": unique_articles[:20],  # send top 20 to UI
            "source_profiles": source_profiles,
            "sentiment": {
                "results": sentiment_results,
                "summary": sentiment_summary
            },
            "risk": risk_report,
            "fact_check": fact_results,
            "synthesis": synthesis,
        }

        yield final_report

    # ── Quick Analysis (token-lite) ───────────────────────────────

    async def quick_analyze(self, query: str) -> dict:
        """Single-query, minimal-token analysis for free-tier conservation."""
        articles = await self.scraper.scrape(query=query, max_results=3)

        if not articles:
            return {"error": "No articles found"}

        titles = [a.get("title", "") for a in articles]
        texts = [a.get("description", "")[:300] for a in articles]

        prompt = f"""Quick analysis for: "{query}"
Headlines: {json.dumps(titles)}
Snippets: {json.dumps(texts)}

Respond JSON: {{"summary": "...", "sentiment": "positive|neutral|negative", "risk": "low|medium|high", "top_insight": "..."}}"""

        result_text = await self._gemini_call(prompt)
        result = self._safe_json(result_text, {"summary": result_text})
        result["articles"] = articles[:5]
        return result

    # ── Helpers ───────────────────────────────────────────────────

    def _build_context(self, queries, articles, sentiment_summary, risk_report, source_profiles, fact_results) -> str:
        """Build compact context string within token budget."""
        parts = [
            f"QUERIES: {', '.join(queries)}",
            f"\nARTICLES ({len(articles)} total, showing top 8):",
        ]
        for a in articles[:8]:
            parts.append(f"- [{a.get('source','?')}] {a.get('title','')} | {a.get('description','')[:150]}")

        parts.append(f"\nSENTIMENT: overall={sentiment_summary.get('overall','?')}, "
                    f"positive={sentiment_summary.get('positive_pct',0):.0%}, "
                    f"negative={sentiment_summary.get('negative_pct',0):.0%}")

        parts.append(f"\nRISK: level={risk_report.get('overall_risk','?')}, "
                    f"score={risk_report.get('risk_score',0)}/100")

        if risk_report.get("risk_factors"):
            parts.append(f"Risk factors: {', '.join(risk_report['risk_factors'][:5])}")

        if fact_results:
            parts.append(f"\nFACT CHECK: {len([f for f in fact_results if f.get('verified')])} verified, "
                        f"{len([f for f in fact_results if not f.get('verified')])} unverified")

        return "\n".join(parts)

    def _extract_domain(self, url: str) -> str:
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc.replace("www.", "")
        except:
            return ""

    def _safe_json(self, text: str, fallback: dict) -> dict:
        """Safely parse JSON from Gemini response, handling markdown fences."""
        try:
            cleaned = text.strip()
            if "```" in cleaned:
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
            return json.loads(cleaned.strip())
        except Exception:
            return fallback
