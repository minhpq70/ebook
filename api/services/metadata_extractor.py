from __future__ import annotations
import io
import json
import logging
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
from core.openai_client import get_openai, get_chat_openai
from core.config import settings
from .pdf_processor import is_valid_vietnamese_text
import re

logger = logging.getLogger("ebook.metadata")
def extract_early_text(pdf_bytes: bytes, max_pages: int = 5) -> str:
    """Trích xuất text từ n trang đầu tiên bằng PyMuPDF, kèm OCR fallback."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = ""
        for i in range(min(max_pages, len(doc))):
            page_text = doc[i].get_text() or ""
            # Bắt buộc OCR nếu trang quá ít chữ (<50) vì có thể trang bìa là ảnh quét
            if len(page_text.strip()) < 50 or not is_valid_vietnamese_text(page_text):
                try:
                    pix = doc[i].get_pixmap(dpi=300)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    ocr_text = pytesseract.image_to_string(img, lang="vie")
                    if len(ocr_text.strip()) > len(page_text.strip()):
                        page_text = ocr_text
                except Exception as e:
                    logger.warning(f"Lỗi OCR trang {i} (Tesseract chưa cài đặt hoặc thiếu model vie): {e}")
            if page_text:
                text += page_text + "\n\n"
        doc.close()
        return text.strip()
    except Exception as e:
        logger.warning("Lỗi extract text: %s", e)
        return ""

def get_cover_image_bytes(pdf_bytes: bytes) -> bytes | None:
    """
    Sử dụng PyMuPDF để trích xuất trang đầu tiên thành ảnh JPEG.
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if len(doc) == 0:
            return None
        page = doc.load_page(0)
        # Render với độ phân giải khoảng 150dpi (matrix 2)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img_bytes = pix.tobytes("jpeg")
        doc.close()
        return img_bytes
    except Exception as e:
        logger.warning("Lỗi trích xuất ảnh bìa: %s", e)
        return None

def extract_toc(pdf_bytes: bytes) -> str | None:
    """
    Trích xuất Mục lục (Table of Contents / Outline) từ PDF.
    Tìm ở cả đầu sách và cuối sách (mục lục VN thường ở cuối).
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        toc = doc.get_toc()
        total_pages = len(doc)
        
        final_toc = ""
        
        # Phần 1: Metadata TOC (nếu có, luôn chính xác)
        if toc:
            lines = ["[HỆ THỐNG] MỤC LỤC TỪ METADATA:"]
            for item in toc:
                level, title, page = item[0], item[1], item[2]
                indent = "  " * (level - 1)
                lines.append(f"{indent}- {title} (Trang {page})")
            final_toc += "\n".join(lines) + "\n\n"
        
        # Phần 2: Quét text trang mục lục bằng PyMuPDF
        # Tìm ở 10 trang đầu VÀ 15 trang cuối (mục lục VN thường ở cuối sách)
        search_pages = list(range(min(10, total_pages)))
        if total_pages > 20:
            search_pages.extend(range(total_pages - 15, total_pages))

        found_entries = []
        toc_pattern = re.compile(r"^\s*\d+\.?\s+.*?\s+\d+$")  # lines ending with page number

        for p in search_pages:
            if p >= len(doc):
                continue
            text = doc[p].get_text() or ""
            # Nếu trang có ít chữ hoặc không phải tiếng Việt, dùng OCR
            if len(text.strip()) < 50 or not is_valid_vietnamese_text(text):
                try:
                    pix = doc[p].get_pixmap(dpi=300)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    ocr_text = pytesseract.image_to_string(img, lang="vie")
                    if len(ocr_text.strip()) > len(text.strip()):
                        text = ocr_text
                except Exception:
                    pass
            for line in text.splitlines():
                if toc_pattern.match(line.strip()):
                    found_entries.append(line.strip())

        if found_entries:
            final_toc += "[HỆ THỐNG] VĂN BẢN MỤC LỤC CHI TIẾT:\n" + "\n".join(found_entries[:2000]) + "\n\n"

        doc.close()

        if final_toc.strip():
            return final_toc

        return None
    except Exception as e:
        logger.warning("Lỗi trích xuất Mục lục: %s", e)
        return None

async def generate_ai_summary(pdf_bytes: bytes) -> str | None:
    """
    Dùng AI tóm tắt nội dung sách dựa trên các trang đầu (những trang thường chứa tóm tắt/lời nói đầu).
    """
    text = extract_early_text(pdf_bytes, max_pages=15)
    if not text:
        return None

    system_prompt = """Bạn là một biên tập viên xuất bản. 
Dựa vào đoạn văn bản trích xuất từ phần đầu của một cuốn sách (có thể chứa mục lục, lời nói đầu, hoặc trang thông tin), 
hãy viết một đoạn tóm tắt ngắn gọn, hấp dẫn về nội dung cuốn sách (khoảng 3-5 câu). 
Nếu văn bản vô nghĩa hoặc không đủ dữ liệu, hãy trả về 'Không có đủ thông tin để tóm tắt.'"""

    client = get_chat_openai()
    try:
        response = await client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Trích xuất văn bản từ sách:\n\n{text[:8000]}"}
            ],
            temperature=0.3,
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.warning("Lỗi tạo AI summary: %s", e)
        return None

async def extract_metadata_from_pdf(pdf_bytes: bytes) -> dict:
    """
    Trích xuất text trang bìa và gửi lên GPT để lấy metadata.
    Trả về dict: {"title": "", "author": "", "publisher": "", "published_year": ""}
    """
    text = extract_early_text(pdf_bytes, max_pages=3)
    if not text:
        return {}

    system_prompt = """Bạn là một thủ thư chuyên nghiệp.
Nhiệm vụ của bạn là phân tích các trang đầu của cuốn sách và trích xuất thông tin xuất bản.
Nếu không tìm thấy thông tin nào, hãy để giá trị là null.
Trả về định dạng JSON nghiêm ngặt với các trường sau:
- title: Tên sách (chính xác, bỏ các ký tự rác)
- author: Tên tác giả
- publisher: Nhà xuất bản
- published_year: Năm xuất bản (chỉ lấy số năm, hoặc string nếu không rõ, ví dụ "2023" hoặc "Thập niên 90")"""

    client = get_chat_openai()
    try:
        response = await client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Trích xuất thông tin từ đoạn văn bản sau:\n\n{text[:4000]}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=200
        )
        
        result_text = response.choices[0].message.content
        if result_text:
            data = json.loads(result_text)
            return data
    except Exception as e:
        logger.warning("Lỗi gọi OpenAI metadata: %s", e)
        
    return {}
