"""
orchestration/kafka/topic_admin.py
CLI utility to create, list, inspect and reset Kafka topics
Usage: python topic_admin.py [create|list|describe|reset]
"""

import asyncio
import sys

from loguru import logger

from config.settings import get_settings
from streaming.kafka_streams import TOPICS, create_topics

settings = get_settings()


async def list_topics():
    from aiokafka.admin import AIOKafkaAdminClient

    admin = AIOKafkaAdminClient(bootstrap_servers=settings.kafka_bootstrap)
    await admin.start()
    try:
        topics = sorted(await admin.list_topics())
        apex = [t for t in topics if t.startswith("apex.")]
        print("\n=== Kafka Topics ===")
        for t in apex:
            print(f"  {t}")
        print(f"\nTotal APEX topics: {len(apex)}")
    finally:
        await admin.close()


async def describe_topics():
    from aiokafka.admin import AIOKafkaAdminClient

    admin = AIOKafkaAdminClient(bootstrap_servers=settings.kafka_bootstrap)
    await admin.start()
    try:
        existing = set(await admin.list_topics())
        print("\n=== APEX Topic Registry ===")
        for key, cfg in TOPICS.items():
            status = "✓ exists" if cfg.name in existing else "✗ missing"
            print(f"  {key:12} → {cfg.name:35} ({cfg.partitions}p) [{status}]")
    finally:
        await admin.close()


async def reset_topic(topic_name: str):
    """Delete and recreate a topic (clears all messages)."""
    from aiokafka.admin import AIOKafkaAdminClient, NewTopic

    admin = AIOKafkaAdminClient(bootstrap_servers=settings.kafka_bootstrap)
    await admin.start()
    try:
        existing = set(await admin.list_topics())
        if topic_name in existing:
            await admin.delete_topics([topic_name])
            await asyncio.sleep(2)
            logger.info(f"Deleted topic: {topic_name}")
        cfg = next((v for v in TOPICS.values() if v.name == topic_name), None)
        if cfg:
            await admin.create_topics(
                [
                    NewTopic(
                        name=cfg.name,
                        num_partitions=cfg.partitions,
                        replication_factor=cfg.replication,
                    )
                ]
            )
            logger.info(f"Recreated topic: {topic_name}")
    finally:
        await admin.close()


async def consumer_groups():
    from aiokafka.admin import AIOKafkaAdminClient

    admin = AIOKafkaAdminClient(bootstrap_servers=settings.kafka_bootstrap)
    await admin.start()
    try:
        groups = await admin.list_consumer_groups()
        apex = [(gid, state) for gid, state in groups if "apex" in gid.lower()]
        print("\n=== Consumer Groups ===")
        for gid, state in apex:
            print(f"  {gid:40} [{state}]")
    finally:
        await admin.close()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "describe"
    if cmd == "create":
        asyncio.run(create_topics())
    elif cmd == "list":
        asyncio.run(list_topics())
    elif cmd == "describe":
        asyncio.run(describe_topics())
    elif cmd == "groups":
        asyncio.run(consumer_groups())
    elif cmd == "reset" and len(sys.argv) > 2:
        asyncio.run(reset_topic(sys.argv[2]))
    else:
        print("Usage: python topic_admin.py [create|list|describe|groups|reset <topic>]")