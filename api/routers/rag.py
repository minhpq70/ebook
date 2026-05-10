"""
RAG Router
- POST /rag/query        — Hỏi đáp (blocking, đầy đủ response)
- POST /rag/query/stream — Hỏi đáp (SSE streaming, text xuất hiện dần)
"""
import asyncio
import json
import logging
import time
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

from models.schemas import RAGQueryRequest, RAGQueryResponse
from services import ingestion, retrieval, rag_engine
from services.metrics_registry import get_metrics_registry
from services.sheets_logger import log_query as sheets_log
from services.rag_engine import is_toc_query, is_book_meta_query, detect_task_type

router = APIRouter(prefix="/rag", tags=["RAG"])
VALID_TASK_TYPES = {"qa", "explain", "summarize_chapter", "summarize_book", "suggest", "auto"}
query_logger = logging.getLogger("rag.queries")

# Giá USD / 1 token (gpt-4o-mini, táng 4/2026)
_PRICE_INPUT  = 0.15 / 1_000_000   # $0.15 / 1M input tokens
_PRICE_OUTPUT = 0.60 / 1_000_000   # $0.60 / 1M output tokens

def _calc_cost(tokens_used: int | None) -> str:
    """Tính chi phí USD ước tính (giả sử 70% input / 30% output)."""
    if not tokens_used:
        return "n/a"
    cost = tokens_used * 0.7 * _PRICE_INPUT + tokens_used * 0.3 * _PRICE_OUTPUT
    return f"${cost:.6f}"



async def _get_validated_chunks(req: RAGQueryRequest):
    """Validate book + retrieve chunks — dùng chung cho cả 2 endpoints."""
    if req.task_type not in VALID_TASK_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"task_type không hợp lệ. Chọn: {', '.join(VALID_TASK_TYPES)}"
        )
    # Tự động nhận diện task type từ câu hỏi
    if req.task_type == "auto":
        req.task_type = detect_task_type(req.query)
    book = ingestion.get_book(req.book_id, source=req.source)
    if not book:
        raise HTTPException(status_code=404, detail="Không tìm thấy sách")
    if book.get("status") != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"Sách chưa sẵn sàng (status: {book.get('status')})"
        )

    # Resolve external_id → internal UUID (quan trọng!)
    # req.book_id có thể là "7" (external), nhưng DB cần UUID nội bộ
    internal_book_id = book["id"]
    req.book_id = internal_book_id

    # Tự động tăng top_k theo task type
    effective_top_k = req.top_k
    if is_toc_query(req.query):
        effective_top_k = max(effective_top_k or 5, 20)
    elif req.task_type == "summarize_chapter":
        effective_top_k = max(effective_top_k or 5, 15)
    elif req.task_type == "summarize_book":
        effective_top_k = max(effective_top_k or 5, 20)
    else:
        # Q&A: tối thiểu 8 (hybrid + keyword supplement sẽ thêm nữa)
        effective_top_k = max(effective_top_k or 5, 8)

    try:
        chunks = None
        force_meta_supplement = is_book_meta_query(req.query)

        # Khi hỏi mục lục: lấy trực tiếp các trang MỤC LỤC in sẵn trong sách
        if not chunks and is_toc_query(req.query):
            chunks = await retrieval.retrieve_toc_chunks(
                book_id=internal_book_id,
            )

        # Khi tóm tắt phần/chương cụ thể: dùng section sampling + TOC context
        if not chunks and req.task_type == "summarize_chapter":
            section_num = retrieval.detect_section_reference(req.query)
            if section_num is not None:
                # Lấy TOC chunks để LLM biết danh sách đầy đủ các bài viết trong phần
                toc_chunks = await retrieval.retrieve_toc_chunks(
                    book_id=internal_book_id,
                )
                # Lấy nội dung phân tán
                content_chunks = await retrieval.retrieve_chunks_for_section_summary(
                    book_id=internal_book_id,
                    section_number=section_num,
                    max_chunks=30,
                )
                if content_chunks:
                    # Ghép TOC (nếu có) + nội dung — TOC ở đầu để LLM thấy cấu trúc trước
                    if toc_chunks:
                        chunks = toc_chunks + content_chunks
                    else:
                        chunks = content_chunks

        # Fallback: hybrid search thông thường
        if not chunks:
            chunks = await retrieval.retrieve_chunks(
                book_id=internal_book_id,
                query=req.query,
                top_k=effective_top_k,
            )

            # Bổ sung context từ Lời giới thiệu/Lời NXB (trang 1-10)
            if chunks and req.task_type == "qa":
                intro_chunks = await retrieval.retrieve_book_meta_chunks(
                    book_id=internal_book_id,
                )
                if intro_chunks:
                    existing_ids = {c.id for c in chunks}
                    if force_meta_supplement:
                        # Câu hỏi đặc thù về metadata: thêm TẤT CẢ intro chunks
                        new_intro = [c for c in intro_chunks if c.id not in existing_ids]
                    else:
                        # Q&A thường: CHỈ thêm intro chunks LIÊN QUAN (tránh noise)
                        q_words = set(w for w in req.query.lower().split() if len(w) >= 3)
                        new_intro = []
                        for c in intro_chunks:
                            if c.id in existing_ids:
                                continue
                            overlap = sum(1 for w in q_words if w in c.content.lower())
                            if overlap >= 2:
                                new_intro.append(c)
                        new_intro = new_intro[:3]  # Max 3 cho Q&A thường
                    if new_intro:
                        chunks = new_intro + chunks

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi retrieval: {str(e)}")
    if not chunks:
        raise HTTPException(status_code=404, detail="Không tìm thấy nội dung liên quan")
    return chunks


@router.post("/query", response_model=RAGQueryResponse)
@limiter.limit("10/minute")
async def query_book(request: Request, req: RAGQueryRequest):
    """RAG query — blocking, trả về full response."""
    started_at = time.perf_counter()
    chunks = await _get_validated_chunks(req)
    try:
        result = await rag_engine.run_rag_query(
            book_id=req.book_id,
            query=req.query,
            task_type=req.task_type,
            chunks=chunks,
        )
        cost = _calc_cost(result.tokens_used)
        query_logger.info(
            "QUERY\tbook=%s\ttype=%s\ttokens=%s\tcost=%s\tq=%s",
            req.book_id, req.task_type,
            result.tokens_used, cost,
            req.query,
        )
        get_metrics_registry().record_query(
            task_type=req.task_type,
            latency_ms=(time.perf_counter() - started_at) * 1000,
            source_count=len(chunks),
        )
        # Ghi vào Google Sheets (bất đồng bộ, không block response)
        await sheets_log(
            mode="QUERY", book_id=req.book_id, task_type=req.task_type,
            query=req.query, tokens_used=result.tokens_used, cost_usd=cost,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi AI: {str(e)}")



@router.post("/query/stream")
@limiter.limit("10/minute")
async def query_book_stream(request: Request, req: RAGQueryRequest):
    """
    RAG query — SSE streaming.
    Text của AI xuất hiện dần (giống ChatGPT).
    """
    started_at = time.perf_counter()
    try:
        chunks = await _get_validated_chunks(req)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    async def generate():
        tokens_used = 0
        try:
            async for event in rag_engine.stream_rag_query(
                book_id=req.book_id,
                query=req.query,
                task_type=req.task_type,
                chunks=chunks,
            ):
                yield event
                
                # Bóc tách thông tin done để log
                if '"type": "done"' in event or '"type":"done"' in event:
                    try:
                        # event có dạng: data: {"type": "done", "data": {"tokens_used": 123...}} \n\n
                        json_str = event.replace("data: ", "").strip()
                        data_obj = json.loads(json_str)
                        if data_obj.get("data") and data_obj["data"].get("tokens_used"):
                            tokens_used = data_obj["data"]["tokens_used"]
                    except Exception:
                        pass
        except Exception as e:
            error_event = json.dumps({"type": "error", "data": str(e)})
            yield f"data: {error_event}\n\n"
        finally:
            # Khi stream xong, ghi log chính thức
            cost = _calc_cost(tokens_used) if tokens_used else 0.0
            get_metrics_registry().record_query(
                task_type=req.task_type,
                latency_ms=(time.perf_counter() - started_at) * 1000,
                source_count=len(chunks),
            )
            query_logger.info(
                "STREAM\tbook=%s\ttype=%s\ttokens=%s\tcost=%s\tq=%s",
                req.book_id, req.task_type, tokens_used, cost, req.query,
            )
            # Không được dùng await trong finally của sync generator nếu generate() bị drop sớm, 
            # nhưng FastAPI StreamingResponse support async generator safely closure.
            asyncio.create_task(sheets_log(
                mode="STREAM", book_id=req.book_id, task_type=req.task_type,
                query=req.query, tokens_used=tokens_used, cost_usd=cost,
            ))

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # tắt nginx buffering nếu có
        },
    )
