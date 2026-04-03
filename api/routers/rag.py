"""
RAG Router
- POST /rag/query        — Hỏi đáp (blocking, đầy đủ response)
- POST /rag/query/stream — Hỏi đáp (SSE streaming, text xuất hiện dần)
"""
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from models.schemas import RAGQueryRequest, RAGQueryResponse
from services import ingestion, retrieval, rag_engine

router = APIRouter(prefix="/rag", tags=["RAG"])
VALID_TASK_TYPES = {"qa", "explain", "summarize_chapter", "summarize_book", "suggest"}


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
    try:
        chunks = await retrieval.retrieve_chunks(
            book_id=req.book_id,
            query=req.query,
            top_k=req.top_k,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi retrieval: {str(e)}")
    if not chunks:
        raise HTTPException(status_code=404, detail="Không tìm thấy nội dung liên quan")
    return chunks


@router.post("/query", response_model=RAGQueryResponse)
async def query_book(req: RAGQueryRequest):
    """RAG query — blocking, trả về full response."""
    chunks = await _get_validated_chunks(req)
    try:
        return await rag_engine.run_rag_query(
            book_id=req.book_id,
            query=req.query,
            task_type=req.task_type,
            chunks=chunks,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi AI: {str(e)}")


@router.post("/query/stream")
async def query_book_stream(req: RAGQueryRequest):
    """
    RAG query — SSE streaming.
    Text của AI xuất hiện dần (giống ChatGPT).

    Events:
      data: {"type":"sources","data":[...]}   ← chunks retrieved
      data: {"type":"token","data":" text"}   ← mỗi token
      data: {"type":"done","data":{...}}      ← kết thúc
      data: [DONE]
    """
    chunks = await _get_validated_chunks(req)

    async def generate():
        try:
            async for event in rag_engine.stream_rag_query(
                book_id=req.book_id,
                query=req.query,
                task_type=req.task_type,
                chunks=chunks,
            ):
                yield event
        except Exception as e:
            error_event = json.dumps({"type": "error", "data": str(e)})
            yield f"data: {error_event}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # tắt nginx buffering nếu có
        },
    )
