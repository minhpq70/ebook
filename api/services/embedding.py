"""
Embedding Service — OpenAI text-embedding-3-small with Redis Caching
- Embed single text with caching
- Embed batch (tối ưu API calls)
- Cache embeddings to avoid re-computation
"""
import asyncio
import logging
from core.openai_client import get_openai
from core.redis_client import get_cache_manager
from core.config import settings

logger = logging.getLogger("ebook.embedding")


async def embed_text(text: str) -> list[float]:
    """Embed một đoạn text với caching."""
    if not text or not text.strip():
        return []

    # Try cache first
    cache_manager = get_cache_manager()
    cached_embedding = await cache_manager.get_embedding(text)
    if cached_embedding:
        logger.debug("Using cached embedding")
        return cached_embedding

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
    all_embeddings: list[list[float]] = []
    uncached_texts = []
    uncached_indices = []

    # Check cache for all texts first
    for i, text in enumerate(texts):
        if text and text.strip():
            cached = await cache_manager.get_embedding(text)
            if cached:
                all_embeddings.append(cached)
            else:
                uncached_texts.append(text)
                uncached_indices.append(i)
                all_embeddings.append([])  # Placeholder
        else:
            all_embeddings.append([])

    # If all texts were cached, return immediately
    if not uncached_texts:
        logger.info(f"All {len(texts)} embeddings retrieved from cache")
        return all_embeddings

    # Compute embeddings for uncached texts
    logger.info(f"Computing {len(uncached_texts)} new embeddings, {len(texts) - len(uncached_texts)} from cache")

    client = get_openai()
    uncached_embeddings = []

    for i in range(0, len(uncached_texts), batch_size):
        batch = uncached_texts[i: i + batch_size]
        response = await client.embeddings.create(
            model=settings.openai_embedding_model,
            input=batch,
            encoding_format="float"
        )

        # Sort by index to maintain order
        sorted_data = sorted(response.data, key=lambda x: x.index)
        batch_embeddings = [item.embedding for item in sorted_data]
        uncached_embeddings.extend(batch_embeddings)

        # Cache each embedding
        for text, embedding in zip(batch, batch_embeddings):
            await cache_manager.set_embedding(text, embedding)

        # Rate limit delay if more batches
        if i + batch_size < len(uncached_texts):
            await asyncio.sleep(0.1)

    # Fill in the cached results
    for idx, embedding in zip(uncached_indices, uncached_embeddings):
        all_embeddings[idx] = embedding

    return all_embeddings
