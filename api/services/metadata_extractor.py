import io
import json
import fitz  # PyMuPDF
from pypdf import PdfReader
from core.openai_client import get_openai
from core.config import settings

def extract_early_text(pdf_bytes: bytes, max_pages: int = 3) -> str:
    """Extraxt text từ n trang đầu tiên bằng Pypdf để đưa cho AI đọc."""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        # Đọc 3 trang đầu
        for i in range(min(max_pages, len(reader.pages))):
            page_text = reader.pages[i].extract_text()
            if page_text:
                text += page_text + "\n\n"
        return text.strip()
    except Exception as e:
        print(f"Lỗi extract text: {e}")
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
        print(f"Lỗi trích xuất ảnh bìa: {e}")
        return None

def extract_toc(pdf_bytes: bytes) -> str | None:
    """
    Trích xuất Mục lục (Table of Contents / Outline) có sẵn trong PDF.
    Nếu không có, quét bằng chữ 'Mục Lục' ở đầu hoặc cuối sách.
    Trả về dạng văn bản (text), hoặc None nếu không có.
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        toc = doc.get_toc()
        
        if toc:
            doc.close()
            # toc là một list chứa [level, title, page_number]
            lines = []
            lines.append("[HỆ THỐNG] MỤC LỤC CUỐN SÁCH (TABLE OF CONTENTS):")
            for item in toc:
                level = item[0]
                title = item[1]
                page = item[2]
                indent = "  " * (level - 1)
                lines.append(f"{indent}- {title} (Trang {page})")
            return "\n".join(lines)
            
        # NẾU KHÔNG CÓ METADATA TOC, TIẾN HÀNH QUÉT TEXT (15 TRANG ĐẦU, 15 TRANG CUỐI)
        total_pages = len(doc)
        search_pages = list(range(min(15, total_pages)))
        if total_pages > 30:
            search_pages.extend(range(total_pages - 15, total_pages))
            
        found_toc_text = ""
        in_toc_mode = False
        
        for p in search_pages:
            text = doc.load_page(p).get_text("text")
            if "mục lục" in text.lower() or "table of contents" in text.lower():
                in_toc_mode = True
            
            if in_toc_mode:
                found_toc_text += text + "\n"
                # Thường mục lục kéo dài 2-3 trang, cứ gom lại
            
        doc.close()
        
        if len(found_toc_text) > 50:
            # Lấy tối đa 15000 ký tự (khoảng 10-15 trang) để không vượt quá giới hạn embedding
            return f"[HỆ THỐNG] MỤC LỤC CUỐN SÁCH (TABLE OF CONTENTS):\n{found_toc_text[:15000]}"
            
        return None
    except Exception as e:
        print(f"Lỗi trích xuất Mục lục: {e}")
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

    client = get_openai()
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
        print(f"Lỗi tạo AI summary: {e}")
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

    client = get_openai()
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
        print(f"Lỗi gọi OpenAI metadata: {e}")
        
    return {}
