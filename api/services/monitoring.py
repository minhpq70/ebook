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


def is_memory_guard_tripped() -> bool:
    """Trả về True nếu heap Python vượt hard limit cấu hình."""
    if not settings.memory_monitor_enabled:
        return False
    if settings.memory_hard_limit_mb <= 0 or not tracemalloc.is_tracing():
        return False
    current_bytes, _ = tracemalloc.get_traced_memory()
    current_mb = current_bytes / (1024 * 1024)
    return current_mb >= settings.memory_hard_limit_mb
