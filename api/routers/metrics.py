"""
Runtime Metrics Router
- Expose runtime snapshot cho monitoring nội bộ
"""
from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from core.auth import require_admin
from core.redis_client import get_cache_manager
from services.error_tracker import get_recent_errors, get_error_summary, clear_errors
from services.metrics_analytics import build_metrics_analytics
from services.metrics_registry import get_metrics_registry
from services.monitoring import get_runtime_snapshot
from services.prometheus_exporter import render_prometheus_metrics

router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.get("/runtime")
async def runtime_metrics():
    """Lấy snapshot runtime hiện tại."""
    return get_runtime_snapshot()


@router.get("/summary")
async def metrics_summary(_: dict = Depends(require_admin)):
    """Tổng hợp metrics runtime/request/query/cache/ingestion."""
    return get_metrics_registry().snapshot()


@router.get("/analytics")
async def metrics_analytics(_: dict = Depends(require_admin)):
    """Analytics suy diễn từ metrics snapshot hiện tại."""
    return build_metrics_analytics(get_metrics_registry().snapshot())


@router.get("/persisted")
async def persisted_metrics(_: dict = Depends(require_admin)):
    """Đọc snapshot metrics persisted gần nhất từ Redis."""
    snapshot = await get_cache_manager().get_metrics_snapshot()
    return {"snapshot": snapshot}


@router.get("/prometheus", response_class=PlainTextResponse)
async def prometheus_metrics(_: dict = Depends(require_admin)):
    """Export metrics dạng Prometheus text exposition."""
    return render_prometheus_metrics(
        metrics_snapshot=get_metrics_registry().snapshot(),
        runtime_snapshot=get_runtime_snapshot(),
    )


@router.get("/errors")
async def recent_errors(limit: int = 50, _: dict = Depends(require_admin)):
    """Lấy danh sách lỗi gần nhất từ in-memory buffer."""
    return {"errors": get_recent_errors(limit), "summary": get_error_summary()}


@router.get("/errors/summary")
async def error_summary(_: dict = Depends(require_admin)):
    """Thống kê tổng hợp lỗi theo loại."""
    return get_error_summary()


@router.post("/errors/clear")
async def clear_error_buffer(_: dict = Depends(require_admin)):
    """Reset error buffer và counters."""
    clear_errors()
    return {"message": "Đã xóa buffer lỗi"}
