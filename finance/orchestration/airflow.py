"""
orchestration/airflow/dags/all_dags.py
All 5 APEX Airflow DAGs in one file:
  1. apex_scrape          — every 15 min: news, Reddit, NSE bulk
  2. apex_signals         — every 30 min: 5-agent AI analysis
  3. apex_macro_refresh   — hourly: FRED macro data
  4. apex_sec_edgar       — weekday 9am: Form 4 + 13F
  5. apex_daily_report    — daily 6am: Monte Carlo report
"""

import asyncio
import json
import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

sys.path.insert(0, "/app")

DEFAULT = {
    "owner": "apex",
    "retries": 2,
    "retry_delay": timedelta(minutes=3),
    "email_on_failure": False,
    "execution_timeout": timedelta(minutes=20),
}

WATCHLIST = [
    "NVDA",
    "AAPL",
    "MSFT",
    "META",
    "TSLA",
    "BRK-B",
    "JPM",
    "GS",
    "GLD",
    "USO",
    "TLT",
    "BTC-USD",
    "ETH-USD",
    "RELIANCE.NS",
    "HDFCBANK.NS",
    "TCS.NS",
]


# ────────────────────────────────────────────────────────────────────────────
# DAG 1 — Scrape (every 15 min)
# ────────────────────────────────────────────────────────────────────────────
def _scrape(**_):
    from config.settings import get_settings
    from ingestion.scrapers.scrapers import ScraperOrchestrator
    from streaming.kafka_streams import create_topics, make_producer

    settings = get_settings()

    async def run():
        await create_topics()
        prod = await make_producer()
        try:
            orch = ScraperOrchestrator(prod)
            await orch.run_cycle()
        finally:
            await prod.stop()

    asyncio.run(run())


with DAG(
    "apex_scrape",
    default_args=DEFAULT,
    schedule_interval="*/15 * * * *",
    start_date=days_ago(1),
    catchup=False,
    tags=["apex", "scraping"],
) as dag1:
    PythonOperator(task_id="run_scrapers", python_callable=_scrape)


# ────────────────────────────────────────────────────────────────────────────
# DAG 2 — AI Signal Generation (every 30 min)
# ────────────────────────────────────────────────────────────────────────────
def _signals(**_):
    from agents.crew.crew import APEXCrew
    from config.settings import get_settings
    from streaming.kafka_streams import make_producer

    settings = get_settings()

    async def run():
        crew = APEXCrew()
        prod = await make_producer()
        try:
            results = await crew.batch_analyze(WATCHLIST)
            for r in results:
                if isinstance(r, dict) and r.get("conviction", 50) != 50:
                    await prod.send_and_wait(
                        settings.kafka_topics["signals"], json.dumps(r, default=str).encode()
                    )
                    print(
                        f"Signal: {r.get('symbol')} {r.get('signal_type')} "
                        f"conviction={r.get('conviction',50):.0f}%"
                    )
        finally:
            await prod.stop()

    asyncio.run(run())


with DAG(
    "apex_signals",
    default_args=DEFAULT,
    schedule_interval="*/30 * * * *",
    start_date=days_ago(1),
    catchup=False,
    tags=["apex", "agents", "signals"],
) as dag2:
    PythonOperator(task_id="run_agent_crew", python_callable=_signals)


# ────────────────────────────────────────────────────────────────────────────
# DAG 3 — Macro Refresh (hourly)
# ────────────────────────────────────────────────────────────────────────────
def _macro(**_):
    import redis as syncredis

    from config.settings import get_settings
    from ingestion.feeds.market_feeds import FREDFeed

    settings = get_settings()

    async def run():
        feed = FREDFeed()
        data = await feed.all_macro()
        r = syncredis.from_url(settings.redis_url)
        r.setex(
            "macro:snapshot",
            3600,
            json.dumps(
                {k: float(v.iloc[-1]) if hasattr(v, "iloc") else v for k, v in data.items()},
                default=str,
            ),
        )
        r.close()
        print(f"Macro refreshed: {list(data.keys())}")

    asyncio.run(run())


with DAG(
    "apex_macro_refresh",
    default_args=DEFAULT,
    schedule_interval="@hourly",
    start_date=days_ago(1),
    catchup=False,
    tags=["apex", "macro"],
) as dag3:
    PythonOperator(task_id="refresh_fred_macro", python_callable=_macro)


# ────────────────────────────────────────────────────────────────────────────
# DAG 4 — SEC EDGAR (weekdays 9am UTC)
# ────────────────────────────────────────────────────────────────────────────
def _sec(**_):
    from config.settings import get_settings
    from ingestion.scrapers.scrapers import SECEdgarScraper
    from streaming.kafka_streams import make_producer

    settings = get_settings()

    async def run():
        prod = await make_producer()
        try:
            scraper = SECEdgarScraper(prod)
            await scraper.form4(days_back=2)
            await scraper.form_13f(days_back=90)
            await scraper.congressional()
        finally:
            await prod.stop()

    asyncio.run(run())


with DAG(
    "apex_sec_edgar",
    default_args=DEFAULT,
    schedule_interval="0 9 * * 1-5",
    start_date=days_ago(1),
    catchup=False,
    tags=["apex", "sec", "insiders"],
) as dag4:
    PythonOperator(task_id="scrape_sec_edgar", python_callable=_sec)


# ────────────────────────────────────────────────────────────────────────────
# DAG 5 — Daily Monte Carlo Report (6am UTC)
# ────────────────────────────────────────────────────────────────────────────
def _daily_report(**_):

    from ingestion.feeds.market_feeds import YFinanceFeed
    from models.monte_carlo.gbm_hawkes import HawkesProcess, MonteCarloPricer

    pricer = MonteCarloPricer()
    report = {"generated_at": datetime.utcnow().isoformat(), "simulations": {}}

    for sym in WATCHLIST[:8]:
        try:
            df = YFinanceFeed.history(sym, period="1y")
            close = df["Close"].squeeze().values
            mc = pricer.run(close, horizon_days=30, n_paths=500)
            mc.pop("paths_sample", None)

            # Hawkes shock analysis
            ret = df["Close"].squeeze().pct_change().dropna().values
            thresh = float(ret.std() * 2)
            shocks = [float(i) for i, r in enumerate(ret) if abs(r) > thresh]
            hp = HawkesProcess()
            if len(shocks) > 5:
                params = hp.fit(shocks, T=float(len(ret)))
                mc["hawkes"] = {
                    "params": params,
                    "expected_30d": round(hp.expected_events(30.0, shocks[-10:]), 2),
                }
            report["simulations"][sym] = mc
            print(
                f"{sym}: prob_profit={mc['prob_profit']:.1%} " f"kelly={mc['kelly_fraction']:.1%}"
            )
        except Exception as e:
            print(f"{sym} error: {e}")

    with open("/tmp/apex_daily_report.json", "w") as f:
        json.dump(report, f, default=str, indent=2)
    print(f"Daily report saved: {len(report['simulations'])} symbols")


with DAG(
    "apex_daily_report",
    default_args=DEFAULT,
    schedule_interval="0 6 * * *",
    start_date=days_ago(1),
    catchup=False,
    tags=["apex", "report", "mc"],
) as dag5:
    PythonOperator(task_id="generate_daily_report", python_callable=_daily_report)