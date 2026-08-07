"""Unified Python BullMQ worker entrypoint.

Starts all workers:
- ingestion.parse, ingestion.chunk, ingestion.embed, ingestion.index, ingestion.validate
- memory.summarize, memory.prune
- tool-execution
- calibration, synthetic-fixture
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal

from app.core.settings import get_settings
from app.infrastructure.database import create_session_factory
from app.workers.calibration_worker import create_calibration_workers
from app.workers.ingestion_worker import create_ingestion_workers
from app.workers.query_worker import create_query_worker
from app.workers.tool_worker import create_tool_worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

ALL_QUEUES = [
    "ingestion.parse",
    "ingestion.chunk",
    "ingestion.embed",
    "ingestion.index",
    "ingestion.validate",
    "memory.summarize",
    "memory.prune",
    "tool-execution",
    "calibration",
    "synthetic-fixture",
    "rag.query",
]


async def main() -> None:
    settings = get_settings()
    redis_url = os.environ.get("REDIS_URL", "redis://127.0.0.1:6380")
    session_factory = create_session_factory(settings)

    logger.info("Starting Open Grounding unified worker")
    logger.info("Redis: %s", redis_url)

    workers = [
        *create_ingestion_workers(settings, session_factory, redis_url),
        create_tool_worker(settings, session_factory, redis_url),
        *create_calibration_workers(settings, session_factory, redis_url),
        create_query_worker(settings, session_factory, redis_url),
    ]

    logger.info(
        "Active queues (%d): %s",
        len(ALL_QUEUES),
        ", ".join(ALL_QUEUES),
    )

    loop = asyncio.get_event_loop()

    async def _shutdown() -> None:
        logger.info("Shutting down workers...")
        await asyncio.gather(*[w.close() for w in workers], return_exceptions=True)
        logger.info("All workers stopped")

    def _handle_signal(sig: int) -> None:
        logger.info("Received signal %s", sig)
        loop.create_task(_shutdown())

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_signal, sig)

    # Keep running until shutdown
    stop_event = asyncio.Event()

    def _set_stop(sig: int) -> None:
        _handle_signal(sig)
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _set_stop, sig)

    await stop_event.wait()


if __name__ == "__main__":
    asyncio.run(main())
