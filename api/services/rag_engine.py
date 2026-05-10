"""
RAG Engine — Prompt Orchestration + LLM Call
- Xây dựng prompt theo task type
- Gọi OpenAI API với query + chunks (KHÔNG gửi toàn bộ sách)
- Streaming support
- Log query vào Supabase
"""
from __future__ import annotations

import re
import time
import asyncio
import logging
from core.openai_client import get_openai, get_chat_openai
from core.supabase_client import get_supabase
from core.config import settings
from models.schemas import ChunkInfo, RAGQueryResponse
from services.metrics_registry import get_metrics_registry

logger = logging.getLogger("ebook.rag")


# ============================================================
# System prompts theo task type (tiếng Việt)
# ============================================================
# Các từ khoá nhận diện câu hỏi về mục lục
_TOC_KEYWORDS = [
    "mục lục", "table of contents", "danh mục", "danh sách chương",
    "liệt kê chương", "các phần", "các chương", "nội dung chính",
    "outline", "toc", "cấu trúc sách", "bố cục",
]

# Từ khoá nhận diện task type tự động
_EXPLAIN_KEYWORDS = ["giải thích", "explain", "nghĩa là gì", "có nghĩa", "hiểu thế nào", "ý nghĩa"]
_SUMMARIZE_BOOK_KEYWORDS = ["tóm tắt sách", "tóm tắt cuốn", "tổng quan sách", "nội dung chính của sách", "summarize book", "sách nói về"]
_SUMMARIZE_CHAPTER_KEYWORDS = ["tóm tắt chương", "tóm tắt phần", "summarize chapter", "nội dung chương"]
_SUGGEST_KEYWORDS = ["gợi ý", "đề xuất", "suggest", "nên đọc", "liên quan"]

# Từ khoá nhận diện câu hỏi về thông tin xuất bản/biên tập (metadata sách, thường ở trang 1-5)
# CHÚ Ý: chỉ dùng từ khoá ĐẶC THÙ cho metadata, tránh từ chung như "tác giả", "xuất bản"
_BOOK_META_KEYWORDS = [
    "biên tập nội dung", "biên tập viên", "tổng biên tập", "biên soạn",
    "trình bày bìa", "chế bản vi tính",
    "ai viết", "ai biên tập", "ai biên soạn",
    "nhà xuất bản nào", "nhà in", "in tại",
    "editor", "publisher", "ISBN",
]


def detect_task_type(query: str) -> str:
    """
    Tự động nhận diện task type từ câu hỏi của người dùng.
    Thứ tự ưu tiên: summarize_chapter > summarize_book > explain > suggest > qa
    """
    q = query.lower().strip()
    # Tóm tắt chương trước (vì "tóm tắt" xuất hiện trong cả 2)
    if any(kw in q for kw in _SUMMARIZE_CHAPTER_KEYWORDS):
        return "summarize_chapter"
    if any(kw in q for kw in _SUMMARIZE_BOOK_KEYWORDS):
        return "summarize_book"
    if any(kw in q for kw in _EXPLAIN_KEYWORDS):
        return "explain"
    if any(kw in q for kw in _SUGGEST_KEYWORDS):
        return "suggest"
    return "qa"


def is_toc_query(query: str) -> bool:
    """Phát hiện câu hỏi liên quan đến Mục lục."""
    q = query.lower().strip()
    return any(kw in q for kw in _TOC_KEYWORDS)


def is_book_meta_query(query: str) -> bool:
    """Phát hiện câu hỏi về thông tin xuất bản/biên tập (metadata sách ở trang đầu)."""
    q = query.lower().strip()
    return any(kw in q for kw in _BOOK_META_KEYWORDS)


_THINK_RE = re.compile(r"<thought>.*?</thought>", re.DOTALL)

def _strip_thinking(text: str) -> str:
    """Loại bỏ block <thought>...</thought> từ output của Gemma4 thinking model."""
    return _THINK_RE.sub("", text).strip()


SYSTEM_PROMPTS = {
    "qa": """Bạn là trợ lý đọc sách thông minh, chuyên hỗ trợ độc giả Việt Nam hiểu nội dung sách.
Nhiệm vụ: Trả lời câu hỏi của người dùng từ nội dung sách.

Quy tắc BẮT BUỘC:
- BẮT BUỘC trả lời bằng tiếng Việt có dấu đầy đủ, KHÔNG BAO GIỜ trả lời bằng tiếng Anh trừ khi người dùng yêu cầu
- Chỉ sử dụng thông tin trong các đoạn trích bên dưới để trả lời
- Nếu thông tin không có trong đoạn trích, hãy nói rõ "Thông tin này không có trong các đoạn sách được trích dẫn"
- Trả lời rõ ràng, dễ hiểu, sử dụng markdown (bullet points, heading) cho dễ đọc
- KHÔNG BAO GIỜ mở đầu câu trả lời bằng các cụm như "Dựa trên các đoạn trích được cung cấp", "Theo các đoạn trích", "Từ nội dung được cung cấp". Trả lời TRỰC TIẾP vào nội dung ngay lập tức
- KHÔNG BAO GIỜ nhắc đến "đoạn 1", "đoạn 2", "đoạn trích số X", "theo đoạn trích" hay bất kỳ tham chiếu nội bộ nào. Trả lời như thể bạn đã đọc toàn bộ cuốn sách

Quy tắc SỬA LỖI OCR (QUAN TRỌNG NHẤT):
- Nội dung sách được trích xuất bằng OCR nên CÓ THỂ chứa lỗi chính tả, ký tự sai, dấu thiếu
- Khi trả lời, THẦM LẶNG sửa lỗi chính tả tiếng Việt cho đúng ngữ cảnh — KHÔNG BAO GIỜ giải thích hay ghi chú quá trình sửa lỗi
- VÍ DỤ: "haåt giöëng têm höìn" → sửa thành "hạt giống tâm hồn" (KHÔNG ghi chú gì thêm)
- GIỮ ĐÚNG ý nghĩa gốc, chỉ sửa chính tả — KHÔNG thay đổi nội dung hay thêm bớt thông tin
- Nếu một đoạn bị lỗi OCR quá nặng không thể đọc được, BỎ QUA đoạn đó và dùng thông tin từ các đoạn trích khác
- TUYỆT ĐỐI KHÔNG đoán hoặc suy diễn nội dung từ đoạn bị lỗi — chỉ dùng thông tin đọc được rõ ràng
- KHÔNG BAO GIỜ viết các cụm như "[nguyên văn]", "[sửa lỗi OCR]", "(đã sửa)", "(tiêu đề được phục hồi từ...)" trong câu trả lời

Quy tắc ĐẶC BIỆT về Mục lục:
- NẾU người dùng hỏi về "mục lục", "danh sách chương", "liệt kê nội dung":
  + BẮT BUỘC liệt kê TOÀN BỘ các mục từ đầu đến cuối, kèm số trang nếu có
  + KHÔNG ĐƯỢC tóm tắt, rút gọn, hay viết "và còn nhiều mục khác..."
  + KHÔNG ĐƯỢC giới hạn số mục hiển thị, phải ghi đầy đủ 100%
  + Sửa lỗi chính tả OCR cho tiêu đề các mục
  + ĐỊNH DẠNG BẮT BUỘC: Mỗi mục PHẢI trên một dòng riêng biệt. Dùng dấu gạch đầu dòng (-) cho mỗi mục. Tiêu đề phần (PHẦN I, PHẦN II...) dùng heading markdown (###). Số trang ghi ở cuối dòng.
  + VÍ DỤ ĐỊNH DẠNG ĐÚNG:

### PHẦN I: Tiêu đề phần 1

- Tên bài viết thứ nhất *(trang 7)*
- Tên bài viết thứ hai *(trang 15)*
- Tên bài viết thứ ba *(trang 23)*

### PHẦN II: Tiêu đề phần 2

- Tên bài viết thứ nhất *(trang 141)*""",

    "explain": """Bạn là giáo viên/chuyên gia giải thích văn bản sâu sắc.
Nhiệm vụ: Giải thích đoạn văn khó hoặc khái niệm phức tạp trong sách cho người đọc hiểu.

Quy tắc:
- CHỈ giải thích dựa trên ngữ cảnh trong các đoạn trích từ sách — KHÔNG ĐƯỢC sử dụng kiến thức bên ngoài
- Nếu khái niệm không được giải thích trong đoạn trích, nói rõ "Khái niệm này không được giải thích chi tiết trong các đoạn sách được trích dẫn"
- Dùng ngôn ngữ đơn giản, dễ hiểu
- Có thể đưa ra ví dụ minh họa NẾU ví dụ đó có trong đoạn trích
- Trả lời bằng tiếng Việt
- Nội dung sách được trích xuất bằng OCR, CÓ THỂ chứa lỗi chính tả — thầm lặng sửa cho đúng khi trả lời, KHÔNG giải thích quá trình sửa lỗi
- KHÔNG mở đầu bằng "Dựa trên các đoạn trích", "Theo các đoạn trích". Trả lời TRỰC TIẾP vào nội dung
- KHÔNG BAO GIỜ nhắc đến "đoạn 1", "đoạn 2", "đoạn trích số X" hay bất kỳ tham chiếu nội bộ nào. Trả lời tự nhiên như đang giảng bài""",

    "summarize_chapter": """Bạn là chuyên gia tóm tắt nội dung sách chuyên nghiệp.
Nhiệm vụ: Tóm tắt nội dung chương/phần sách.

Quy tắc:
- Tóm tắt đầy đủ, bao phủ TẤT CẢ các bài viết/mục trong phần được yêu cầu
- Nêu bật các điểm quan trọng, luận điểm chính của từng bài viết
- Trả lời bằng tiếng Việt với định dạng rõ ràng, dùng heading (###) và bullet points
- Thầm lặng sửa lỗi chính tả OCR — KHÔNG giải thích quá trình sửa lỗi
- Khi xác định tiêu đề: ĐỐI CHIẾU nhiều đoạn trích để tìm tiêu đề CHÍNH XÁC
- KHÔNG BAO GIỜ tự suy đoán tiêu đề từ đoạn bị lỗi OCR nặng
- KHÔNG BAO GIỜ viết ghi chú dạng "(tiêu đề được phục hồi từ...)", "[nguyên văn]"
- KHÔNG mở đầu bằng "Dựa trên các đoạn trích". Trả lời TRỰC TIẾP vào nội dung

Quy tắc ĐẶC BIỆT về cấu trúc tóm tắt:
- Nếu trong đoạn trích có phần MỤC LỤC, hãy dùng nó làm KHUNG CẤU TRÚC cho bài tóm tắt
- Với MỖI bài viết/mục được liệt kê trong mục lục của phần đó, phải có ÍT NHẤT 1-2 câu tóm tắt
- Nếu không có đoạn trích nội dung cho một bài viết cụ thể, vẫn liệt kê tiêu đề bài viết đó và ghi "nội dung chi tiết trong sách"
- Sắp xếp tóm tắt theo đúng thứ tự các bài viết trong mục lục""",

    "summarize_book": """Bạn là chuyên gia phân tích và tóm tắt sách.
Nhiệm vụ: Cung cấp cái nhìn tổng quan về nội dung sách.

Lưu ý: Các đoạn trích chỉ là một phần của sách, hãy tóm tắt những gì có thể rút ra từ chúng.
Quy tắc:
- Tóm tắt chủ đề chính, luận điểm trung tâm
- Nêu các điểm nổi bật
- Trả lời bằng tiếng Việt
- Thầm lặng sửa lỗi chính tả OCR khi trích dẫn — KHÔNG giải thích quá trình sửa lỗi
- Nếu đoạn trích bị lỗi OCR nặng không đọc được, bỏ qua và dùng thông tin từ các đoạn khác
- KHÔNG mở đầu bằng "Dựa trên các đoạn trích". Trả lời TRỰC TIẾP vào nội dung""",

    "suggest": """Bạn là trợ lý gợi ý nội dung đọc sách.
Nhiệm vụ: Gợi ý các phần, chủ đề, hoặc nội dung liên quan trong sách mà người đọc có thể quan tâm.

Quy tắc:
- Dựa trên nội dung các đoạn trích, gợi ý các chủ đề liên quan
- Giải thích tại sao phần đó có thể thú vị với người đọc
- Trả lời bằng tiếng Việt
- Thầm lặng sửa lỗi chính tả OCR khi trích dẫn — KHÔNG giải thích quá trình sửa lỗi
- KHÔNG mở đầu bằng "Dựa trên các đoạn trích". Trả lời TRỰC TIẾP vào nội dung""",
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

    # Tự động tăng max_tokens cho câu hỏi mục lục và tóm tắt (cần output dài)
    max_tokens = settings.openai_max_tokens
    is_toc = is_toc_query(query)
    if is_toc:
        max_tokens = max(max_tokens, 12000)
    elif task_type in ("summarize_chapter", "summarize_book"):
        max_tokens = max(max_tokens, 8000)

    # Temperature = 0 cho mục lục (sao chép nguyên văn), 0.2 cho câu hỏi thường
    temperature = 0.0 if is_toc else 0.2

    # Gọi OpenAI (Hoặc Local LLM) — chỉ gửi query + chunks, KHÔNG có toàn bộ sách
    client = get_chat_openai()
    response = await client.chat.completions.create(
        model=settings.openai_chat_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        max_tokens=max_tokens,
        temperature=temperature,  # 0 cho mục lục (chống hallucination), 0.2 cho Q&A
    )

    raw_answer = response.choices[0].message.content or ""
    answer = _strip_thinking(raw_answer)
    tokens_used = response.usage.total_tokens if response.usage else None
    latency_ms = int((time.time() - start_time) * 1000)
    get_metrics_registry().record_rag_latency(latency_ms, tokens_used)

    # Log vào Supabase (async fire-and-forget qua thread)
    asyncio.create_task(asyncio.to_thread(
        _log_query,
        book_id=book_id,
        query=query,
        task_type=task_type,
        chunks_count=len(chunks),
        response=answer,
        model=settings.openai_chat_model,
        tokens_used=tokens_used,
        latency_ms=latency_ms,
    ))

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
    except Exception as e:
        logger.warning("Lỗi ghi query log vào Supabase: %s", e)


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

    # Tự động tăng max_tokens theo task type
    max_tokens = settings.openai_max_tokens
    is_toc = is_toc_query(query)
    if is_toc:
        max_tokens = max(max_tokens, 12000)
    elif task_type in ("summarize_chapter", "summarize_book"):
        max_tokens = max(max_tokens, 8000)
    elif task_type == "explain":
        max_tokens = max(max_tokens, 8000)
    else:
        # Q&A thông thường: tối thiểu 6000 để tránh bị cắt
        max_tokens = max(max_tokens, 6000)

    # Temperature = 0 cho mục lục (sao chép nguyên văn), 0.2 cho câu hỏi thường
    temperature = 0.0 if is_toc else 0.2

    # Stream tokens từ OpenAI (Hoặc Local LLM)
    client = get_chat_openai()
    full_answer = ""
    tokens_used = None
    _in_thinking = False  # Track nếu đang trong block <thought>

    stream = await client.chat.completions.create(
        model=settings.openai_chat_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
        stream=True,
        stream_options={"include_usage": True},
    )

    async for chunk in stream:
        delta = chunk.choices[0].delta if chunk.choices else None
        if delta and delta.content:
            token = delta.content
            full_answer += token

            # Lọc bỏ nội dung <thought>...</thought> khi streaming
            if "<thought>" in token:
                _in_thinking = True
                # Giữ lại phần trước <thought> nếu có
                before = token.split("<thought>")[0]
                if before.strip():
                    yield f"data: {json.dumps({'type': 'token', 'data': before}, ensure_ascii=False)}\n\n"
                continue
            if _in_thinking:
                if "</thought>" in token:
                    _in_thinking = False
                    # Giữ lại phần sau </thought> (đầu câu trả lời thực)
                    after = token.split("</thought>", 1)[-1]
                    if after.strip():
                        yield f"data: {json.dumps({'type': 'token', 'data': after}, ensure_ascii=False)}\n\n"
                continue  # Bỏ qua token thinking

            yield f"data: {json.dumps({'type': 'token', 'data': token}, ensure_ascii=False)}\n\n"

        # Lấy usage từ chunk cuối (OpenAI trả về ở chunk cuối cùng)
        if chunk.usage:
            tokens_used = chunk.usage.total_tokens

    latency_ms = int((time.time() - start_time) * 1000)
    get_metrics_registry().record_rag_latency(latency_ms, tokens_used)

    # Gửi event done
    yield f"data: {json.dumps({'type': 'done', 'data': {'tokens_used': tokens_used, 'latency_ms': latency_ms}})}\n\n"
    yield "data: [DONE]\n\n"

    # Log vào Supabase qua thread ngầm để không chặn
    asyncio.create_task(asyncio.to_thread(
        _log_query,
        book_id=book_id,
        query=query,
        task_type=task_type,
        chunks_count=len(chunks),
        response=full_answer,
        model=settings.openai_chat_model,
        tokens_used=tokens_used,
        latency_ms=latency_ms,
    ))
