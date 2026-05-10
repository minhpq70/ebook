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
    use_query_expansion: bool = False,
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

    # Generate cache key (includes top_k to avoid stale results)
    query_hash = hashlib.md5(f"{query}:{use_query_expansion}:{k}".encode()).hexdigest()[:16]

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

    # ── Bước 4: Semantic Reranking (Lược bỏ để tăng tốc) ──────────
    # Thay vì gọi API nhúng lại toàn bộ chunk (tốn thời gian), ta tin tưởng vào 
    # điểm số trả về từ hybrid_search của Supabase pgvector
    reranked = candidates[:k]
    reranked = await _expand_context_neighbors(book_id, reranked, k)

    # ── Bước 5: Bổ sung keyword match trực tiếp ──────────────────
    # Hybrid search đôi khi miss chunks chứa CHÍNH XÁC cụm từ trong câu hỏi
    # (do embedding similarity ưu tiên chunks ở chỗ khác). Bổ sung bằng ILIKE.
    keyword_chunks = await _keyword_supplement(book_id, query, reranked)
    if keyword_chunks:
        reranked = keyword_chunks + reranked

    # Cache the result
    result_dicts = [chunk.dict() for chunk in reranked]
    await cache_manager.set_query_result(query_hash, book_id, result_dicts)
    metrics.record_retrieval(
        latency_ms=(time.perf_counter() - started_at) * 1000,
        candidate_count=len(candidates),
    )

    return reranked


import re as _re_retrieval


async def _keyword_supplement(
    book_id: str,
    query: str,
    existing_chunks: list[ChunkInfo],
    max_supplement: int = 5,
) -> list[ChunkInfo]:
    """
    Bổ sung chunks chứa CHÍNH XÁC cụm từ quan trọng từ câu hỏi.
    Hybrid search đôi khi miss do embedding similarity ưu tiên sai.
    
    Chiến lược:
    1. Trích xuất cụm từ dài (≥4 ký tự, loại bỏ stopwords) từ query
    2. ILIKE search trong book_chunks
    3. De-duplicate với kết quả hybrid search
    4. Trả về max_supplement chunks mới
    """
    # ƯU TIÊN 1: Trích xuất text trong dấu nháy (tiêu đề bài viết)
    import re as _re_quoted
    quoted_phrases = []
    for q in _re_quoted.findall(r'["“]([^"”]{8,})["”]', query):
        cq = _re_quoted.sub(r'[,.]', '', q).strip()
        if len(cq) >= 8:
            quoted_phrases.append(cq)

    # Loại bỏ dấu câu
    q_clean = _re_quoted.sub(r'[?!.,;:()\[\]{}"“”\']+', '', query).strip()
    if len(q_clean) < 8 and not quoted_phrases:
        return []

    # Tìm chunks chứa cụm từ dài nhất từ query
    existing_ids = {c.id for c in existing_chunks}
    supabase = get_supabase()

    # Xây dựng search phrases (ưu tiên giảm dần)
    search_phrases = list(quoted_phrases)  # Quoted text ưu tiên nhất

    # ƯU TIÊN 2: Toàn bộ query (trừ prefix)
    q_trimmed = _re_quoted.sub(
        r'^(hãy|cho biết|liệt kê|nêu|là gì|những|các|theo|tóm tắt bài|tóm tắt|nội dung bài|nội dung)\s+',
        '', q_clean, flags=_re_quoted.IGNORECASE,
    ).strip()
    if len(q_trimmed) >= 8 and q_trimmed not in search_phrases:
        search_phrases.append(q_trimmed)

    # ƯU TIÊN 3: cụm 6 từ liên tiếp
    words = q_clean.split()
    if len(words) >= 6:
        for start in range(len(words) - 5):
            phrase = ' '.join(words[start:start+6])
            if len(phrase) >= 20:
                search_phrases.append(phrase)

    new_chunks: list[ChunkInfo] = []
    seen_ids = set(existing_ids)

    for phrase in search_phrases:
        if len(new_chunks) >= max_supplement:
            break
        try:
            result = (
                supabase.table("book_chunks")
                .select("id, chunk_index, page_number, content")
                .eq("book_id", book_id)
                .ilike("content", f"%{phrase}%")
                .order("chunk_index")
                .limit(max_supplement)
                .execute()
            )
            for row in (result.data or []):
                # Bỏ qua chunks ở vùng mục lục (thường ở cuối sách, page > tổng trang - 20)
                if row.get("page_number") and row["page_number"] > 500:
                    continue
                if row["id"] not in seen_ids and len(new_chunks) < max_supplement:
                    seen_ids.add(row["id"])
                    new_chunks.append(ChunkInfo(
                        id=row["id"],
                        chunk_index=row["chunk_index"],
                        page_number=row.get("page_number"),
                        content=row["content"],
                    ))
                    # Section expansion: nếu chunk chứa TIÊU ĐỀ IN HOA
                    # (dấu hiệu đầu bài viết), lấy thêm 8 chunks liên tiếp sau
                    content_upper = row["content"][:200]
                    has_title = any(
                        line.strip() == line.strip().upper() and len(line.strip()) > 15
                        for line in content_upper.split('\n')
                        if line.strip()
                    )
                    if has_title:
                        expand_result = (
                            supabase.table("book_chunks")
                            .select("id, chunk_index, page_number, content")
                            .eq("book_id", book_id)
                            .gt("chunk_index", row["chunk_index"])
                            .order("chunk_index")
                            .limit(8)
                            .execute()
                        )
                        for er in (expand_result.data or []):
                            if er["id"] not in seen_ids:
                                seen_ids.add(er["id"])
                                new_chunks.append(ChunkInfo(
                                    id=er["id"],
                                    chunk_index=er["chunk_index"],
                                    page_number=er.get("page_number"),
                                    content=er["content"],
                                ))
        except Exception:
            continue  # ILIKE failure is non-critical

    return new_chunks

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


async def retrieve_book_meta_chunks(book_id: str) -> list[ChunkInfo]:
    """
    Lấy chunks từ 10 trang đầu sách — nơi chứa thông tin xuất bản,
    biên tập, tác giả, nhà in, ISBN, v.v.
    """
    supabase = get_supabase()
    result = (
        supabase.table("book_chunks")
        .select("id, chunk_index, page_number, content")
        .eq("book_id", book_id)
        .gte("page_number", 1)
        .lte("page_number", 10)
        .order("chunk_index")
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


import re as _re
import logging as _logging

_section_logger = _logging.getLogger("ebook.retrieval.section")

# Map Roman numerals → Arabic
_ROMAN_MAP = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8}
_ROMAN_REVERSE = {v: k for k, v in _ROMAN_MAP.items()}

# Regex nhận diện "phần 1", "phần I", "part 1", "chương 2", "chapter 3"
_SECTION_RE = _re.compile(
    r"(?:phần|part|chương|chapter)\s+(\d+|[IVX]+)",
    _re.IGNORECASE,
)


def detect_section_reference(query: str) -> int | None:
    """
    Phát hiện tham chiếu đến phần/chương từ câu hỏi.
    Trả về số thứ tự phần (1-based) hoặc None nếu không tìm thấy.
    Ví dụ: 'tóm tắt phần 1' → 1, 'tóm tắt phần III' → 3
    """
    m = _SECTION_RE.search(query)
    if not m:
        return None
    raw = m.group(1).strip().upper()
    if raw.isdigit():
        return int(raw)
    return _ROMAN_MAP.get(raw)


async def find_section_page_range(
    book_id: str,
    section_number: int,
) -> tuple[int, int] | None:
    """
    Tìm phạm vi trang [start, end] của phần/chương trong sách.
    Sử dụng chiến lược multi-batch để bypass Supabase 1000-row limit:
    - Scan qua chunks theo batch (mỗi batch 1000 rows)
    - Tìm header "Phần I", "Phần II", v.v.
    Trả về (page_start, page_end) hoặc None nếu không tìm thấy.
    """
    supabase = get_supabase()

    # Lấy tổng số trang
    book_res = supabase.table("books").select("total_pages").eq("id", book_id).execute()
    total_pages = (book_res.data[0].get("total_pages") or 0) if book_res.data else 0

    # Scan qua tất cả chunks theo batch để tìm section headers
    section_starts: dict[int, int] = {}  # section_number → page_number
    batch_size = 1000
    offset = 0

    while True:
        result = (
            supabase.table("book_chunks")
            .select("chunk_index, page_number, content")
            .eq("book_id", book_id)
            .order("chunk_index")
            .range(offset, offset + batch_size - 1)
            .execute()
        )
        chunks = result.data or []
        if not chunks:
            break

        for c in chunks:
            content = c["content"].strip()[:100]
            m = _re.match(r"Phần\s+([IVX]+|\d+)\b", content)
            if m:
                raw = m.group(1).strip().upper()
                if raw.isdigit():
                    sec_num = int(raw)
                else:
                    sec_num = _ROMAN_MAP.get(raw)
                if sec_num and sec_num not in section_starts:
                    section_starts[sec_num] = c["page_number"]

        if len(chunks) < batch_size:
            break  # Đã hết dữ liệu
        offset += batch_size

    if section_number not in section_starts:
        _section_logger.warning(
            "Không tìm thấy Phần %d trong sách %s. Các phần tìm được: %s",
            section_number, book_id, section_starts,
        )
        return None

    page_start = section_starts[section_number]

    # page_end = trang bắt đầu của phần tiếp theo - 1, hoặc trang cuối sách
    next_sections = sorted(s for s in section_starts if s > section_number)
    if next_sections:
        page_end = section_starts[next_sections[0]] - 1
    else:
        # Phần cuối cùng → lấy đến trang cuối sách
        page_end = total_pages if total_pages > 0 else page_start + 100

    _section_logger.info(
        "Phần %d: pages %d-%d (sách %s)", section_number, page_start, page_end, book_id,
    )
    return (page_start, page_end)


async def retrieve_chunks_for_section_summary(
    book_id: str,
    section_number: int,
    max_chunks: int = 25,
) -> list[ChunkInfo] | None:
    """
    Lấy mẫu phân tán (distributed sampling) chunks trên toàn bộ phạm vi
    của một phần/chương sách để đảm bảo tóm tắt bao phủ mọi chủ đề.

    Chiến lược:
    1. Tìm page range của section
    2. Lấy tất cả chunks trong range
    3. Lấy mẫu đều: chia đều thành max_chunks lát, lấy 1 chunk/lát
    4. Ưu tiên chunk dài (nhiều nội dung hơn) trong mỗi lát

    Returns None nếu không tìm thấy section.
    """
    page_range = await find_section_page_range(book_id, section_number)
    if not page_range:
        return None

    page_start, page_end = page_range

    supabase = get_supabase()
    result = (
        supabase.table("book_chunks")
        .select("id, chunk_index, page_number, content")
        .eq("book_id", book_id)
        .gte("page_number", page_start)
        .lte("page_number", page_end)
        .order("chunk_index")
        .execute()
    )

    all_chunks = result.data or []
    if not all_chunks:
        return None

    _section_logger.info(
        "Phần %d: %d chunks trong pages %d-%d, sampling %d",
        section_number, len(all_chunks), page_start, page_end, max_chunks,
    )

    if len(all_chunks) <= max_chunks:
        # Ít chunks → lấy tất cả
        return [
            ChunkInfo(
                id=row["id"],
                chunk_index=row["chunk_index"],
                page_number=row.get("page_number"),
                content=row["content"],
            )
            for row in all_chunks
        ]

    # Distributed sampling: chia thành max_chunks lát, lấy chunk dài nhất mỗi lát
    step = len(all_chunks) / max_chunks
    sampled: list[ChunkInfo] = []
    for i in range(max_chunks):
        start_idx = int(i * step)
        end_idx = int((i + 1) * step)
        slice_chunks = all_chunks[start_idx:end_idx]
        if not slice_chunks:
            continue
        # Chọn chunk dài nhất trong lát (nhiều nội dung nhất)
        best = max(slice_chunks, key=lambda c: len(c["content"]))
        sampled.append(ChunkInfo(
            id=best["id"],
            chunk_index=best["chunk_index"],
            page_number=best.get("page_number"),
            content=best["content"],
        ))

    return sampled


async def retrieve_toc_chunks(book_id: str) -> list[ChunkInfo] | None:
    """
    Tìm và trả về TẤT CẢ chunks thuộc phần Mục lục (MỤC LỤC) của sách.

    Chiến lược (bypass Supabase 1000-row limit):
    1. Lấy total_pages từ books table
    2. Query chỉ các chunks ở ~20 trang cuối (nơi MỤC LỤC thường nằm)
    3. Scan tìm "MỤC LỤC" keyword, xác định phạm vi chính xác
    4. Trả về tất cả chunks trong phạm vi đó

    Returns None nếu không tìm thấy phần mục lục.
    """
    supabase = get_supabase()

    # Bước 1: Lấy tổng số trang
    book_res = supabase.table("books").select("total_pages").eq("id", book_id).execute()
    total_pages = (book_res.data[0].get("total_pages") or 0) if book_res.data else 0
    if total_pages == 0:
        # Fallback: tìm page cao nhất từ chunks
        max_page_res = (
            supabase.table("book_chunks")
            .select("page_number")
            .eq("book_id", book_id)
            .order("page_number", desc=True)
            .limit(1)
            .execute()
        )
        total_pages = max_page_res.data[0]["page_number"] if max_page_res.data else 0
    if total_pages == 0:
        return None

    # Bước 2: Lấy chunks ở 20 trang cuối (đủ rộng cho mục lục 5-10 trang)
    tail_start = max(1, total_pages - 20)
    tail_res = (
        supabase.table("book_chunks")
        .select("id, chunk_index, page_number, content")
        .eq("book_id", book_id)
        .gte("page_number", tail_start)
        .order("chunk_index")
        .execute()
    )
    tail_chunks = tail_res.data or []

    # Bước 3: Tìm chunks chứa "MỤC LỤC"
    toc_pages: set[int] = set()
    for c in tail_chunks:
        if "MỤC LỤC" in c["content"].upper() and c["page_number"] > 0:
            toc_pages.add(c["page_number"])

    # Cũng kiểm tra phần đầu sách (một số sách có mục lục ở đầu)
    if not toc_pages:
        head_res = (
            supabase.table("book_chunks")
            .select("id, chunk_index, page_number, content")
            .eq("book_id", book_id)
            .lte("page_number", 20)
            .order("chunk_index")
            .execute()
        )
        for c in (head_res.data or []):
            if "MỤC LỤC" in c["content"].upper() and c["page_number"] > 0:
                toc_pages.add(c["page_number"])
        if toc_pages:
            tail_chunks = head_res.data or []

    if not toc_pages:
        _section_logger.info("Không tìm thấy trang MỤC LỤC trong sách %s", book_id)
        return None

    # Bước 4: Mở rộng phạm vi và lấy tất cả chunks trong đó
    page_start = min(toc_pages)
    page_end = max(toc_pages) + 1  # +1 để bao phủ trang cuối

    _section_logger.info(
        "Tìm thấy MỤC LỤC tại pages %d-%d, sách %s",
        page_start, page_end, book_id,
    )

    # Query chính xác phạm vi trang mục lục
    toc_res = (
        supabase.table("book_chunks")
        .select("id, chunk_index, page_number, content")
        .eq("book_id", book_id)
        .gte("page_number", page_start)
        .lte("page_number", page_end)
        .order("chunk_index")
        .execute()
    )

    toc_chunks = [
        ChunkInfo(
            id=c["id"],
            chunk_index=c["chunk_index"],
            page_number=c["page_number"],
            content=c["content"],
        )
        for c in (toc_res.data or [])
    ]

    _section_logger.info(
        "Trả về %d TOC chunks (pages %d-%d)", len(toc_chunks), page_start, page_end,
    )
    return toc_chunks if toc_chunks else None


