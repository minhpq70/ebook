"""
RAG Engine — Prompt Orchestration + LLM Call
- Xây dựng prompt theo task type
- Gọi OpenAI API với query + chunks (KHÔNG gửi toàn bộ sách)
- Streaming support
- Log query vào Supabase
"""
import time
from core.openai_client import get_openai
from core.supabase_client import get_supabase
from core.config import settings
from models.schemas import ChunkInfo, RAGQueryResponse


# ============================================================
# System prompts theo task type (tiếng Việt)
# ============================================================
SYSTEM_PROMPTS = {
    "qa": """Bạn là trợ lý đọc sách thông minh, chuyên hỗ trợ độc giả hiểu nội dung sách.
Nhiệm vụ: Trả lời câu hỏi của người dùng DỰA TRÊN các đoạn trích từ sách được cung cấp.

Quy tắc quan trọng:
- Chỉ sử dụng thông tin trong các đoạn trích bên dưới để trả lời
- Nếu thông tin không có trong đoạn trích, hãy nói rõ "Thông tin này không có trong đoạn sách được trích dẫn"
- Trả lời bằng tiếng Việt, rõ ràng và dễ hiểu
- Có thể trích dẫn trực tiếp từ sách khi cần thiết
- NẾU người dùng yêu cầu "liệt kê" hoặc "đọc mục lục", BẮT BUỘC phải liệt kê đầy đủ toàn bộ chữ thấy được trong chunk mục lục, KHÔNG ĐƯỢC TÓM TẮT hay ẩn bớt.""",

    "explain": """Bạn là giáo viên/chuyên gia giải thích văn bản sâu sắc.
Nhiệm vụ: Giải thích đoạn văn khó hoặc khái niệm phức tạp trong sách cho người đọc hiểu.

Quy tắc:
- Giải thích dựa trên ngữ cảnh trong các đoạn trích
- Dùng ngôn ngữ đơn giản, dễ hiểu
- Có thể đưa ra ví dụ minh họa nếu phù hợp
- Trả lời bằng tiếng Việt""",

    "summarize_chapter": """Bạn là chuyên gia tóm tắt nội dung sách chuyên nghiệp.
Nhiệm vụ: Tóm tắt nội dung chương/phần sách dựa trên các đoạn trích được cung cấp.

Quy tắc:
- Tóm tắt ngắn gọn nhưng đầy đủ các ý chính
- Nêu bật các điểm quan trọng, luận điểm chính
- Trả lời bằng tiếng Việt với định dạng rõ ràng (có thể dùng bullet points)""",

    "summarize_book": """Bạn là chuyên gia phân tích và tóm tắt sách.
Nhiệm vụ: Cung cấp cái nhìn tổng quan về nội dung sách dựa trên các đoạn trích đại diện.

Lưu ý: Các đoạn trích chỉ là một phần của sách, hãy tóm tắt những gì có thể rút ra từ chúng.
Quy tắc:
- Tóm tắt chủ đề chính, luận điểm trung tâm
- Nêu các điểm nổi bật
- Trả lời bằng tiếng Việt""",

    "suggest": """Bạn là trợ lý gợi ý nội dung đọc sách.
Nhiệm vụ: Gợi ý các phần, chủ đề, hoặc nội dung liên quan trong sách mà người đọc có thể quan tâm.

Quy tắc:
- Dựa trên nội dung các đoạn trích, gợi ý các chủ đề liên quan
- Giải thích tại sao phần đó có thể thú vị với người đọc
- Trả lời bằng tiếng Việt""",
}


def _build_context_block(chunks: list[ChunkInfo]) -> str:
    """Xây dựng context block từ danh sách chunks."""
    parts = []
    for i, chunk in enumerate(chunks, 1):
        page_info = f" (Trang {chunk.page_number})" if chunk.page_number else ""
        parts.append(f"[Đoạn {i}{page_info}]\n{chunk.content}")
    return "\n\n---\n\n".join(parts)


def _build_user_message(query: str, context: str, task_type: str) -> str:
    """Xây dựng user message với query + context."""
    task_labels = {
        "qa": "Câu hỏi",
        "explain": "Yêu cầu giải thích",
        "summarize_chapter": "Yêu cầu tóm tắt chương",
        "summarize_book": "Yêu cầu tóm tắt sách",
        "suggest": "Yêu cầu gợi ý",
    }
    label = task_labels.get(task_type, "Yêu cầu")

    return f"""{label}: {query}

===== Đoạn trích từ sách =====
{context}
==============================

Hãy trả lời dựa trên các đoạn trích trên."""


async def run_rag_query(
    book_id: str,
    query: str,
    task_type: str,
    chunks: list[ChunkInfo],
) -> RAGQueryResponse:
    """
    Core RAG function:
    1. Xây dựng prompt từ query + chunks
    2. Gọi OpenAI (KHÔNG gửi toàn bộ sách)
    3. Log kết quả
    4. Trả về response có kèm source references
    """
    start_time = time.time()

    # Xây context từ chunks đã retrieve
    context = _build_context_block(chunks)
    system_prompt = SYSTEM_PROMPTS.get(task_type, SYSTEM_PROMPTS["qa"])
    user_message = _build_user_message(query, context, task_type)

    # Gọi OpenAI — chỉ gửi query + chunks, KHÔNG có toàn bộ sách
    client = get_openai()
    response = await client.chat.completions.create(
        model=settings.openai_chat_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        max_tokens=settings.openai_max_tokens,
        temperature=0.3,  # thấp để có câu trả lời ổn định, ít hallucinate
    )

    answer = response.choices[0].message.content or ""
    tokens_used = response.usage.total_tokens if response.usage else None
    latency_ms = int((time.time() - start_time) * 1000)

    # Log vào Supabase (async fire-and-forget)
    _log_query(
        book_id=book_id,
        query=query,
        task_type=task_type,
        chunks_count=len(chunks),
        response=answer,
        model=settings.openai_chat_model,
        tokens_used=tokens_used,
        latency_ms=latency_ms,
    )

    return RAGQueryResponse(
        query=query,
        task_type=task_type,
        answer=answer,
        sources=chunks,
        model=settings.openai_chat_model,
        tokens_used=tokens_used,
    )


def _log_query(
    book_id: str,
    query: str,
    task_type: str,
    chunks_count: int,
    response: str,
    model: str,
    tokens_used: int | None,
    latency_ms: int,
) -> None:
    """Ghi log query vào Supabase (sync, non-blocking)."""
    try:
        supabase = get_supabase()
        supabase.table("query_logs").insert({
            "book_id": book_id,
            "query": query,
            "task_type": task_type,
            "retrieved_chunks": chunks_count,
            "response": response[:2000],
            "model": model,
            "tokens_used": tokens_used,
            "latency_ms": latency_ms,
        }).execute()
    except Exception:
        pass


async def stream_rag_query(
    book_id: str,
    query: str,
    task_type: str,
    chunks: list[ChunkInfo],
):
    """
    Streaming RAG: yield SSE events dần dần thay vì chờ toàn bộ response.

    SSE Event format:
      data: {"type": "sources", "data": [...chunks...]}
      data: {"type": "token",   "data": " từng token"}
      data: {"type": "done",    "data": {"tokens_used": N}}
      data: [DONE]
    """
    import json

    start_time = time.time()

    context = _build_context_block(chunks)
    system_prompt = SYSTEM_PROMPTS.get(task_type, SYSTEM_PROMPTS["qa"])
    user_message = _build_user_message(query, context, task_type)

    # Gửi sources trước để frontend hiển thị ngay
    sources_payload = [
        {
            "id": c.id,
            "chunk_index": c.chunk_index,
            "page_number": c.page_number,
            "content": c.content,
            "score": c.score,
        }
        for c in chunks
    ]
    yield f"data: {json.dumps({'type': 'sources', 'data': sources_payload}, ensure_ascii=False)}\n\n"

    # Stream tokens từ OpenAI
    client = get_openai()
    full_answer = ""
    tokens_used = None

    stream = await client.chat.completions.create(
        model=settings.openai_chat_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        max_tokens=settings.openai_max_tokens,
        temperature=0.3,
        stream=True,
        stream_options={"include_usage": True},
    )

    async for chunk in stream:
        delta = chunk.choices[0].delta if chunk.choices else None
        if delta and delta.content:
            token = delta.content
            full_answer += token
            yield f"data: {json.dumps({'type': 'token', 'data': token}, ensure_ascii=False)}\n\n"

        # Lấy usage từ chunk cuối (OpenAI trả về ở chunk cuối cùng)
        if chunk.usage:
            tokens_used = chunk.usage.total_tokens

    latency_ms = int((time.time() - start_time) * 1000)

    # Gửi event done
    yield f"data: {json.dumps({'type': 'done', 'data': {'tokens_used': tokens_used, 'latency_ms': latency_ms}})}\n\n"
    yield "data: [DONE]\n\n"

    # Log vào Supabase
    _log_query(
        book_id=book_id,
        query=query,
        task_type=task_type,
        chunks_count=len(chunks),
        response=full_answer,
        model=settings.openai_chat_model,
        tokens_used=tokens_used,
        latency_ms=latency_ms,
    )

