"""
Runtime Monitoring Service
- Theo dõi memory Python heap bằng tracemalloc
- Cung cấp snapshot nhẹ cho health/metrics
- Hỗ trợ memory circuit breaker có thể cấu hình
"""
from __future__ import annotations

import gc
import tracemalloc

from core.config import settings

MEMORY_HEAVY_PATH_PREFIXES = (
    "/api/v1/books/upload",
    "/api/v1/rag/query",
    "/api/v1/admin/books/",
)


def start_runtime_monitoring() -> None:
    """Bật tracemalloc một lần ở startup để theo dõi memory hiện tại/đỉnh."""
    if settings.memory_monitor_enabled and not tracemalloc.is_tracing():
        tracemalloc.start(25)


def get_runtime_snapshot() -> dict:
    """Trả về snapshot runtime nhẹ, an toàn để expose qua endpoint nội bộ."""
    current_mb = 0.0
    peak_mb = 0.0
    if tracemalloc.is_tracing():
        current_bytes, peak_bytes = tracemalloc.get_traced_memory()
        current_mb = round(current_bytes / (1024 * 1024), 2)
        peak_mb = round(peak_bytes / (1024 * 1024), 2)

    return {
        "memory": {
            "python_heap_mb": current_mb,
            "python_heap_peak_mb": peak_mb,
            "soft_limit_mb": settings.memory_soft_limit_mb,
            "hard_limit_mb": settings.memory_hard_limit_mb,
        },
        "gc": {
            "counts": gc.get_count(),
            "thresholds": gc.get_threshold(),
        },
        "circuit_breaker": {
            "enabled": settings.memory_monitor_enabled,
            "soft_limit_exceeded": current_mb >= settings.memory_soft_limit_mb > 0,
            "hard_limit_exceeded": current_mb >= settings.memory_hard_limit_mb > 0,
        },
    }


def _current_python_heap_mb() -> float:
    if not tracemalloc.is_tracing():
        return 0.0
    current_bytes, _ = tracemalloc.get_traced_memory()
    return current_bytes / (1024 * 1024)


def get_memory_guard_decision(path: str) -> dict:
    """
    Quyết định guard theo 2 mức:
    - hard: chặn gần như mọi request
    - soft: chỉ chặn các endpoint nặng về memory/CPU
    """
    if not settings.memory_monitor_enabled:
        return {"block": False, "reason": None, "level": "disabled"}

    current_mb = _current_python_heap_mb()
    if settings.memory_hard_limit_mb > 0 and current_mb >= settings.memory_hard_limit_mb:
        return {
            "block": True,
            "reason": "hard_limit",
            "level": "hard",
            "current_mb": round(current_mb, 2),
        }

    is_heavy_path = any(path.startswith(prefix) for prefix in MEMORY_HEAVY_PATH_PREFIXES)
    if (
        is_heavy_path
        and settings.memory_soft_limit_mb > 0
        and current_mb >= settings.memory_soft_limit_mb
    ):
        return {
            "block": True,
            "reason": "soft_limit_heavy_endpoint",
            "level": "soft",
            "current_mb": round(current_mb, 2),
        }

    return {"block": False, "reason": None, "level": "ok", "current_mb": round(current_mb, 2)}


def is_memory_guard_tripped() -> bool:
    """Trả về True nếu heap Python vượt hard limit cấu hình."""
    if not settings.memory_monitor_enabled:
        return False
    if settings.memory_hard_limit_mb <= 0 or not tracemalloc.is_tracing():
        return False
    current_mb = _current_python_heap_mb()
    return current_mb >= settings.memory_hard_limit_mb
