from __future__ import annotations
import io
import json
import logging
import fitz  # PyMuPDF
from PIL import Image
from core.openai_client import get_openai, get_chat_openai
from core.config import settings
from .pdf_processor import is_valid_vietnamese_text
from .ocr_engine import ocr_page_image
import re
import asyncio

logger = logging.getLogger("ebook.metadata")
def extract_early_text(pdf_bytes: bytes, max_pages: int = 5, use_ocr: bool = True) -> str:
    """Trích xuất text từ n trang đầu tiên bằng PyMuPDF, kèm OCR fallback tùy chọn."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = ""
        for i in range(min(max_pages, len(doc))):
            page_text = doc[i].get_text() or ""
            # Bắt buộc OCR nếu trang quá ít chữ (<50) vì có thể trang bìa là ảnh quét
            if use_ocr and (len(page_text.strip()) < 50 or not is_valid_vietnamese_text(page_text)):
                try:
                    pix = doc[i].get_pixmap(dpi=300)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    ocr_text = ocr_page_image(img)
                    if len(ocr_text.strip()) > len(page_text.strip()):
                        page_text = ocr_text
                except Exception as e:
                    logger.warning(f"Lỗi OCR trang {i}: {e}")
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
                    ocr_text = ocr_page_image(img)
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
    text = await asyncio.to_thread(extract_early_text, pdf_bytes, 15)
    if not text:
        return None

    system_prompt = """Bạn là một biên tập viên xuất bản. 
Dựa vào đoạn văn bản trích xuất từ phần đầu của một cuốn sách (có thể chứa mục lục, lời nói đầu, hoặc trang thông tin), 
hãy viết một đoạn tóm tắt ngắn gọn, hấp dẫn về nội dung cuốn sách (khoảng 3-5 câu). 
Nếu văn bản vô nghĩa hoặc không đủ dữ liệu, hãy trả về 'Không có đủ thông tin để tóm tắt.'
LƯU Ý QUAN TRỌNG: KHÔNG ĐƯỢC sinh ra các thẻ <thought> hay phân tích quá trình suy nghĩ của bạn. Hãy in ra trực tiếp đoạn tóm tắt cuối cùng."""

    client = get_chat_openai()
    try:
        response = await client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Trích xuất văn bản từ sách:\n\n{text[:8000]}"}
            ],
            temperature=0.3,
            max_tokens=1000
        )
        content = response.choices[0].message.content.strip()
        import re
        content = re.sub(r'<thought>.*?</thought>', '', content, flags=re.DOTALL).strip()
        return content
    except Exception as e:
        logger.warning("Lỗi tạo AI summary: %s", e)
        return None

async def extract_metadata_from_pdf(pdf_bytes: bytes) -> dict:
    """
    Trích xuất text trang bìa và gửi lên GPT để lấy metadata.
    Trả về dict: {"title": "", "author": "", "publisher": "", "published_year": ""}
    """
    # Tắt OCR ở bước này vì đây là bước chạy đồng bộ trong API Upload,
    # nếu chạy OCR (đặc biệt là lần đầu load model PaddleOCR) sẽ tốn rất nhiều thời gian gây ra 504 Timeout.
    text = await asyncio.to_thread(extract_early_text, pdf_bytes, 3, False)
    if not text:
        return {}

    system_prompt = """Bạn là một thủ thư chuyên nghiệp.
Nhiệm vụ của bạn là phân tích các trang đầu của cuốn sách và trích xuất thông tin xuất bản.
Nếu không tìm thấy thông tin nào, hãy để giá trị là null.

BẮT BUỘC: Chỉ trả về DUY NHẤT một khối JSON hợp lệ, KHÔNG có text nào khác trước hoặc sau.
KHÔNG viết giải thích, KHÔNG viết markdown, KHÔNG có ```json```.
KHÔNG sử dụng thẻ <thought> hay bất kỳ suy luận nào.

Định dạng JSON nghiêm ngặt:
{"title": "Tên sách", "author": "Tên tác giả", "publisher": "Nhà xuất bản", "published_year": "Năm"}"""

    client = get_chat_openai()
    try:
        response = await client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Trích xuất thông tin từ đoạn văn bản sau:\n\n{text[:4000]}"}
            ],
            temperature=0.0,
            max_tokens=300
        )
        
        result_text = response.choices[0].message.content or ""
        result_text = result_text.strip()
        
        # Loại bỏ thinking tags nếu có (Gemma, Qwen)
        result_text = re.sub(r'<thought>.*?</thought>', '', result_text, flags=re.DOTALL).strip()
        
        # Loại bỏ markdown code fences
        result_text = re.sub(r'^```(?:json)?\s*', '', result_text)
        result_text = re.sub(r'\s*```$', '', result_text)
        
        # Tìm JSON block bằng regex (phòng trường hợp AI thêm text thừa)
        json_match = re.search(r'\{[^{}]*\}', result_text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            logger.info("AI metadata extracted: %s", data.get('title', '?'))
            return data
        else:
            logger.warning("Không tìm thấy JSON trong response AI metadata: %s", result_text[:200])
    except json.JSONDecodeError as e:
        logger.warning("Lỗi parse JSON metadata: %s — raw: %s", e, result_text[:200])
    except Exception as e:
        logger.warning("Lỗi gọi OpenAI metadata: %s", e)
        
    return {}

