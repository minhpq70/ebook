from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime
from enum import Enum


# ============================================================
# BOOK Schemas
# ============================================================
class BookCreate(BaseModel):
    title: str
    author: Optional[str] = None
    description: Optional[str] = None
    language: str = "vi"


class BookUploadRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500, description="Tiêu đề sách")
    author: Optional[str] = Field(None, max_length=200, description="Tác giả")
    publisher: Optional[str] = Field(None, max_length=200, description="Nhà xuất bản")
    published_year: Optional[str] = Field(None, max_length=10, description="Năm xuất bản")
    category: Optional[str] = Field(None, max_length=100, description="Danh mục sách")
    page_size: Optional[str] = Field(None, max_length=50, description="Khổ cỡ sách")
    description: Optional[str] = Field(None, max_length=2000, description="Mô tả sách")
    language: str = Field("vi", pattern=r"^(vi|en)$", description="Ngôn ngữ (vi/en)")

    @validator('title', 'author', 'publisher', 'published_year', 'category', 'page_size', 'description', pre=True)
    def sanitize_string(cls, v):
        if v is None:
            return v
        # Loại bỏ ký tự nguy hiểm và trim
        import re
        v = re.sub(r'[<>]', '', str(v)).strip()
        return v if v else None


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
class TaskType(str, Enum):
    QA = "qa"
    EXPLAIN = "explain"
    SUMMARIZE_CHAPTER = "summarize_chapter"
    SUMMARIZE_BOOK = "summarize_book"
    SUGGEST = "suggest"


class RAGQueryRequest(BaseModel):
    book_id: str
    query: str
    task_type: str = "qa"  # qa | explain | summarize_chapter | summarize_book | suggest | auto
    source: Optional[str] = None         # hệ thống nguồn (libol, stbook...)
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
    total_pages: Optional[int] = None
    processed_pages: Optional[int] = None
    total_chunks: Optional[int] = None
    stored_chunks: Optional[int] = None
    message: Optional[str] = None
