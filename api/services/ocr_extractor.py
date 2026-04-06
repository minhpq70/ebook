"""
Vietnamese OCR Text Extractor
Khi text extraction thông thường bị vỡ encoding (do font SVN/VnTime/custom CMap),
module này dùng OCR (Tesseract + PyMuPDF) để "đọc" chữ từ ảnh render của trang PDF.

Flow:
1. Thử text extraction thông thường (nhanh)
2. Kiểm tra chất lượng text (có bị vỡ encoding không?)
3. Nếu vỡ → fallback sang OCR (chậm hơn nhưng chính xác)
"""
import io
import re
import fitz  # PyMuPDF
from PIL import Image
import pytesseract


def _is_garbled_vietnamese(text: str) -> bool:
    """
    Phát hiện text tiếng Việt bị vỡ encoding hoặc text không thể đọc được.
    """
    if not text or len(text) < 100:
        return False
        
    vn_chars = set('àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ'
                   'ÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴĐ')
    
    vn_count = sum(1 for c in text if c in vn_chars)
    alpha_count = sum(1 for c in text if c.isalpha())
    non_space_len = len(text.replace(' ', '').replace('\n', ''))
    
    # Ký tự điều khiển C1 (0x80 - 0x9F) thường xuyên xuất hiện khi font custom bị map sai vào Unicode
    c1_control_count = sum(1 for c in text if 0x80 <= ord(c) <= 0x9F)
    weird_symbols_count = sum(1 for c in text if c in '«»©®µ¶×÷')
    
    if c1_control_count > 50 or weird_symbols_count > 50:
        return True
    
    # Text rác: alpha_count quá nhỏ so với tổng text (toàn ký tự lạ/symbol)
    if non_space_len > 100 and alpha_count < non_space_len * 0.1:
        return True
        
    if alpha_count < 50:
        return False
        
    vn_ratio = vn_count / alpha_count
    
    garbled_chars = set('µ¸¶·¹¨»¾¼½©ªÊÇÈÉËÌÐÎÏÑÕÒÓÔÖßãèåæçé¬íêëìî®ïóñò÷ôõöøúþûüý­°±²³¦§¡¤¢£¥ÆŸœš')
    garbled_count = sum(1 for c in text if c in garbled_chars)
    garbled_ratio = garbled_count / alpha_count
    
    # 1. Quá ít ký tự Việt chuẩn VÀ có nhiều ký tự rác TCVN3
    if vn_ratio < 0.03 and garbled_ratio > 0.03:
        return True
        
    # 2. Hoặc quá ít ký tự Việt có dấu trong một văn bản dài tiếng Việt
    # Tính cả text tiếng Anh có số lượng nhỏ vn_ratio nhưng nếu dài thì vn_ratio=0
    # Nên dùng ngưỡng an toàn hơn: vn_ratio < 0.005 (nửa phần trăm)
    if vn_ratio < 0.005 and vn_count < 5:
        return True
        
    return False


def ocr_page(page: fitz.Page, lang: str = 'vie', dpi: int = 300) -> str:
    """
    OCR một trang PDF bằng Tesseract.
    
    Args:
        page: fitz.Page object
        lang: Ngôn ngữ OCR (mặc định 'vie' cho tiếng Việt)
        dpi: Độ phân giải render (300 cho chất lượng tốt)
    """
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    img = Image.open(io.BytesIO(pix.tobytes('png')))
    
    text = pytesseract.image_to_string(img, lang=lang)
    return text.strip()


def extract_pages_with_ocr_fallback(pdf_bytes: bytes, max_pages: int = None) -> list[dict]:
    """
    Trích xuất text từ PDF với fallback OCR.
    
    1. Đọc text extraction thường (nhanh) cho 3 trang đầu
    2. Kiểm tra chất lượng: nếu bị vỡ → chuyển sang OCR cho TOÀN BỘ sách
    3. Nếu text OK → dùng text extraction thường cho toàn bộ (nhanh)
    
    Returns: [{'page_number': int, 'text': str}, ...]
    """
    doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    total = len(doc)
    if max_pages:
        total = min(total, max_pages)
    
    # --- Bước 1: Kiểm tra 3 trang đầu bằng text extraction ---
    sample_text = ""
    for i in range(min(15, total)):
        sample_text += doc.load_page(i).get_text("text") + "\n"
    
    use_ocr = _is_garbled_vietnamese(sample_text)
    
    if use_ocr:
        print(f"[OCR] Phát hiện text bị vỡ encoding → dùng OCR cho {total} trang", flush=True)
    else:
        print(f"[TEXT] Text extraction bình thường cho {total} trang", flush=True)
    
    # --- Bước 2: Trích xuất ---
    pages = []
    for i in range(total):
        if use_ocr:
            text = ocr_page(doc.load_page(i), lang='vie', dpi=250)
        else:
            text = doc.load_page(i).get_text("text")
        
        # Làm sạch
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.strip()
        
        if text and len(text) > 20:
            pages.append({
                "page_number": i + 1,
                "text": text,
            })
        
        # Progress log mỗi 50 trang
        if use_ocr and (i + 1) % 50 == 0:
            print(f"[OCR] Đã xử lý {i+1}/{total} trang...", flush=True)
    
    doc.close()
    return pages


def ocr_toc_pages(pdf_bytes: bytes, max_toc_pages: int = 15) -> str | None:
    """
    Trích xuất Mục lục bằng OCR.
    Quét các trang đầu của sách (thường trang 3-10) tìm trang có chữ 'Mục lục'.
    
    Returns: Text mục lục hoặc None
    """
    doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    total = min(len(doc), max_toc_pages)
    
    toc_text = ""
    in_toc = False
    
    for i in range(total):
        text = ocr_page(doc.load_page(i), lang='vie', dpi=300)
        
        if 'mục lục' in text.lower() or 'MỤC LỤC' in text:
            in_toc = True
        
        if in_toc:
            toc_text += text + "\n"
            # Nếu trang không còn dạng mục lục (không có số trang/dấu chấm) thì dừng
            # Heuristic: mục lục có nhiều số (số trang)
            digit_count = sum(1 for c in text if c.isdigit())
            if in_toc and len(toc_text) > 500 and digit_count < 3:
                break
    
    doc.close()
    
    if toc_text.strip():
        return f"[HỆ THỐNG] MỤC LỤC (OCR):\n{toc_text.strip()}"
    
    return None
