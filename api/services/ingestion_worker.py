"""
Ingestion Worker
- Poll Redis queue và xử lý ingest/reingest jobs
"""
from __future__ import annotations

import asyncio
import logging

from core.config import settings
from services import ingestion
from services.ingestion_queue import dequeue_ingestion_job

logger = logging.getLogger("ebook.ingestion_worker")


async def run_worker_forever(worker_name: str = "worker-1") -> None:
    """Poll queue liên tục và xử lý job."""
    logger.info("Starting ingestion worker %s", worker_name)
    while True:
        try:
            job = await dequeue_ingestion_job()
            if not job:
                continue

            book_id = job["book_id"]
            job_type = job.get("job_type", "ingest")
            logger.info("Worker %s processing %s for book %s", worker_name, job_type, book_id)
            await ingestion.process_ingestion_job(book_id=book_id, job_type=job_type)
        except asyncio.CancelledError:
            logger.info("Stopping ingestion worker %s", worker_name)
            raise
        except Exception as exc:
            logger.error("Worker %s failed to process job: %s", worker_name, exc, exc_info=True)
