"""
Standalone worker entrypoint.
Chạy riêng process, không chung event loop với FastAPI.
PM2: pm2 start "venv/bin/python worker.py" --name ebook-worker --cwd /path/to/api
"""
from __future__ import annotations

import asyncio
import logging

# Load .env trước khi import bất kỳ module nào sử dụng settings
from dotenv import load_dotenv
load_dotenv()

from core.redis_client import get_cache_manager
from services.ingestion_worker import run_worker_forever

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("ebook.worker")


async def main() -> None:
    logger.info("Standalone ingestion worker starting...")
    # Test Redis connection
    cache = get_cache_manager()
    redis = await cache.get_redis()
    if redis:
        logger.info("Redis connected, starting queue polling...")
    else:
        logger.error("Redis not available! Worker cannot function.")
        return
    await run_worker_forever("standalone-worker")


if __name__ == "__main__":
    asyncio.run(main())
