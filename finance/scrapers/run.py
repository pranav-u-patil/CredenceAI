import asyncio

from aiokafka import AIOKafkaProducer
from loguru import logger

from config.settings import get_settings
from ingestion.scrapers.scrapers import ScraperOrchestrator

settings = get_settings()

CYCLE_INTERVAL = 15 * 60  # 15 minutes
DAILY_INTERVAL = 24 * 3600


async def main():
    logger.info("[Scrapers] Starting APEX Scraper Service…")
    producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_bootstrap)
    await producer.start()
    logger.info("[Scrapers] Kafka producer connected")

    orch = ScraperOrchestrator(producer)
    last_daily = 0.0
    cycle = 0

    try:
        while True:
            cycle += 1
            logger.info(f"[Scrapers] Cycle #{cycle}")
            try:
                await orch.run_cycle()
            except Exception as e:
                logger.error(f"[Scrapers] Cycle error: {e}")

            now = asyncio.get_event_loop().time()
            if now - last_daily > DAILY_INTERVAL:
                try:
                    await orch.run_daily()
                    last_daily = now
                except Exception as e:
                    logger.error(f"[Scrapers] Daily error: {e}")

            logger.info(f"[Scrapers] Next cycle in {CYCLE_INTERVAL // 60}m")
            await asyncio.sleep(CYCLE_INTERVAL)
    finally:
        await producer.stop()


if __name__ == "__main__":
    asyncio.run(main())