"""
Reranker Service
- Nhận danh sách chunks đã retrieve
- Tính cosine similarity giữa query embedding và từng chunk
- Rerank và trả về top-k chunks chất lượng nhất
"""
import numpy as np
from models.schemas import ChunkInfo
from services.embedding import embed_text, embed_batch


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Tính cosine similarity giữa 2 vectors."""
    arr_a = np.array(a, dtype=np.float32)
    arr_b = np.array(b, dtype=np.float32)
    norm_a = np.linalg.norm(arr_a)
    norm_b = np.linalg.norm(arr_b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(arr_a, arr_b) / (norm_a * norm_b))


def _deduplicate_chunks(chunks: list[ChunkInfo], threshold: float = 0.95) -> list[ChunkInfo]:
    """
    Loại bỏ các chunks gần trùng lặp.
    Dùng text overlap đơn giản (không cần embedding).
    """
    seen: list[str] = []
    unique: list[ChunkInfo] = []

    for chunk in chunks:
        is_duplicate = False
        text_a = chunk.content.lower().strip()

        for seen_text in seen:
            # Tính overlap dựa trên ký tự chung
            set_a = set(text_a.split())
            set_b = set(seen_text.split())
            if not set_a or not set_b:
                continue
            overlap = len(set_a & set_b) / min(len(set_a), len(set_b))
            if overlap > threshold:
                is_duplicate = True
                break

        if not is_duplicate:
            seen.append(text_a)
            unique.append(chunk)

    return unique


async def rerank_chunks(
    query: str,
    chunks: list[ChunkInfo],
    top_k: int,
    query_embedding: list[float] | None = None,
) -> list[ChunkInfo]:
    """
    Rerank chunks theo semantic similarity với query.

    Flow:
    1. Embed query (hoặc dùng embedding có sẵn)
    2. Embed tất cả chunks
    3. Tính cosine similarity
    4. Kết hợp với hybrid search score (nếu có)
    5. Dedup + trả về top-k

    Args:
        query: Câu hỏi gốc
        chunks: Danh sách chunks từ retrieval (đã có hybrid score)
        top_k: Số chunks muốn giữ lại
        query_embedding: Embedding của query (tránh embed lại nếu đã có)
    """
    if not chunks:
        return []

    # Dedup trước để tránh xử lý trùng
    chunks = _deduplicate_chunks(chunks)

    if len(chunks) <= top_k:
        return chunks

    # Embed query nếu chưa có
    if query_embedding is None:
        query_embedding = await embed_text(query)

    # Embed toàn bộ chunks
    chunk_texts = [c.content for c in chunks]
    chunk_embeddings = await embed_batch(chunk_texts)

    # Tính cosine similarity và kết hợp với hybrid score
    scored: list[tuple[float, ChunkInfo]] = []
    for chunk, chunk_emb in zip(chunks, chunk_embeddings):
        semantic_score = _cosine_similarity(query_embedding, chunk_emb)

        # Hybrid: 60% semantic rerank + 40% hybrid search score từ pgvector
        hybrid_score = chunk.score or 0.0
        final_score = 0.6 * semantic_score + 0.4 * hybrid_score

        scored.append((final_score, chunk))

    # Sort descending và lấy top-k
    scored.sort(key=lambda x: x[0], reverse=True)
    top_chunks = [chunk for _, chunk in scored[:top_k]]

    # Cập nhật score mới vào chunk
    for (score, _), chunk in zip(scored[:top_k], top_chunks):
        chunk.score = score

    return top_chunks
