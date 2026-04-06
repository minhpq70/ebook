"""
Books Router
- POST /books/upload — Upload & ingest PDF
- GET  /books        — Danh sách sách
- GET  /books/{id}   — Chi tiết sách
- DELETE /books/{id} — Xóa sách
"""
import uuid
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from models.schemas import BookResponse, BookListResponse, IngestionStatus
from services import ingestion
from services.metadata_extractor import extract_metadata_from_pdf

router = APIRouter(prefix="/books", tags=["Books"])


@router.post("/upload", response_model=IngestionStatus)
async def upload_book(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="File PDF của sách"),
    title: str = Form(..., description="Tiêu đề sách"),
    author: str = Form(None, description="Tác giả"),
    publisher: str = Form(None, description="Nhà xuất bản"),
    published_year: str = Form(None, description="Năm xuất bản"),
    description: str = Form(None, description="Mô tả sách"),
    language: str = Form("vi", description="Ngôn ngữ (vi/en)"),
):
    """
    Upload PDF — trả về ngay với book_id, ingestion chạy nền.
    Frontend dùng GET /books/{id} để poll status.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ file PDF")
    if file.size and file.size > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File quá lớn (tối đa 50MB)")

    pdf_bytes = await file.read()
    unique_filename = f"{uuid.uuid4()}_{file.filename}"
    
    # Kích hoạt AI nếu có thông số trống
    is_default_title = (title == file.filename.replace('.pdf', '') or title == file.filename)
    if is_default_title or not author or not publisher or not published_year:
        ai_meta = await extract_metadata_from_pdf(pdf_bytes)
        if ai_meta:
            if is_default_title and ai_meta.get('title'):
                title = ai_meta['title']
            if not author and ai_meta.get('author'):
                author = ai_meta['author']
            if not publisher and ai_meta.get('publisher'):
                publisher = ai_meta['publisher']
            if not published_year and ai_meta.get('published_year'):
                published_year = str(ai_meta['published_year'])

    # Tạo book record + upload file lên Storage trước (nhanh)
    try:
        book_id = await ingestion.create_book_record(
            pdf_bytes=pdf_bytes,
            filename=unique_filename,
            title=title,
            author=author,
            publisher=publisher,
            published_year=published_year,
            description=description,
            language=language,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi upload: {str(e)}")

    # Ingestion pipeline chạy nền — không chặn response
    background_tasks.add_task(
        ingestion.run_ingestion_pipeline,
        book_id=book_id,
        pdf_bytes=pdf_bytes,
    )

    return IngestionStatus(
        book_id=book_id,
        status="processing",
        message=f"Đang xử lý sách '{title}'... Tự động cập nhật khi hoàn tất.",
    )



@router.get("", response_model=BookListResponse)
async def list_books():
    """Lấy danh sách tất cả sách."""
    books_data = ingestion.list_books()
    return BookListResponse(
        books=[BookResponse(**b) for b in books_data],
        total=len(books_data),
    )


@router.get("/{book_id}", response_model=BookResponse)
async def get_book(book_id: str):
    """Lấy metadata chi tiết của một cuốn sách."""
    book = ingestion.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Không tìm thấy sách")
    return BookResponse(**book)


@router.delete("/{book_id}")
async def delete_book(book_id: str):
    """Xóa sách và toàn bộ chunks liên quan."""
    book = ingestion.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Không tìm thấy sách")
    ingestion.delete_book(book_id)
    return {"message": f"Đã xóa sách '{book['title']}'"}


@router.get("/{book_id}/pdf-url")
async def get_pdf_url(book_id: str):
    """
    Tạo signed URL (1 giờ) để frontend đọc PDF từ Supabase Storage.
    Cần thiết vì bucket là private — không thể truy cập trực tiếp.
    """
    book = ingestion.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Không tìm thấy sách")

    file_path = book.get("file_path")
    if not file_path:
        raise HTTPException(status_code=404, detail="File PDF không tìm thấy")

    try:
        from core.supabase_client import get_supabase
        supabase = get_supabase()
        signed = supabase.storage.from_("books").create_signed_url(
            path=file_path,
            expires_in=3600,  # 1 giờ
        )
        url = signed.get("signedURL") or signed.get("signed_url") or signed.get("data", {}).get("signedUrl")
        if not url:
            raise ValueError("Không lấy được signed URL")
        return {"url": url, "expires_in": 3600}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tạo signed URL: {str(e)}")

