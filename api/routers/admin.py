"""
Admin Router
- GET  /admin/config        — Lấy cấu hình AI hiện tại + danh sách providers
- PUT  /admin/config        — Cập nhật provider/model
- GET  /admin/logs          — 100 dòng log gần nhất
- PATCH /admin/books/{id}   — Chỉnh metadata sách
"""
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from core.auth import require_admin
from core.supabase_client import get_supabase
from core.openai_client import get_available_providers
from services.ai_config_service import (
    AI_PROVIDERS, get_ai_config, update_ai_config, get_embedding_providers
)
from services.ingestion_queue import enqueue_ingestion_job

router = APIRouter(prefix="/admin", tags=["Admin"])

LOG_FILE = Path(__file__).parent.parent / "logs" / "queries.log"


# ── Schemas ───────────────────────────────────────────────────────────────────

class UpdateConfigRequest(BaseModel):
    provider: str
    chat_model: str
    embedding_provider: str
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
    """Lấy cấu hình AI hiện tại, danh sách providers, và trạng thái API key."""
    return {
        "current": get_ai_config(),
        "providers": AI_PROVIDERS,
        "embedding_providers": get_embedding_providers(),
        "available": get_available_providers(),
    }


@router.put("/config")
def put_config(req: UpdateConfigRequest, _: dict = Depends(require_admin)):
    """Cập nhật provider + model. Ghi vào .env và restart để áp dụng."""
    if req.provider not in AI_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Provider không hợp lệ: {req.provider}")
    updated = update_ai_config(req.provider, req.chat_model, req.embedding_provider, req.embedding_model)
    
    # Restart API để reload settings từ .env mới
    import subprocess
    try:
        subprocess.Popen(["pm2", "restart", "ebook-api", "--silent"], 
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass  # Nếu không có pm2, bỏ qua — admin phải restart thủ công
    
    return {"message": "Cập nhật cấu hình thành công. Server sẽ restart trong vài giây.", "config": updated}


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

    await ingestion.mark_book_queued(book_id, "Đã đưa vào hàng đợi re-ingest")
    await enqueue_ingestion_job(book_id=book_id, job_type="reingest")

    return {"message": f"Sách '{book['title']}' đã vào hàng đợi re-ingest.", "book_id": book_id}
