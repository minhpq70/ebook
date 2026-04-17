"""
Embedding Service — OpenAI text-embedding-3-small with Redis Caching
- Embed single text with caching
- Embed batch (tối ưu API calls)
- Cache embeddings to avoid re-computation
"""
import asyncio
import logging
import time
from openai import APIConnectionError, APITimeoutError, RateLimitError
from core.openai_client import get_openai
from core.redis_client import get_cache_manager
from core.config import settings
from services.metrics_registry import get_metrics_registry

logger = logging.getLogger("ebook.embedding")


def _group_texts_by_value(texts: list[str]) -> tuple[dict[str, list[int]], list[list[float]]]:
    """
    Gom các text giống nhau để tránh gọi embedding API lặp lại.
    Trả về map text -> các vị trí gốc, cùng placeholder output.
    """
    grouped: dict[str, list[int]] = {}
    results: list[list[float]] = [[] for _ in texts]
    for idx, text in enumerate(texts):
        if text and text.strip():
            grouped.setdefault(text, []).append(idx)
    return grouped, results


async def _embed_request_with_retry(client, batch: list[str]) -> list[list[float]]:
    """Call embeddings API với exponential backoff cho lỗi tạm thời."""
    last_error: Exception | None = None
    for attempt in range(settings.embedding_max_retries):
        try:
            response = await client.embeddings.create(
                model=settings.openai_embedding_model,
                input=batch,
                encoding_format="float"
            )
            sorted_data = sorted(response.data, key=lambda x: x.index)
            return [item.embedding for item in sorted_data]
        except (RateLimitError, APITimeoutError, APIConnectionError) as exc:
            last_error = exc
            delay = min(2 ** attempt, 8) + 0.1 * attempt
            logger.warning(
                "Embedding batch retry %d/%d after error: %s",
                attempt + 1,
                settings.embedding_max_retries,
                exc,
            )
            await asyncio.sleep(delay)
    if last_error is not None:
        raise last_error
    return []


async def embed_text(text: str) -> list[float]:
    """Embed một đoạn text với caching."""
    if not text or not text.strip():
        return []

    # Try cache first
    cache_manager = get_cache_manager()
    cached_embedding = await cache_manager.get_embedding(text)
    if cached_embedding:
        logger.debug("Using cached embedding")
        get_metrics_registry().record_cache("embedding", True)
        return cached_embedding
    get_metrics_registry().record_cache("embedding", False)

    # Compute new embedding
    client = get_openai()
    response = await client.embeddings.create(
        model=settings.openai_embedding_model,
        input=text,
        encoding_format="float"
    )
    embedding = response.data[0].embedding

    # Cache the result
    await cache_manager.set_embedding(text, embedding)

    return embedding


async def embed_batch(texts: list[str], batch_size: int = 100) -> list[list[float]]:
    """
    Embed nhiều đoạn text cùng lúc với caching.
    OpenAI hỗ trợ batch tối đa 2048 inputs, mỗi input max 8191 tokens.
    Chia thành batches để tránh rate limit.
    """
    if not texts:
        return []

    cache_manager = get_cache_manager()
    grouped_texts, all_embeddings = _group_texts_by_value(texts)
    uncached_texts: list[str] = []
    started_at = time.perf_counter()
    metrics = get_metrics_registry()

    for text, indices in grouped_texts.items():
        cached = await cache_manager.get_embedding(text)
        if cached:
            metrics.record_cache("embedding", True)
            for idx in indices:
                all_embeddings[idx] = cached
        else:
            metrics.record_cache("embedding", False)
            uncached_texts.append(text)

    if not uncached_texts:
        logger.info(f"All {len(texts)} embeddings retrieved from cache")
        return all_embeddings

    logger.info(f"Computing {len(uncached_texts)} new embeddings, {len(texts) - len(uncached_texts)} from cache")
    client = get_openai()
    semaphore = asyncio.Semaphore(settings.embedding_max_concurrency)
    effective_batch_size = max(1, batch_size or settings.embedding_batch_size)

    async def process_batch(batch: list[str]) -> list[tuple[str, list[float]]]:
        async with semaphore:
            embeddings = await _embed_request_with_retry(client, batch)
            return list(zip(batch, embeddings))

    batches = [
        uncached_texts[i:i + effective_batch_size]
        for i in range(0, len(uncached_texts), effective_batch_size)
    ]
    batch_results = await asyncio.gather(*(process_batch(batch) for batch in batches))

    for result in batch_results:
        for text, embedding in result:
            for idx in grouped_texts[text]:
                all_embeddings[idx] = embedding
            await cache_manager.set_embedding(text, embedding)

    metrics.record_embedding_batch(
        latency_ms=(time.perf_counter() - started_at) * 1000,
        total_inputs=len(texts),
        uncached_inputs=len(uncached_texts),
    )

    return all_embeddings
