import asyncio
import json
import re
from datetime import datetime, timedelta

import aiohttp
from aiokafka import AIOKafkaProducer
from loguru import logger

from config.settings import get_settings

settings = get_settings()

try:
    import feedparser

    FEEDPARSER = True
except ImportError:
    FEEDPARSER = False
    logger.warning("feedparser not installed: pip install feedparser")

try:
    import praw

    PRAW = True
except ImportError:
    PRAW = False

NEWS_FEEDS = [
    ("Reuters Business", "https://feeds.reuters.com/reuters/businessNews"),
    ("Reuters Markets", "https://feeds.reuters.com/reuters/UKmarkets"),
    ("CNBC Finance", "https://www.cnbc.com/id/10000664/device/rss/rss.html"),
    ("MarketWatch", "https://feeds.marketwatch.com/marketwatch/topstories/"),
    ("Yahoo Finance", "https://finance.yahoo.com/rss/topfinstories"),
    ("Seeking Alpha", "https://seekingalpha.com/market_currents.xml"),
    ("ZeroHedge", "https://feeds.feedburner.com/zerohedge/feed"),
    ("Economic Times", "https://economictimes.indiatimes.com/markets/rss.cms"),
    ("Business Standard", "https://www.business-standard.com/rss/finance-us.rss"),
    ("Mint Markets", "https://www.livemint.com/rss/markets"),
    ("Investing.com", "https://www.investing.com/rss/news_25.rss"),
]

ENTITY_MAP = {
    "Apple": "AAPL",
    "Microsoft": "MSFT",
    "Nvidia": "NVDA",
    "NVIDIA": "NVDA",
    "Tesla": "TSLA",
    "Amazon": "AMZN",
    "Google": "GOOGL",
    "Alphabet": "GOOGL",
    "Meta": "META",
    "Netflix": "NFLX",
    "Bitcoin": "BTC-USD",
    "Ethereum": "ETH-USD",
    "Buffett": "BRK-B",
    "Berkshire": "BRK-B",
    "JPMorgan": "JPM",
    "Goldman": "GS",
    "Reliance": "RELIANCE.NS",
    "Infosys": "INFY.NS",
    "TCS": "TCS.NS",
    "HDFC": "HDFCBANK.NS",
    "Wipro": "WIPRO.NS",
}

SEC_HEADERS = {"User-Agent": "APEX-Research apex@research.io"}
REDDIT_HEADERS = {"User-Agent": "APEX-Intelligence/1.0 (research tool)"}


def extract_symbols(text: str) -> list:
    """Extract ticker symbols and known entity names from text."""
    found = []
    for m in re.findall(r"\$([A-Z]{1,5})\b", text):
        found.append(m)
    for name, sym in ENTITY_MAP.items():
        if name in text:
            found.append(sym)
    return list(set(found))[:10]


class NewsScraper:
    def __init__(self, producer: AIOKafkaProducer):
        self.producer = producer
        self.seen: set = set()

    async def run(self):
        await asyncio.gather(
            *[self._scrape_feed(name, url) for name, url in NEWS_FEEDS],
            return_exceptions=True,
        )

    async def _scrape_feed(self, source: str, url: str):
        if not FEEDPARSER:
            return
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                    content = await r.text()
        except Exception as e:
            logger.debug(f"Feed {source} error: {e}")
            return

        feed = feedparser.parse(content)
        count = 0
        for entry in feed.entries[:20]:
            link = entry.get("link", "")
            if link in self.seen:
                continue
            self.seen.add(link)
            text = f"{entry.get('title', '')} {entry.get('summary', '')}"
            msg = {
                "type": "news",
                "source": source,
                "title": entry.get("title", "")[:300],
                "summary": entry.get("summary", "")[:500],
                "url": link,
                "published_at": str(entry.get("published", datetime.utcnow().isoformat())),
                "symbols": extract_symbols(text),
                "ts": datetime.utcnow().isoformat(),
            }
            await self.producer.send_and_wait(settings.topics["news"], json.dumps(msg).encode())
            count += 1
        if count:
            logger.info(f"News [{source}]: {count} new items")


class SECEdgarScraper:
    def __init__(self, producer: AIOKafkaProducer):
        self.producer = producer

    async def form4(self, days_back: int = 1):
        """SEC Form 4 — insider trades. Free, no auth."""
        start = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        url = f"https://efts.sec.gov/LATEST/search-index?q=%22form+4%22&dateRange=custom&startdt={start}&forms=4"
        try:
            async with aiohttp.ClientSession(headers=SEC_HEADERS) as s:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=20)) as r:
                    data = await r.json()
            for f in data.get("hits", {}).get("hits", [])[:100]:
                src = f.get("_source", {})
                msg = {
                    "type": "sec_form4",
                    "entity_name": src.get("entity_name", ""),
                    "filed_at": src.get("file_date", ""),
                    "accession": src.get("accession_no", ""),
                    "ts": datetime.utcnow().isoformat(),
                }
                await self.producer.send_and_wait(
                    settings.topics["insiders"], json.dumps(msg).encode()
                )
            logger.info("SEC Form 4: scrape complete")
        except Exception as e:
            logger.error(f"SEC Form4 error: {e}")

    async def form_13f(self, days_back: int = 90):
        """SEC 13F — institutional holdings. Free, no auth."""
        start = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        url = f"https://efts.sec.gov/LATEST/search-index?forms=13F-HR&dateRange=custom&startdt={start}"
        try:
            async with aiohttp.ClientSession(headers=SEC_HEADERS) as s:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=20)) as r:
                    data = await r.json()
            for f in data.get("hits", {}).get("hits", [])[:50]:
                src = f.get("_source", {})
                msg = {
                    "type": "sec_13f",
                    "institution": src.get("entity_name", ""),
                    "filed_at": src.get("file_date", ""),
                    "accession": src.get("accession_no", ""),
                    "ts": datetime.utcnow().isoformat(),
                }
                await self.producer.send_and_wait(
                    settings.topics["insiders"], json.dumps(msg).encode()
                )
            logger.info("SEC 13F: scrape complete")
        except Exception as e:
            logger.error(f"SEC 13F error: {e}")

    async def congressional(self):
        """HouseStockWatcher — STOCK Act disclosures. Free JSON API."""
        url = (
            "https://house-stock-watcher-data.s3-us-east-2.amazonaws.com/data/all_transactions.json"
        )
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=30)) as r:
                    trades = await r.json()
            for t in trades[:100]:
                msg = {
                    "type": "congressional",
                    "representative": t.get("representative", ""),
                    "symbol": t.get("ticker", ""),
                    "trade_type": t.get("type", ""),
                    "amount": t.get("amount", ""),
                    "transaction_date": t.get("transaction_date", ""),
                    "ts": datetime.utcnow().isoformat(),
                }
                await self.producer.send_and_wait(
                    settings.topics["insiders"], json.dumps(msg).encode()
                )
            logger.info(f"Congressional: {min(len(trades), 100)} trades scraped")
        except Exception as e:
            logger.error(f"Congressional scrape error: {e}")


class RedditScraper:
    SUBREDDITS = [
        "wallstreetbets",
        "investing",
        "options",
        "stocks",
        "IndiaInvestments",
        "SecurityAnalysis",
    ]

    def __init__(self, producer: AIOKafkaProducer):
        self.producer = producer
        self.reddit = None
        if PRAW and settings.reddit_client_id:
            try:
                self.reddit = praw.Reddit(
                    client_id=settings.reddit_client_id,
                    client_secret=settings.reddit_secret,
                    user_agent=settings.reddit_user_agent,
                    read_only=True,
                )
            except Exception:
                pass

    async def run(self):
        # Use no-auth JSON endpoint (free, 60 req/min)
        for sub in self.SUBREDDITS[:4]:
            try:
                url = f"https://www.reddit.com/r/{sub}/hot.json?limit=25"
                async with aiohttp.ClientSession(headers=REDDIT_HEADERS) as s:
                    async with s.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                        data = await r.json()
                posts = data.get("data", {}).get("children", [])
                for p in posts:
                    d = p["data"]
                    text = d.get("title", "")
                    msg = {
                        "type": "social",
                        "platform": "reddit",
                        "subreddit": sub,
                        "author": d.get("author", ""),
                        "content": text[:400],
                        "score": d.get("score", 0),
                        "comments": d.get("num_comments", 0),
                        "symbols": extract_symbols(text),
                        "url": f"https://reddit.com{d.get('permalink', '')}",
                        "posted_at": datetime.utcfromtimestamp(d.get("created_utc", 0)).isoformat(),
                        "ts": datetime.utcnow().isoformat(),
                    }
                    await self.producer.send_and_wait(
                        settings.topics["social"], json.dumps(msg).encode()
                    )
                logger.info(f"Reddit r/{sub}: {len(posts)} posts")
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Reddit r/{sub} error: {e}")


class NSEBulkScraper:
    def __init__(self, producer: AIOKafkaProducer):
        self.producer = producer

    async def run(self):
        from ingestion.feeds.market_feeds import NSEFeed

        nse = NSEFeed()
        for fetch_method, label in [("bulk_deals", "bulk"), ("block_deals", "block")]:
            try:
                df = await getattr(nse, fetch_method)()
                if df is not None and not df.empty:
                    for _, row in df.iterrows():
                        d = row.to_dict()
                        d["type"] = f"nse_{label}"
                        d["ts"] = datetime.utcnow().isoformat()
                        await self.producer.send_and_wait(
                            settings.topics["insiders"], json.dumps(d, default=str).encode()
                        )
                    logger.info(f"NSE {label}: {len(df)} records")
            except Exception as e:
                logger.error(f"NSE {label} error: {e}")


class ScraperOrchestrator:
    def __init__(self, producer: AIOKafkaProducer):
        self.news = NewsScraper(producer)
        self.sec = SECEdgarScraper(producer)
        self.reddit = RedditScraper(producer)
        self.nse = NSEBulkScraper(producer)

    async def run_cycle(self):
        """15-minute cycle: news + Reddit + NSE + congressional."""
        await asyncio.gather(
            self.news.run(),
            self.sec.form4(days_back=1),
            self.sec.congressional(),
            self.reddit.run(),
            self.ns e.run(),
            return_exceptions=True,
        )

    async def run_daily(self):
        """Daily: heavy 13F scrape."""
        await self.sec.form_13f(days_back=90)