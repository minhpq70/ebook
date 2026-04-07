"""
PDF Processor Service
- Đọc file PDF từ bytes
- Trích xuất text theo trang
- Chunk text thành các đoạn nhỏ với overlap
- Tối ưu cho tiếng Việt
"""
import io
import re
from dataclasses import dataclass
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
import tiktoken

from core.config import settings


@dataclass
class TextChunk:
    content: str
    page_number: int
    chunk_index: int
    token_count: int


def _count_tokens(text: str) -> int:
    """Đếm tokens dùng cl100k_base (compatible với OpenAI models)."""
    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def _clean_text(text: str) -> str:
    """Làm sạch text tiếng Việt: xóa ký tự lạ, chuẩn hóa khoảng trắng."""
    # Xóa ký tự control characters (trừ newline và tab)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    # Collapse nhiều khoảng trắng thành 1
    text = re.sub(r'[ \t]+', ' ', text)
    # Collapse nhiều newlines thành tối đa 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def extract_pages_from_pdf(pdf_bytes: bytes) -> list[dict]:
    """
    Trích xuất text từng trang của PDF bằng pypdf.
    Returns: [{'page_number': int, 'text': str}, ...]
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        text = _clean_text(text)
        if text:
            pages.append({
                "page_number": i + 1,
                "text": text
            })
    return pages


def chunk_pages(pages: list[dict]) -> list[TextChunk]:
    """
    Chunk nội dung các trang thành các đoạn nhỏ.

    Chiến lược tối ưu cho tiếng Việt:
    - Dùng tiktoken để đếm tokens chính xác (không ước lượng)
    - Ưu tiên split theo paragraph → câu → khoảng trắng
    - Chunk nhỏ hơn (300 tokens) → precision cao hơn khi retrieve
    - Overlap lớn hơn (80 tokens) → không mất context giữa chunks
    """
    enc = tiktoken.get_encoding("cl100k_base")

    def _token_len(text: str) -> int:
        return len(enc.encode(text))

    splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " ", ""],
        chunk_size=settings.rag_chunk_size,           # token-based (300)
        chunk_overlap=settings.rag_chunk_overlap,     # token-based (80)
        length_function=_token_len,                   # dùng tiktoken, không ước lượng
        is_separator_regex=False,
    )

    chunks: list[TextChunk] = []
    chunk_index = 0

    for page in pages:
        page_number = page["page_number"]
        text = page["text"]

        if len(text) < 50:  # bỏ qua trang quá ngắn
            continue

        page_chunks = splitter.split_text(text)

        for chunk_text in page_chunks:
            chunk_text = chunk_text.strip()
            if not chunk_text or len(chunk_text) < 20:
                continue

            token_count = _token_len(chunk_text)
            chunks.append(TextChunk(
                content=chunk_text,
                page_number=page_number,
                chunk_index=chunk_index,
                token_count=token_count
            ))
            chunk_index += 1

    return chunks



def process_pdf(pdf_bytes: bytes) -> tuple[list[TextChunk], int]:
    """
    Pipeline hoàn chỉnh: bytes → chunks
    Returns: (chunks, total_pages)
    """
    pages = extract_pages_from_pdf(pdf_bytes)
    total_pages = max((p["page_number"] for p in pages), default=0)
    chunks = chunk_pages(pages)
    
    # Trích xuất TOC nguyên bản (nếu có) để tạo 1 chunk tham chiếu cực mạnh cho RAG
    try:
        from .metadata_extractor import extract_toc
        toc_text = extract_toc(pdf_bytes)
        if toc_text:
            chunks.append(TextChunk(
                content=toc_text,
                page_number=-1, # Báo hiệu đây là metadata system-generated
                chunk_index=-1,
                token_count=_count_tokens(toc_text)
            ))
    except Exception as e:
        print(f"Lỗi thêm TOC chunk: {e}")

    return chunks, total_pages
