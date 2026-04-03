"""
Embedding Service — OpenAI text-embedding-3-small
- Embed single text
- Embed batch (tối ưu API calls)
"""
import asyncio
from core.openai_client import get_openai
from core.config import settings


async def embed_text(text: str) -> list[float]:
    """Embed một đoạn text."""
    client = get_openai()
    response = await client.embeddings.create(
        model=settings.openai_embedding_model,
        input=text,
        encoding_format="float"
    )
    return response.data[0].embedding


async def embed_batch(texts: list[str], batch_size: int = 100) -> list[list[float]]:
    """
    Embed nhiều đoạn text cùng lúc.
    OpenAI hỗ trợ batch tối đa 2048 inputs, mỗi input max 8191 tokens.
    Chia thành batches để tránh rate limit.
    """
    all_embeddings: list[list[float]] = []
    client = get_openai()

    for i in range(0, len(texts), batch_size):
        batch = texts[i: i + batch_size]
        response = await client.embeddings.create(
            model=settings.openai_embedding_model,
            input=batch,
            encoding_format="float"
        )
        # Đảm bảo thứ tự đúng theo index
        sorted_data = sorted(response.data, key=lambda x: x.index)
        all_embeddings.extend([item.embedding for item in sorted_data])

        # Nhỏ delay tránh rate limit nếu batch lớn
        if i + batch_size < len(texts):
            await asyncio.sleep(0.1)

    return all_embeddings
