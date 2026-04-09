"""
Query Expansion Service
- Sinh 2-3 paraphrase tiếng Việt của câu query gốc
- Giúp tăng recall khi tìm kiếm (cùng ý nhưng cách diễn đạt khác)
- Dùng OpenAI GPT-4o-mini (nhanh + rẻ)
"""
from core.openai_client import get_openai
from core.config import settings


EXPAND_SYSTEM_PROMPT = """Bạn là chuyên gia ngôn ngữ tiếng Việt. 
Nhiệm vụ: Tạo các cách diễn đạt khác nhau cho câu hỏi/yêu cầu được cung cấp.

Quy tắc:
- Giữ nguyên ý nghĩa gốc, chỉ thay đổi cách diễn đạt
- Dùng từ đồng nghĩa, cấu trúc câu khác
- Mỗi dòng là 1 paraphrase, KHÔNG đánh số, KHÔNG giải thích
- Chỉ trả về đúng 2 dòng"""


async def expand_query(query: str) -> list[str]:
    """
    Sinh 2 paraphrase của query để tăng recall.
    
    Ví dụ:
    Query: "Tác giả nói gì về lòng từ bi?"
    → ["Quan điểm của tác giả về sự thương yêu là gì?",
       "Nội dung liên quan đến tình thương và lòng trắc ẩn trong sách"]
    
    Returns: [query_gốc, paraphrase_1, paraphrase_2]
    """
    try:
        client = get_openai()
        response = await client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=[
                {"role": "system", "content": EXPAND_SYSTEM_PROMPT},
                {"role": "user", "content": f"Câu gốc: {query}"},
            ],
            max_tokens=200,
            temperature=0.7,
        )
        raw = response.choices[0].message.content or ""
        paraphrases = [line.strip() for line in raw.strip().splitlines() if line.strip()]
        # Query gốc luôn ở đầu, thêm paraphrases phía sau
        return [query] + paraphrases[:2]

    except Exception:
        # Nếu expand thất bại → trả về query gốc (degraded gracefully)
        return [query]


async def embed_expanded_queries(queries: list[str]) -> list[float]:
    """
    Embed nhiều query variants, trả về embedding trung bình (centroid).
    Centroid embedding tốt hơn single query embedding vì bao phủ nhiều hướng ngữ nghĩa.
    """
    import numpy as np
    from services.embedding import embed_batch

    embeddings = await embed_batch(queries)
    # Tính mean embedding
    arr = np.array(embeddings, dtype=np.float32)
    centroid = arr.mean(axis=0)
    # Normalize về unit vector
    norm = np.linalg.norm(centroid)
    if norm > 0:
        centroid = centroid / norm
    return centroid.tolist()
