"""Python BullMQ-compatible worker for RAG ingestion pipeline.

Consumes jobs from BullMQ queues via Redis XREAD streams.
Each stage: parse → chunk → embed → index → validate.
"""

import asyncio
import json
import logging
import os
import signal
import sys

from app.core.settings import get_settings
from app.workers.ingestion_worker import IngestionWorker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    redis_url = os.environ.get("REDIS_URL", "redis://127.0.0.1:6380")

    logger.info("Starting Open Grounding ingestion worker")
    logger.info("Redis: %s", redis_url)

    worker = IngestionWorker(settings=settings, redis_url=redis_url)

    loop = asyncio.get_event_loop()

    def _shutdown(sig: int) -> None:
        logger.info("Received signal %s, shutting down...", sig)
        loop.create_task(worker.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _shutdown, sig)

    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())
