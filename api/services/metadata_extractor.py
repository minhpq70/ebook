import io
import json
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

async def extract_metadata_from_pdf(pdf_bytes: bytes) -> dict:
    """
    Trích xuất text trang bìa và gửi lên GPT-4o-mini để lấy metadata.
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
