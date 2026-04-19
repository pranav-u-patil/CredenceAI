import asyncio
import json
import asyncpg
from aiokafka import AIOKafkaConsumer
from loguru import logger

from config.settings import get_settings
from orchestration.kafka import TOPICS
from processing.nlp.nlp_pipeline import NLPPipeline

settings = get_settings()
nlp = NLPPipeline()


# ──────────────────────────────────────────
# DB
# ──────────────────────────────────────────
async def get_conn():
    return await asyncpg.connect(settings.timescale_dsn)


# ──────────────────────────────────────────
# NORMALIZE
# ──────────────────────────────────────────
def normalize(event: dict):
    return {
        "type": event.get("type"),
        "text": (
            event.get("title")
            or event.get("content")
            or event.get("summary")
            or ""
        ),
        "symbols": event.get("symbols", []),
        "raw": event
    }


# ──────────────────────────────────────────
# WRITE: NEWS
# ──────────────────────────────────────────
async def write_news(conn, e, sentiment, entities):
    try:
        await conn.execute("""
            INSERT INTO news_items(
                title, body, url, source, symbols,
                sentiment_score, sentiment_label, entities, processed
            )
            VALUES($1,$2,$3,$4,$5,$6,$7,$8,TRUE)
            ON CONFLICT (url) DO NOTHING
        """,
            e["raw"].get("title"),
            e["raw"].get("summary"),
            e["raw"].get("url"),
            e["raw"].get("source"),
            e["symbols"],
            sentiment["score"],
            sentiment["label"],
            json.dumps(entities)
        )
    except Exception as ex:
        logger.error(f"[DB] news insert error: {ex}")


# ──────────────────────────────────────────
# WRITE: SOCIAL
# ──────────────────────────────────────────
async def write_social(conn, e, sentiment):
    try:
        await conn.execute("""
            INSERT INTO social_posts(
                platform, author, content, symbols,
                sentiment_score, engagement, url
            )
            VALUES($1,$2,$3,$4,$5,$6,$7)
        """,
            e["raw"].get("platform"),
            e["raw"].get("author"),
            e["raw"].get("content"),
            e["symbols"],
            sentiment["score"],
            e["raw"].get("score", 0),
            e["raw"].get("url")
        )
    except Exception as ex:
        logger.error(f"[DB] social insert error: {ex}")


# ──────────────────────────────────────────
# PROCESS EVENT
# ──────────────────────────────────────────
async def process_event(conn, event: dict):
    e = normalize(event)

    if not e["text"]:
        return

    sentiment = nlp.score(e["text"])
    entities = nlp.extract_entities(e["text"])

    if e["type"] == "news":
        await write_news(conn, e, sentiment, entities)

    elif e["type"] == "social":
        await write_social(conn, e, sentiment)


# ──────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────
async def main():
    consumer = AIOKafkaConsumer(
        TOPICS["news"],
        TOPICS["social"],
        bootstrap_servers=settings.kafka_bootstrap,
        value_deserializer=lambda m: json.loads(m.decode()),
        enable_auto_commit=True,
        auto_offset_reset="latest"
    )

    await consumer.start()
    logger.info("[Processing] Kafka consumer started")

    conn = await get_conn()
    logger.info("[Processing] Connected to TimescaleDB")

    try:
        async for msg in consumer:
            try:
                await process_event(conn, msg.value)
            except Exception as e:
                logger.error(f"[Processing] event error: {e}")

    finally:
        await consumer.stop()
        await conn.close()
        logger.info("[Processing] Shutdown complete")


# ──────────────────────────────────────────
if __name__ == "__main__":
    asyncio.run(main())