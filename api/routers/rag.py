"""
RAG Router
- POST /rag/query        — Hỏi đáp (blocking, đầy đủ response)
- POST /rag/query/stream — Hỏi đáp (SSE streaming, text xuất hiện dần)
"""
import asyncio
import json
import logging
import time
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

from models.schemas import RAGQueryRequest, RAGQueryResponse
from services import ingestion, retrieval, rag_engine
from services.metrics_registry import get_metrics_registry
from services.sheets_logger import log_query as sheets_log
from services.rag_engine import is_toc_query

router = APIRouter(prefix="/rag", tags=["RAG"])
VALID_TASK_TYPES = {"qa", "explain", "summarize_chapter", "summarize_book", "suggest"}
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
    book = ingestion.get_book(req.book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Không tìm thấy sách")
    if book.get("status") != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"Sách chưa sẵn sàng (status: {book.get('status')})"
        )

    # Tự động tăng top_k khi hỏi mục lục / TOC
    effective_top_k = req.top_k
    if is_toc_query(req.query):
        effective_top_k = max(effective_top_k or 5, 20)

    try:
        chunks = await retrieval.retrieve_chunks(
            book_id=req.book_id,
            query=req.query,
            top_k=effective_top_k,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi retrieval: {str(e)}")
    if not chunks:
        raise HTTPException(status_code=404, detail="Không tìm thấy nội dung liên quan")
    return chunks


@router.post("/query", response_model=RAGQueryResponse)
@limiter.limit("10/minute")
async def query_book(req: RAGQueryRequest):
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
async def query_book_stream(req: RAGQueryRequest):
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
