"""
FastAPI Application Entry Point
Ebook Platform — Private RAG Backend (POC)
"""
import logging
import logging.handlers
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import settings
from routers import books, rag, auth, admin, categories

# ── Logging setup ────────────────────────────────────────────────────────────
# LƯU Ý TRIỂN KHAI:
#   - Localhost : file log tồn tại lâu dài tại api/logs/
#   - Render    : filesystem là ephemeral → file log BỊ XÓA khi redeploy/restart
#                 Nếu cần log lâu dài trên Render, phải dùng dịch vụ ngoài
#                 (ví dụ: Logtail, Papertrail, hoặc ghi vào Supabase)
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

query_logger = logging.getLogger("rag.queries")
query_logger.setLevel(logging.INFO)

_handler = logging.handlers.TimedRotatingFileHandler(
    filename=LOG_DIR / "queries.log",
    when="midnight",        # tạo file mới mỗi đêm (queries.log.YYYY-MM-DD)
    backupCount=0,          # = 0 → GIỮ TẤT CẢ file cũ, không xóa
    encoding="utf-8",
)
_handler.setFormatter(logging.Formatter(
    "%(asctime)s\t%(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
))
query_logger.addHandler(_handler)
query_logger.propagate = False  # không in thêm ra console uvicorn
# ─────────────────────────────────────────────────────────────────────────────



app = FastAPI(
    title="Ebook Platform API",
    description="Nền tảng xuất bản điện tử với Private RAG — POC",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — cho phép Next.js frontend gọi API
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(books.router, prefix="/api/v1")
app.include_router(rag.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(categories.router, prefix="/api/v1")


# Fix: CORS middleware của Starlette không tự thêm header vào error responses.
# Handler này đảm bảo 401/403 vẫn có Access-Control-Allow-Origin
# để trình duyệt không báo nhầm "CORS policy" khi thực ra là Unauthorized.
from fastapi.exceptions import HTTPException as FastAPIHTTPException

@app.exception_handler(FastAPIHTTPException)
async def cors_aware_http_exception_handler(request: Request, exc: FastAPIHTTPException):
    origin = request.headers.get("origin", "*")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers={
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
        },
    )


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "ebook-platform-api",
        "version": "0.1.0",
        "env": settings.app_env,
    }


@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "Ebook Platform API",
        "docs": "/docs",
        "health": "/health",
        "test_chat": "/test",
    }


@app.get("/test", tags=["Test"], include_in_schema=False)
async def test_chat_page():
    """Phục vụ trang test chat AI — truy cập http://localhost:8001/test"""
    from fastapi.responses import FileResponse
    html_path = Path(__file__).parent / "test_chat.html"
    if html_path.exists():
        return FileResponse(html_path, media_type="text/html")
    return JSONResponse({"error": "test_chat.html not found"}, status_code=404)

