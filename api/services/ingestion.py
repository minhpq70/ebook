"""
Book Ingestion Service
- Upload PDF lên Supabase Storage
- Tạo record trong table books
- Trigger pipeline: chunk → embed → store vectors
"""
import asyncio
import unicodedata
import re
from core.supabase_client import get_supabase
from core.config import settings
from .pdf_processor import process_pdf, TextChunk
from .embedding import embed_batch


STORAGE_BUCKET = "books"


def _sanitize_filename(filename: str) -> str:
    """
    Chuyển filename về dạng ASCII an toàn cho Supabase Storage.
    Ví dụ: 'Bồ Đề Đạt Ma.pdf' → 'Bo_De_Dat_Ma.pdf'
    """
    # Normalize unicode: phân rã ký tự có dấu thành base + diacritic
    normalized = unicodedata.normalize('NFD', filename)
    # Loại bỏ diacritic marks (combining characters)
    ascii_str = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    # Thay đ / Đ → d (không bị xử lý bởi NFD)
    ascii_str = ascii_str.replace('đ', 'd').replace('Đ', 'D')
    # Thay kỹ tự không phải alphanumeric/dot/dash bằng _
    ascii_str = re.sub(r'[^a-zA-Z0-9._-]', '_', ascii_str)
    # Collapse nhiều _ liên tiếp
    ascii_str = re.sub(r'_+', '_', ascii_str)
    return ascii_str.strip('_')


async def create_book_record(
    pdf_bytes: bytes,
    filename: str,
    title: str,
    author: str | None = None,
    publisher: str | None = None,
    published_year: str | None = None,
    category: str | None = None,
    page_size: str | None = None,
    description: str | None = None,
    language: str = "vi",
) -> str:
    """
    Bước 1 (nhanh): Upload PDF lên Storage + tạo book record.
    Trả về book_id ngay để frontend có thể poll status.
    """
    supabase = get_supabase()

    safe_filename = _sanitize_filename(filename)
    file_path = f"pdfs/{safe_filename}"

    supabase.storage.from_(STORAGE_BUCKET).upload(
        path=file_path,
        file=pdf_bytes,
        file_options={"content-type": "application/pdf", "upsert": "true"}
    )

    book_result = supabase.table("books").insert({
        "title": title,
        "author": author,
        "publisher": publisher,
        "published_year": published_year,
        "category": category,
        "page_size": page_size,
        "description": description,
        "language": language,
        "file_path": file_path,
        "file_size": len(pdf_bytes),
        "status": "processing",
    }).execute()

    return book_result.data[0]["id"]


async def run_ingestion_pipeline(book_id: str, pdf_bytes: bytes) -> None:
    """
    Bước 2 (nặng, chạy nền): PDF → chunk → embed → store vectors.
    Cập nhật book status khi hoàn tất.
    """
    supabase = get_supabase()
    try:
        chunks, total_pages = process_pdf(pdf_bytes)
        if not chunks:
            raise ValueError("Không trích xuất được nội dung từ PDF")

        texts = [c.content for c in chunks]
        embeddings = await embed_batch(texts)
        await _store_chunks(book_id, chunks, embeddings)

        # Trích xuất ảnh bìa
        from .metadata_extractor import get_cover_image_bytes, generate_ai_summary
        cover_bytes = get_cover_image_bytes(pdf_bytes)
        cover_url = None
        if cover_bytes:
            cover_path = f"{book_id}.jpeg"
            supabase.storage.from_("covers").upload(
                path=cover_path,
                file=cover_bytes,
                file_options={"content-type": "image/jpeg", "upsert": "true"}
            )
            cover_url = supabase.storage.from_("covers").get_public_url(cover_path)
            if isinstance(cover_url, dict):
                 cover_url = cover_url.get('publicURL', cover_url.get('publicUrl'))
            if not cover_url:
                cover_url = f"{supabase.supabase_url}/storage/v1/object/public/covers/{cover_path}"

        # Tạo AI summary
        ai_summary = await generate_ai_summary(pdf_bytes)

        update_data = {
            "status": "ready",
            "total_pages": total_pages,
        }
        if cover_url:
            update_data["cover_url"] = cover_url
        if ai_summary:
            update_data["ai_summary"] = ai_summary

        supabase.table("books").update(update_data).eq("id", book_id).execute()

    except Exception as e:
        print(f"Ingestion pipeline error: {e}")
        supabase.table("books").update({"status": "error"}).eq("id", book_id).execute()
        # Vẫn reraise exception để có log chi tiết nếu cần
        raise e


# Giữ lại hàm cũ để backward compatibility
async def upload_and_ingest(
    pdf_bytes: bytes,
    filename: str,
    title: str,
    author: str | None = None,
    publisher: str | None = None,
    published_year: str | None = None,
    description: str | None = None,
    language: str = "vi",
) -> str:
    book_id = await create_book_record(pdf_bytes, filename, title, author, publisher, published_year, description, language)
    await run_ingestion_pipeline(book_id, pdf_bytes)
    return book_id



async def _store_chunks(
    book_id: str,
    chunks: list[TextChunk],
    embeddings: list[list[float]]
) -> None:
    """Insert chunks + embeddings vào Supabase theo batches."""
    supabase = get_supabase()
    batch_size = 50  # Supabase recommend batch nhỏ để tránh timeout

    rows = []
    for chunk, embedding in zip(chunks, embeddings):
        rows.append({
            "book_id": book_id,
            "chunk_index": chunk.chunk_index,
            "page_number": chunk.page_number,
            "content": chunk.content,
            "embedding": embedding,
            "token_count": chunk.token_count,
        })

    # Insert theo batches
    for i in range(0, len(rows), batch_size):
        batch = rows[i: i + batch_size]
        supabase.table("book_chunks").insert(batch).execute()
        await asyncio.sleep(0.05)  # nhỏ delay tránh rate limit


def get_book(book_id: str) -> dict | None:
    """Lấy metadata của sách."""
    supabase = get_supabase()
    result = supabase.table("books").select("*").eq("id", book_id).execute()
    return result.data[0] if result.data else None


def list_books() -> list[dict]:
    """Lấy danh sách tất cả sách."""
    supabase = get_supabase()
    result = (
        supabase.table("books")
        .select("id, title, author, publisher, published_year, description, language, cover_url, file_path, file_size, total_pages, status, created_at")
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


def delete_book(book_id: str) -> None:
    """Xóa sách và tất cả chunks liên quan."""
    supabase = get_supabase()
    # Cascade delete sẽ xóa chunks tự động (do foreign key)
    book = get_book(book_id)
    if book:
        # Xóa file trong Storage
        try:
            supabase.storage.from_(STORAGE_BUCKET).remove([book["file_path"]])
        except Exception:
            pass
        supabase.table("books").delete().eq("id", book_id).execute()
