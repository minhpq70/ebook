from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# ============================================================
# BOOK Schemas
# ============================================================
class BookCreate(BaseModel):
    title: str
    author: Optional[str] = None
    description: Optional[str] = None
    language: str = "vi"


class BookResponse(BaseModel):
    id: str
    title: str
    author: Optional[str] = None
    publisher: Optional[str] = None
    published_year: Optional[str] = None
    category: Optional[str] = None
    page_size: Optional[str] = None
    ai_summary: Optional[str] = None
    description: Optional[str] = None
    language: str
    cover_url: Optional[str] = None
    file_path: str
    file_size: Optional[int] = None
    total_pages: Optional[int] = None
    status: str
    created_at: datetime


class BookListResponse(BaseModel):
    books: list[BookResponse]
    total: int


# ============================================================
# CHUNK Schemas
# ============================================================
class ChunkInfo(BaseModel):
    id: str
    chunk_index: int
    page_number: Optional[int]
    content: str
    score: Optional[float] = None


# ============================================================
# RAG Query Schemas
# ============================================================
class TaskType(str):
    QA = "qa"
    EXPLAIN = "explain"
    SUMMARIZE_CHAPTER = "summarize_chapter"
    SUMMARIZE_BOOK = "summarize_book"
    SUGGEST = "suggest"


class RAGQueryRequest(BaseModel):
    book_id: str
    query: str
    task_type: str = "qa"  # qa | explain | summarize_chapter | summarize_book | suggest
    chapter_hint: Optional[str] = None   # gợi ý chương (tùy chọn)
    top_k: Optional[int] = None          # override số chunks


class RAGQueryResponse(BaseModel):
    query: str
    task_type: str
    answer: str
    sources: list[ChunkInfo]             # các chunks đã dùng để trả lời
    model: str
    tokens_used: Optional[int]


# ============================================================
# Ingestion Status
# ============================================================
class IngestionStatus(BaseModel):
    book_id: str
    status: str
    total_chunks: Optional[int] = None
    message: Optional[str] = None
