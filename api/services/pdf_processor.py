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
import fitz
import pytesseract
from PIL import Image
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


def is_valid_vietnamese_text(text: str) -> bool:
    """
    Kiểm tra xem văn bản trích xuất có bị lỗi font/encoding hay không
    (dành riêng cho tiếng Việt). Trả về True nếu là text hợp lệ.
    """
    if not text or len(text.strip()) < 50:
        # Quá ngắn để kết luận, mặc định cho qua để tránh OCR lãng phí
        return True
        
    # Pattern gom các chữ cái có dấu tiếng Việt
    vie_pattern = re.compile(r'[àáảãạăằắẳẵặâầấẩẫậđèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵ]')
    # Pattern các ký tự rác phổ biến khi lỗi ToUnicode (VNI, TCVN3 nguyên thủy, VISCII...)
    suspicious_pattern = re.compile(r'[µ¸¶·¹¨»¾¼½Æ©ÇÊÈÉË®ÌÐÎÏÑªÒÕÓÔÖ×ÝØÜÞßãä«åæç¬ñõøö÷ùúûüþ¡¢§£¤¥¦]')
    
    # Tính số lượng
    vie_count = len(vie_pattern.findall(text.lower()))
    sus_count = len(suspicious_pattern.findall(text))
    total_chars = len(text)
    
    if total_chars == 0:
        return True
        
    vie_ratio = vie_count / total_chars
    sus_ratio = sus_count / total_chars
    
    # 1. Rất nhiều ký tự lạ -> Chắc chắn hỏng
    if sus_ratio > 0.02:
        return False
        
    # 2. Không có tý tiếng Việt nào nhưng lại dính ký tự lạ -> Hỏng
    if vie_ratio < 0.005 and sus_ratio > 0.005:
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
    
    for i in range(len(doc)):
        page = doc[i]
        # Thử trích xuất text thông thường
        raw_text = page.get_text() or ""
        
        # Đánh giá encoding
        if not is_valid_vietnamese_text(raw_text):
            print(f"Trang {i+1} phát hiện lỗi font/encoding. Fallback to OCR...")
            try:
                # Render trang thành ảnh với độ phân giải đủ đọc
                pix = page.get_pixmap(dpi=300)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                # Chạy OCR
                raw_text = pytesseract.image_to_string(img, lang="vie")
            except Exception as e:
                print(f"Lỗi OCR trang {i+1}: {e}")
                # Nếu OCR lỗi, vẫn giữ lại raw_text lỗi thay vì bỏ trống hoàn toàn

        text = _clean_text(raw_text)
        if text:
            pages.append({
                "page_number": i + 1,
                "text": text
            })
            
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
