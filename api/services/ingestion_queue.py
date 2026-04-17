"""
Ingestion Queue Service
- Redis-backed queue cho ingest/reingest jobs
- Có thể chạy worker trong FastAPI process hoặc tách thành process riêng
"""
from __future__ import annotations

import json
import logging
import uuid

from redis.exceptions import TimeoutError as RedisTimeoutError

from core.config import settings
from core.redis_client import get_cache_manager

logger = logging.getLogger("ebook.ingestion_queue")


def _build_job_payload(book_id: str, job_type: str) -> dict:
    return {
        "job_id": str(uuid.uuid4()),
        "book_id": book_id,
        "job_type": job_type,
    }


async def enqueue_ingestion_job(book_id: str, job_type: str = "ingest") -> dict:
    """Đẩy ingestion job vào Redis queue."""
    payload = _build_job_payload(book_id, job_type)
    redis = await get_cache_manager().get_redis()
    if not redis:
        raise RuntimeError("Redis chưa sẵn sàng cho ingestion queue")
    await redis.lpush(settings.ingestion_queue_name, json.dumps(payload))
    logger.info("Enqueued %s job for book %s", job_type, book_id)
    return payload


async def dequeue_ingestion_job() -> dict | None:
    """Lấy job tiếp theo từ queue, block theo timeout cấu hình."""
    redis = await get_cache_manager().get_redis()
    if not redis:
        return None

    try:
        item = await redis.brpop(
            settings.ingestion_queue_name,
            timeout=settings.ingestion_worker_poll_timeout,
        )
    except RedisTimeoutError:
        # No job arrived within the blocking window. This is normal for idle workers.
        return None
    if not item:
        return None

    _, raw_payload = item
    return json.loads(raw_payload)
