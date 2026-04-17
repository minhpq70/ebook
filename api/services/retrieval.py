"""
Retrieval Service — Hybrid Search với Query Expansion + Reranking + Caching
Flow:
  1. Query expansion: sinh 2-3 paraphrases tiếng Việt
  2. Tính centroid embedding từ tất cả query variants
  3. Hybrid search (vector + FTS) với top_k * 3 candidates
  4. Semantic reranking để chọn top_k chunks chất lượng nhất
"""
from __future__ import annotations

import hashlib
import math
import time
from core.supabase_client import get_supabase
from core.redis_client import get_cache_manager
from core.config import settings
from models.schemas import ChunkInfo
from .embedding import embed_text
from .query_expander import expand_query, embed_expanded_queries
from .reranker import rerank_chunks
from .metrics_registry import get_metrics_registry


async def retrieve_chunks(
    book_id: str,
    query: str,
    top_k: int | None = None,
    use_query_expansion: bool = True,
) -> list[ChunkInfo]:
    """
    Improved retrieval pipeline với caching:
    1. Check cache first
    2. Query Expansion → tăng recall
    3. Centroid Embedding → embedding đại diện tốt hơn
    4. Hybrid Search với n_candidates lớn hơn → nhiều lựa chọn hơn
    5. Semantic Reranking → chọn đúng chunks nhất
    6. Cache result

    Args:
        book_id: UUID của sách
        query: Câu hỏi của người dùng
        top_k: Số chunks cuối cùng trả về
        use_query_expansion: Có expand query không (thêm ~0.5s latency)
    """
    k = top_k or settings.rag_top_k
    started_at = time.perf_counter()
    metrics = get_metrics_registry()

    # Generate cache key
    query_hash = hashlib.md5(f"{query}:{use_query_expansion}".encode()).hexdigest()[:16]

    # Try cache first
    cache_manager = get_cache_manager()
    cached_result = await cache_manager.get_query_result(query_hash, book_id)
    if cached_result:
        metrics.record_cache("query_result", True)
        # Convert back to ChunkInfo objects
        cached_chunks = [ChunkInfo(**chunk) for chunk in cached_result]
        metrics.record_retrieval(
            latency_ms=(time.perf_counter() - started_at) * 1000,
            candidate_count=len(cached_chunks),
        )
        return cached_chunks
    metrics.record_cache("query_result", False)

    # Cache miss - compute result
    n_candidates = max(k * 4, 12)

    # ── Bước 1: Query Expansion ──────────────────────────────────
    if use_query_expansion:
        query_variants = await expand_query(query)
    else:
        query_variants = [query]

    # ── Bước 2: Centroid Embedding ───────────────────────────────
    if len(query_variants) > 1:
        query_embedding = await embed_expanded_queries(query_variants)
    else:
        query_embedding = await embed_text(query)

    # ── Bước 3: Hybrid Search ────────────────────────────────────
    candidates = await _hybrid_search(
        book_id=book_id,
        query_embedding=query_embedding,
        query_text=query,     # FTS vẫn dùng query gốc (tránh noise từ paraphrases)
        top_k=n_candidates,
    )
    candidates = _prepare_rerank_candidates(candidates, k)

    # ── Bước 4: Semantic Reranking ───────────────────────────────
    reranked = await rerank_chunks(
        query=query,
        chunks=candidates,
        top_k=k,
        query_embedding=query_embedding,
    )
    reranked = await _expand_context_neighbors(book_id, reranked, k)

    # Cache the result
    result_dicts = [chunk.dict() for chunk in reranked]
    await cache_manager.set_query_result(query_hash, book_id, result_dicts)
    metrics.record_retrieval(
        latency_ms=(time.perf_counter() - started_at) * 1000,
        candidate_count=len(candidates),
    )

    return reranked


async def _hybrid_search(
    book_id: str,
    query_embedding: list[float],
    query_text: str,
    top_k: int,
) -> list[ChunkInfo]:
    """Gọi hybrid_search RPC trong Supabase."""
    supabase = get_supabase()
    result = supabase.rpc(
        "hybrid_search",
        {
            "p_book_id": book_id,
            "p_query_emb": query_embedding,
            "p_query_text": query_text,
            "p_top_k": top_k,
            "p_vector_w": settings.rag_vector_weight,
            "p_fts_w": settings.rag_fts_weight,
        }
    ).execute()

    chunks = []
    for row in (result.data or []):
        chunks.append(ChunkInfo(
            id=row["id"],
            chunk_index=row["chunk_index"],
            page_number=row.get("page_number"),
            content=row["content"],
            score=row.get("score"),
        ))
    return chunks


def _prepare_rerank_candidates(
    candidates: list[ChunkInfo],
    top_k: int,
) -> list[ChunkInfo]:
    """
    Giữ tập ứng viên đủ rộng để rerank tốt nhưng không embed quá nhiều text.
    """
    if not candidates:
        return []

    rerank_limit = max(top_k * 3, settings.reranker_max_candidates)
    rerank_limit = min(rerank_limit, len(candidates))
    sorted_candidates = sorted(
        candidates,
        key=lambda chunk: chunk.score or 0.0,
        reverse=True,
    )
    return sorted_candidates[:rerank_limit]


async def _expand_context_neighbors(
    book_id: str,
    chunks: list[ChunkInfo],
    top_k: int,
) -> list[ChunkInfo]:
    """
    Prefetch vài chunk lân cận cho top hits để giảm mất ngữ cảnh tại biên chunk.
    Chỉ thay thế các chunk yếu hơn khi còn thiếu hàng xóm liên quan.
    """
    if not chunks or settings.retrieval_prefetch_neighbors <= 0:
        return chunks

    primary = chunks[:top_k]
    seen_ids = {chunk.id for chunk in primary}
    seen_indices = {chunk.chunk_index for chunk in primary}
    neighbor_indices: set[int] = set()

    for chunk in primary[: min(3, len(primary))]:
        for offset in range(1, settings.retrieval_prefetch_neighbors + 1):
            neighbor_indices.add(chunk.chunk_index - offset)
            neighbor_indices.add(chunk.chunk_index + offset)

    neighbor_indices -= seen_indices
    neighbor_indices = {idx for idx in neighbor_indices if idx >= 0}
    if not neighbor_indices:
        return primary

    supabase = get_supabase()
    result = (
        supabase.table("book_chunks")
        .select("id, chunk_index, page_number, content")
        .eq("book_id", book_id)
        .in_("chunk_index", sorted(neighbor_indices))
        .execute()
    )

    neighbors = [
        ChunkInfo(
            id=row["id"],
            chunk_index=row["chunk_index"],
            page_number=row.get("page_number"),
            content=row["content"],
            score=primary[0].score if primary else 0.0,
        )
        for row in (result.data or [])
        if row["id"] not in seen_ids
    ]
    if not neighbors:
        return primary

    merged = sorted(primary + neighbors, key=lambda chunk: chunk.chunk_index)
    if len(merged) <= top_k:
        return merged

    prioritized = primary[: max(1, math.ceil(top_k / 2))]
    prioritized_ids = {chunk.id for chunk in prioritized}
    tail = [chunk for chunk in merged if chunk.id not in prioritized_ids]
    return prioritized + tail[: max(0, top_k - len(prioritized))]


async def retrieve_chunks_by_page_range(
    book_id: str,
    page_start: int,
    page_end: int,
) -> list[ChunkInfo]:
    """
    Lấy chunks theo range trang — dùng cho summarize_chapter
    khi người dùng chỉ định phạm vi trang cụ thể.
    """
    supabase = get_supabase()
    result = (
        supabase.table("book_chunks")
        .select("id, chunk_index, page_number, content")
        .eq("book_id", book_id)
        .gte("page_number", page_start)
        .lte("page_number", page_end)
        .order("chunk_index")
        .limit(20)
        .execute()
    )

    return [
        ChunkInfo(
            id=row["id"],
            chunk_index=row["chunk_index"],
            page_number=row.get("page_number"),
            content=row["content"],
        )
        for row in (result.data or [])
    ]
