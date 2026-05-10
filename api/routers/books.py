"""
Books Router
- POST /books/upload — Upload & ingest PDF
- GET  /books        — Danh sách sách
- GET  /books/{id}   — Chi tiết sách
- DELETE /books/{id} — Xóa sách
"""
import uuid
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import JSONResponse

from core.config import settings
from models.schemas import BookResponse, BookListResponse, IngestionStatus, BookUploadRequest
from services import ingestion
from services.ingestion_queue import enqueue_ingestion_job
from services.metadata_extractor import extract_metadata_from_pdf
from core.auth import require_admin

router = APIRouter(prefix="/books", tags=["Books"])


@router.post("/upload", response_model=IngestionStatus)
async def upload_book(
    file: UploadFile = File(..., description="File PDF của sách"),
    title: str = Form(...),
    author: str | None = Form(None),
    publisher: str | None = Form(None),
    published_year: str | None = Form(None),
    category: str | None = Form(None),
    page_size: str | None = Form(None),
    description: str | None = Form(None),
    language: str = Form("vi"),
    _: dict = Depends(require_admin),
):
    """
    Upload PDF — chỉ Admin. Trả về ngay với book_id, ingestion chạy nền.
    Frontend dùng GET /books/{id} để poll status.
    """
    # Validation file
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ file PDF")
    
    # Kiểm tra MIME type
    allowed_mime_types = ["application/pdf"]
    if file.content_type not in allowed_mime_types:
        raise HTTPException(status_code=400, detail="File phải là PDF hợp lệ")
    
    # Kiểm tra kích thước theo cấu hình để hỗ trợ file lớn hơn.
    max_size = settings.max_upload_size_mb * 1024 * 1024
    if file.size and file.size > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File quá lớn (tối đa {settings.max_upload_size_mb}MB)",
        )
    
    # Đọc và validate nội dung PDF
    pdf_bytes = await file.read()
    if len(pdf_bytes) < 100:  # PDF tối thiểu phải có header
        raise HTTPException(status_code=400, detail="File PDF không hợp lệ")
    
    # Kiểm tra PDF header
    if not pdf_bytes.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="File không phải là PDF hợp lệ")

    unique_filename = f"{uuid.uuid4()}_{file.filename}"

    # Construct request model to trigger validators
    upload_data = BookUploadRequest(
        title=title, author=author, publisher=publisher, published_year=published_year,
        category=category, page_size=page_size, description=description, language=language
    )

    # Lấy metadata từ form (không gọi AI ở đây — để worker xử lý nền)
    title = upload_data.title
    author = upload_data.author
    publisher = upload_data.publisher
    published_year = upload_data.published_year
    category = upload_data.category
    page_size = upload_data.page_size
    description = upload_data.description
    language = upload_data.language

    # Tạo book record + upload file lên Storage trước (nhanh)
    try:
        book_id = await ingestion.create_book_record(
            pdf_bytes=pdf_bytes,
            filename=unique_filename,
            title=title,
            author=author,
            publisher=publisher,
            published_year=published_year,
            category=category,
            page_size=page_size,
            description=description,
            language=language,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi upload: {str(e)}")

    await ingestion.mark_book_queued(book_id, "Đã đưa vào hàng đợi ingestion")
    await enqueue_ingestion_job(book_id=book_id, job_type="ingest")

    return IngestionStatus(
        book_id=book_id,
        status="queued",
        message=f"Sách '{title}' đã vào hàng đợi ingestion. Worker sẽ tự động xử lý.",
    )



@router.get("", response_model=BookListResponse)
async def list_books():
    """Lấy danh sách tất cả sách (public)."""
    books_data = ingestion.list_books()
    return BookListResponse(
        books=[BookResponse(**b) for b in books_data],
        total=len(books_data),
    )


@router.get("/{book_id}", response_model=BookResponse)
async def get_book(book_id: str):
    """Lấy metadata chi tiết của một cuốn sách (public)."""
    book = ingestion.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Không tìm thấy sách")
    return BookResponse(**book)


@router.get("/{book_id}/ingestion-status", response_model=IngestionStatus)
async def get_ingestion_status(book_id: str):
    """Lấy tiến độ ingestion hiện tại từ cache; fallback sang trạng thái book."""
    book = ingestion.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Không tìm thấy sách")

    progress = await ingestion.get_ingestion_progress(book_id)
    if progress:
        return IngestionStatus(**progress)

    return IngestionStatus(
        book_id=book_id,
        status=book["status"],
        total_pages=book.get("total_pages"),
        message="Không có tiến độ tạm thời trong cache",
    )


@router.delete("/{book_id}")
async def delete_book(book_id: str, _: dict = Depends(require_admin)):
    """Xóa sách — chỉ Admin."""
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

from fastapi import Response
@router.get("/{book_id}/cover")
async def get_cover(book_id: str):
    """Lấy ảnh bìa sách."""
    book = ingestion.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Không tìm thấy sách")
    
    try:
        from core.supabase_client import get_supabase
        supabase = get_supabase()
        cover_path = f"{book_id}.jpeg"
        cover_bytes = supabase.storage.from_("covers").download(cover_path)
        if not cover_bytes:
             raise HTTPException(status_code=404, detail="Không tìm thấy file ảnh")
        return Response(content=cover_bytes, media_type="image/jpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
