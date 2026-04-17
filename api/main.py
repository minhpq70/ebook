"""
FastAPI Application Entry Point
Ebook Platform — Private RAG Backend (POC)
"""
import asyncio
import gc
import logging
import logging.handlers
import time
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from core.config import settings
from core.redis_client import get_cache_manager
from routers import books, rag, auth, admin, categories, metrics
from services.metrics_registry import get_metrics_registry
from services.monitoring import get_runtime_snapshot, is_memory_guard_tripped, start_runtime_monitoring

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

# Rate limiting setup
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

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
app.include_router(metrics.router, prefix="/api/v1")


async def _persist_metrics_periodically() -> None:
    """Persist snapshot metrics định kỳ sang Redis."""
    cache_manager = get_cache_manager()
    registry = get_metrics_registry()
    interval = max(5, settings.metrics_persist_interval_seconds)

    while True:
        await asyncio.sleep(interval)
        await cache_manager.set_metrics_snapshot(registry.snapshot())


@app.on_event("startup")
async def configure_runtime() -> None:
    """Áp dụng tuning nhẹ cho GC để giảm peak memory khi ingest."""
    gc.set_threshold(
        settings.gc_threshold_gen0,
        settings.gc_threshold_gen1,
        settings.gc_threshold_gen2,
    )
    start_runtime_monitoring()
    persisted_snapshot = await get_cache_manager().get_metrics_snapshot()
    if persisted_snapshot:
        get_metrics_registry().restore(persisted_snapshot)
    app.state.metrics_persist_task = asyncio.create_task(_persist_metrics_periodically())


@app.on_event("shutdown")
async def persist_runtime_metrics_on_shutdown() -> None:
    """Persist snapshot cuối cùng khi app shutdown."""
    task = getattr(app.state, "metrics_persist_task", None)
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    await get_cache_manager().set_metrics_snapshot(get_metrics_registry().snapshot())


@app.middleware("http")
async def memory_guard_middleware(request: Request, call_next):
    """
    Chặn request nặng khi Python heap vượt hard limit.
    Không chặn health/metrics để vẫn quan sát được trạng thái hệ thống.
    """
    exempt_paths = {"/health", "/api/v1/metrics/runtime"}
    if request.url.path not in exempt_paths and is_memory_guard_tripped():
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Máy chủ đang quá tải bộ nhớ, vui lòng thử lại sau",
                "runtime": get_runtime_snapshot(),
            },
        )
    return await call_next(request)


@app.middleware("http")
async def collect_request_metrics(request: Request, call_next):
    """Thu thập latency và status code cho mọi HTTP request."""
    started_at = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        get_metrics_registry().record_request(
            path=request.url.path,
            method=request.method,
            status_code=status_code,
            latency_ms=(time.perf_counter() - started_at) * 1000,
        )


# Fix: CORS middleware của Starlette không tự thêm header vào error responses.
# Handler này đảm bảo 401/403 vẫn có Access-Control-Allow-Origin
# để trình duyệt không báo nhầm "CORS policy" khi thực ra là Unauthorized.
from fastapi.exceptions import HTTPException as FastAPIHTTPException

@app.exception_handler(FastAPIHTTPException)
async def cors_aware_http_exception_handler(request: Request, exc: FastAPIHTTPException):
    origin = request.headers.get("origin", "")
    # Chỉ trả về CORS header nếu origin nằm trong whitelist
    allowed = origin if origin in settings.cors_origins else ""
    headers = {}
    if allowed:
        headers["Access-Control-Allow-Origin"] = allowed
        headers["Access-Control-Allow-Credentials"] = "true"
    
    # Sanitize error message cho production
    error_detail = exc.detail
    if settings.app_env == "production":
        # Ẩn chi tiết internal errors
        if exc.status_code >= 500:
            error_detail = "Lỗi máy chủ nội bộ"
        # Giữ lại client errors nhưng loại bỏ info nhạy cảm
        elif exc.status_code >= 400:
            # Có thể thêm logic để filter sensitive info
            pass
    
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": error_detail},
        headers=headers,
    )


# Global exception handler cho tất cả unhandled exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    origin = request.headers.get("origin", "")
    allowed = origin if origin in settings.cors_origins else ""
    headers = {}
    if allowed:
        headers["Access-Control-Allow-Origin"] = allowed
        headers["Access-Control-Allow-Credentials"] = "true"
    
    # Log internal error
    logging.error(f"Unhandled exception: {exc}", exc_info=True)
    
    # Return sanitized error
    error_detail = "Lỗi máy chủ nội bộ" if settings.app_env == "production" else str(exc)
    
    return JSONResponse(
        status_code=500,
        content={"detail": error_detail},
        headers=headers,
    )


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    runtime = get_runtime_snapshot()
    return {
        "status": "ok",
        "service": "ebook-platform-api",
        "version": "0.1.0",
        "env": settings.app_env,
        "runtime": runtime,
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
