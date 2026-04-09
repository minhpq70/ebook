"""
Retrieval Service — Hybrid Search với Query Expansion + Reranking
Flow:
  1. Query expansion: sinh 2-3 paraphrases tiếng Việt
  2. Tính centroid embedding từ tất cả query variants
  3. Hybrid search (vector + FTS) với top_k * 3 candidates
  4. Semantic reranking để chọn top_k chunks chất lượng nhất
"""
from __future__ import annotations

from core.supabase_client import get_supabase
from core.config import settings
from models.schemas import ChunkInfo
from .embedding import embed_text, embed_batch
from .query_expander import expand_query, embed_expanded_queries
from .reranker import rerank_chunks


async def retrieve_chunks(
    book_id: str,
    query: str,
    top_k: int | None = None,
    use_query_expansion: bool = True,
) -> list[ChunkInfo]:
    """
    Improved retrieval pipeline:
    1. Query Expansion → tăng recall
    2. Centroid Embedding → embedding đại diện tốt hơn
    3. Hybrid Search với n_candidates lớn hơn → nhiều lựa chọn hơn
    4. Semantic Reranking → chọn đúng chunks nhất

    Args:
        book_id: UUID của sách
        query: Câu hỏi của người dùng
        top_k: Số chunks cuối cùng trả về
        use_query_expansion: Có expand query không (thêm ~0.5s latency)
    """
    k = top_k or settings.rag_top_k
    # Fetch nhiều candidates hơn để reranker có đủ dữ liệu
    n_candidates = k * 3

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

    # ── Bước 4: Semantic Reranking ───────────────────────────────
    reranked = await rerank_chunks(
        query=query,
        chunks=candidates,
        top_k=k,
        query_embedding=query_embedding,
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
