"""
Admin Router
- GET  /admin/config        — Lấy cấu hình AI hiện tại + danh sách providers
- PUT  /admin/config        — Cập nhật provider/model
- GET  /admin/logs          — 100 dòng log gần nhất
- PATCH /admin/books/{id}   — Chỉnh metadata sách
"""
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel

from core.auth import require_admin
from core.supabase_client import get_supabase
from services.ai_config_service import (
    AI_PROVIDERS, get_ai_config, update_ai_config
)

router = APIRouter(prefix="/admin", tags=["Admin"])

LOG_FILE = Path(__file__).parent.parent / "logs" / "queries.log"


# ── Schemas ───────────────────────────────────────────────────────────────────

class UpdateConfigRequest(BaseModel):
    provider: str
    chat_model: str
    embedding_model: str


class UpdateBookMetaRequest(BaseModel):
    title: str | None = None
    author: str | None = None
    publisher: str | None = None
    published_year: str | None = None
    category: str | None = None
    page_size: str | None = None
    description: str | None = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/config")
def get_config(_: dict = Depends(require_admin)):
    """Lấy cấu hình AI hiện tại và toàn bộ danh sách provider/model."""
    return {
        "current": get_ai_config(),
        "providers": AI_PROVIDERS,
    }


@router.put("/config")
def put_config(req: UpdateConfigRequest, _: dict = Depends(require_admin)):
    """Cập nhật provider + model. Hệ thống sẽ dùng model mới cho request tiếp theo."""
    if req.provider not in AI_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Provider không hợp lệ: {req.provider}")
    updated = update_ai_config(req.provider, req.chat_model, req.embedding_model)
    return {"message": "Cập nhật cấu hình thành công", "config": updated}


@router.get("/logs")
def get_logs(lines: int = 100, _: dict = Depends(require_admin)):
    """Đọc N dòng gần nhất từ file queries.log."""
    if not LOG_FILE.exists():
        return {"logs": [], "total": 0, "note": "Chưa có log nào"}

    all_lines = LOG_FILE.read_text(encoding="utf-8").strip().splitlines()
    recent = all_lines[-lines:][::-1]  # mới nhất lên đầu

    parsed = []
    for line in recent:
        parts = line.split("\t")
        if len(parts) >= 2:
            entry = {"timestamp": parts[0]}
            for part in parts[1:]:
                if "=" in part:
                    k, _, v = part.partition("=")
                    entry[k] = v
            parsed.append(entry)

    return {"logs": parsed, "total": len(all_lines)}


@router.patch("/books/{book_id}")
def update_book_meta(
    book_id: str,
    req: UpdateBookMetaRequest,
    _: dict = Depends(require_admin),
):
    """Chỉnh sửa metadata của sách (chỉ Admin)."""
    supabase = get_supabase()

    update_data = {k: v for k, v in req.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="Không có trường nào để cập nhật")

    result = supabase.table("books").update(update_data).eq("id", book_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Không tìm thấy sách")

    return {"message": "Cập nhật thành công", "book": result.data[0]}


@router.post("/books/{book_id}/reingest")
async def reingest_book(
    book_id: str,
    background_tasks: BackgroundTasks,
    _: dict = Depends(require_admin),
):
    """
    Re-ingest sách: xóa chunks cũ và trích xuất lại bằng pypdf.
    """
    from services import ingestion

    supabase = get_supabase()
    book = ingestion.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Không tìm thấy sách")

    # Đánh dấu đang xử lý
    supabase.table("books").update({"status": "processing"}).eq("id", book_id).execute()

    async def _do_reingest():
        import logging
        import traceback
        logger = logging.getLogger("ebook.reingest")
        try:
            # Lấy danh sách ID các chunks cũ
            r = supabase.table("book_chunks").select("id").eq("book_id", book_id).execute()
            chunk_ids = [row["id"] for row in r.data] if r.data else []
            
            # Xóa từng batch để tránh timeout
            batch_size = 50
            for i in range(0, len(chunk_ids), batch_size):
                batch = chunk_ids[i:i+batch_size]
                supabase.table("book_chunks").delete().in_("id", batch).execute()
                logger.info("Đã xóa chunks %d - %d / %d", i+1, i+len(batch), len(chunk_ids))
            
            logger.info("Đã xóa hoàn toàn chunks cũ cho sách %s", book_id)

            # Download PDF
            file_path = book.get("file_path")
            pdf_bytes = supabase.storage.from_("books").download(file_path)
            logger.info("Downloaded PDF: %d bytes", len(pdf_bytes))

            # Chạy lại pipeline ingestion
            await ingestion.run_ingestion_pipeline(book_id, pdf_bytes)
            logger.info("Hoàn thành re-ingest cho sách %s", book_id)
        except Exception as e:
            logger.error("Lỗi reingest sách %s: %s", book_id, e)
            logger.debug(traceback.format_exc())
            supabase.table("books").update({"status": "error"}).eq("id", book_id).execute()

    background_tasks.add_task(_do_reingest)

    return {"message": f"Đang re-ingest sách '{book['title']}'. Quá trình này mất vài phút.", "book_id": book_id}
