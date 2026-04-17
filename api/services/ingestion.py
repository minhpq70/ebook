"""
Book Ingestion Service
- Upload PDF lên Supabase Storage
- Tạo record trong table books
- Trigger pipeline: chunk → embed → store vectors
"""
from __future__ import annotations

import asyncio
import logging
import unicodedata
import re
import time
from core.supabase_client import get_supabase
from core.redis_client import get_cache_manager
from core.config import settings
from .metrics_registry import get_metrics_registry
from .pdf_processor import _count_tokens, chunk_pages, get_pdf_page_count, iter_pdf_page_batches, TextChunk
from .embedding import embed_batch

logger = logging.getLogger("ebook.ingestion")


STORAGE_BUCKET = "books"


async def _update_ingestion_progress(
    book_id: str,
    *,
    status: str,
    message: str,
    total_pages: int | None = None,
    processed_pages: int | None = None,
    total_chunks: int | None = None,
    stored_chunks: int | None = None,
) -> None:
    cache_manager = get_cache_manager()
    progress = {
        "book_id": book_id,
        "status": status,
        "message": message,
        "total_pages": total_pages,
        "processed_pages": processed_pages,
        "total_chunks": total_chunks,
        "stored_chunks": stored_chunks,
    }
    await cache_manager.set_ingestion_progress(book_id, progress)


async def get_ingestion_progress(book_id: str) -> dict | None:
    """Lấy trạng thái ingestion gần nhất từ cache."""
    return await get_cache_manager().get_ingestion_progress(book_id)


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
    import asyncio
    supabase = get_supabase()
    started_at = time.perf_counter()
    metrics = get_metrics_registry()
    try:
        total_pages = await asyncio.to_thread(get_pdf_page_count, pdf_bytes)
        await _update_ingestion_progress(
            book_id,
            status="processing",
            message="Đang phân tích PDF và trích xuất nội dung",
            total_pages=total_pages,
            processed_pages=0,
            total_chunks=0,
            stored_chunks=0,
        )

        total_chunks = 0
        stored_chunks = 0
        next_chunk_index = 0

        for page_batch in iter_pdf_page_batches(pdf_bytes, settings.pdf_page_batch_size):
            chunks = chunk_pages(page_batch, start_chunk_index=next_chunk_index)
            if chunks:
                texts = [chunk.content for chunk in chunks]
                embeddings = await embed_batch(texts, batch_size=settings.embedding_batch_size)
                await _store_chunks(book_id, chunks, embeddings)
                total_chunks += len(chunks)
                stored_chunks += len(chunks)
                next_chunk_index += len(chunks)

            processed_pages = page_batch[-1]["page_number"] if page_batch else 0
            await _update_ingestion_progress(
                book_id,
                status="processing",
                message="Đang chunk, embed và lưu dữ liệu theo lô",
                total_pages=total_pages,
                processed_pages=processed_pages,
                total_chunks=total_chunks,
                stored_chunks=stored_chunks,
            )

        from .metadata_extractor import extract_toc
        toc_text = await asyncio.to_thread(extract_toc, pdf_bytes)
        if toc_text:
            toc_chunk = TextChunk(
                content=toc_text,
                page_number=-1,
                chunk_index=next_chunk_index,
                token_count=_count_tokens(toc_text),
            )
            toc_embedding = await embed_batch([toc_chunk.content], batch_size=1)
            await _store_chunks(book_id, [toc_chunk], toc_embedding)
            total_chunks += 1
            stored_chunks += 1

        # Trích xuất ảnh bìa (cũng CPU-bound — render page thành image)
        from .metadata_extractor import get_cover_image_bytes, generate_ai_summary
        cover_bytes = await asyncio.to_thread(get_cover_image_bytes, pdf_bytes)
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
        metrics.record_ingestion(
            "ready",
            latency_ms=(time.perf_counter() - started_at) * 1000,
            chunks=stored_chunks,
        )
        await _update_ingestion_progress(
            book_id,
            status="ready",
            message="Hoàn tất ingestion",
            total_pages=total_pages,
            processed_pages=total_pages,
            total_chunks=total_chunks,
            stored_chunks=stored_chunks,
        )

    except Exception as e:
        logger.error("Ingestion pipeline error for book %s: %s", book_id, e, exc_info=True)
        supabase.table("books").update({"status": "error"}).eq("id", book_id).execute()
        metrics.record_ingestion("error")
        await _update_ingestion_progress(
            book_id,
            status="error",
            message=str(e),
        )
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
    batch_size = settings.ingestion_store_batch_size

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
        .select("*")
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
        except Exception as e:
            logger.warning("Không thể xóa file storage cho book %s: %s", book_id, e)
        supabase.table("books").delete().eq("id", book_id).execute()
