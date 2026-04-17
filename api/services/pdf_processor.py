"""
PDF Processor Service
- Đọc file PDF từ bytes
- Trích xuất text theo trang
- Chunk text thành các đoạn nhỏ với overlap
- Tối ưu cho tiếng Việt
"""
import io
import re
import logging
from dataclasses import dataclass
from pypdf import PdfReader
import fitz
import pytesseract
from PIL import Image
from langchain_text_splitters import RecursiveCharacterTextSplitter
import tiktoken

from core.config import settings

logger = logging.getLogger("ebook.pdf")


@dataclass
class TextChunk:
    content: str
    page_number: int
    chunk_index: int
    token_count: int


# Cache tiktoken encoding ở module level — tránh khởi tạo lại mỗi lần gọi
_ENCODING = tiktoken.get_encoding("cl100k_base")


def _count_tokens(text: str) -> int:
    """Đếm tokens dùng cl100k_base (compatible với OpenAI models)."""
    return len(_ENCODING.encode(text))


def _clean_text(text: str) -> str:
    """Làm sạch text tiếng Việt: xóa ký tự lạ, chuẩn hóa khoảng trắng."""
    # Xóa ký tự control characters (trừ newline và tab)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    # Collapse nhiều khoảng trắng thành 1
    text = re.sub(r'[ \t]+', ' ', text)
    # Collapse nhiều newlines thành tối đa 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def is_valid_vietnamese_text_optimized(text: str) -> bool:
    """
    Optimized check for valid Vietnamese text.
    Returns True if text contains valid Vietnamese characters and structure.
    More strict validation for OCR quality assessment.
    """
    if not text or len(text.strip()) < 20:  # Require minimum length
        return False

    # Check for Vietnamese characters (đ, ă, â, ê, ô, ư, ơ)
    vietnamese_chars = re.findall(r'[đăâêôươĐĂÂÊÔƯƠ]', text)
    if len(vietnamese_chars) < 3:  # Require more Vietnamese chars
        return False

    # Check for reasonable word structure (Vietnamese words are typically 2-8 chars)
    words = [w for w in text.split() if len(w) > 1]  # Filter out single chars
    if len(words) < 5:  # Require minimum word count
        return False

    # Check average word length (Vietnamese words are typically 2-8 chars)
    avg_word_len = sum(len(word) for word in words) / len(words)
    if avg_word_len < 2 or avg_word_len > 12:  # Stricter bounds
        return False

    # Check for excessive non-alphabetic characters (indicates OCR garbage)
    # Allow common punctuation: spaces, punctuation marks
    alphabetic_chars = sum(c.isalpha() or c in 'đăâêôươĐĂÂÊÔƯƠ' for c in text)
    total_chars = len(text)
    alpha_ratio = alphabetic_chars / total_chars
    if alpha_ratio < 0.6:  # More lenient: require 60% alphabetic content
        return False

    return True


def extract_pages_from_pdf(pdf_bytes: bytes) -> list[dict]:
    """
    Trích xuất text từng trang của PDF bằng PyMuPDF (fitz).
    Nếu trang bị lỗi encoding, tự động chuyển sang OCR (Tesseract).
    Returns: [{'page_number': int, 'text': str}, ...]
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []

    async def process_page_async(page_num: int):
        """Process single page with optimized OCR"""
        page = doc[page_num]
        # Thử trích xuất text thông thường
        raw_text = page.get_text() or ""

        # Đánh giá encoding với optimized logic
        if is_valid_vietnamese_text_optimized(raw_text):
            return _clean_text(raw_text)

        # OCR với resolution thấp hơn (200 DPI) + crop margins để tăng tốc
        # Crop 5% margins để loại bỏ phần không cần thiết
        rect = page.rect
        margin = 0.05
        crop_rect = fitz.Rect(
            rect.x0 + rect.width * margin,
            rect.y0 + rect.height * margin,
            rect.x1 - rect.width * margin,
            rect.y1 - rect.height * margin
        )

        try:
            pix = page.get_pixmap(dpi=200, clip=crop_rect)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            # OCR với timeout 30 giây
            ocr_text = pytesseract.image_to_string(img, lang="vie", timeout=30)
            return _clean_text(ocr_text)
        except Exception as e:
            logger.warning("OCR failed for page %d: %s", page_num + 1, e)
            # Fallback to original text if OCR fails
            return _clean_text(raw_text)

    # Sequential processing for now (will be optimized in Phase 2)
    for i in range(len(doc)):
        try:
            text = asyncio.run(process_page_async(i))
            if text:
                pages.append({
                    "page_number": i + 1,
                    "text": text
                })
        except Exception as e:
            logger.error("Error processing page %d: %s", i + 1, e)

    doc.close()
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
    enc = _ENCODING

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
        logger.warning("Lỗi thêm TOC chunk: %s", e)

    return chunks, total_pages
