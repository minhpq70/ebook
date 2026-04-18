"""
Error Tracking Service
- Thu thập và lưu lỗi có cấu trúc vào Supabase table `error_logs`
- In-memory ring buffer cho quick access gần nhất
- Webhook alerting (Slack/Discord/custom) cho lỗi nghiêm trọng
"""
from __future__ import annotations

import asyncio
import logging
import traceback
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from typing import Any
from datetime import datetime, timezone

import httpx

from core.config import settings

logger = logging.getLogger("ebook.error_tracker")

# ── Data ──────────────────────────────────────────────────────────────────────

@dataclass
class ErrorEntry:
    timestamp: str
    level: str  # "error" | "critical"
    path: str
    method: str
    status_code: int
    error_type: str
    message: str
    stack_trace: str | None = None
    user_id: str | None = None
    request_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


# ── Tracker ───────────────────────────────────────────────────────────────────

_BUFFER_SIZE = 200
_error_buffer: deque[dict] = deque(maxlen=_BUFFER_SIZE)
_error_counts: dict[str, int] = {}  # error_type → count


def record_error(
    *,
    exc: Exception,
    path: str = "",
    method: str = "",
    status_code: int = 500,
    user_id: str | None = None,
) -> dict:
    """Ghi nhận lỗi vào buffer + tăng counter. Trả về entry dict."""
    error_type = type(exc).__name__
    entry = ErrorEntry(
        timestamp=datetime.now(timezone.utc).isoformat(),
        level="critical" if status_code >= 500 else "error",
        path=path,
        method=method,
        status_code=status_code,
        error_type=error_type,
        message=str(exc)[:500],
        stack_trace=traceback.format_exc()[-2000:],  # giữ 2000 ký tự cuối
        user_id=user_id,
    )
    entry_dict = asdict(entry)
    _error_buffer.appendleft(entry_dict)
    _error_counts[error_type] = _error_counts.get(error_type, 0) + 1

    # Fire-and-forget persist + alert
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_persist_and_alert(entry_dict))
    except RuntimeError:
        pass  # no event loop — skip async tasks

    return entry_dict


def get_recent_errors(limit: int = 50) -> list[dict]:
    """Lấy N lỗi gần nhất từ in-memory buffer."""
    return list(_error_buffer)[:limit]


def get_error_summary() -> dict:
    """Tổng hợp thống kê lỗi."""
    return {
        "total_errors": sum(_error_counts.values()),
        "error_types": dict(_error_counts),
        "buffer_size": len(_error_buffer),
        "buffer_capacity": _BUFFER_SIZE,
    }


def clear_errors() -> None:
    """Reset buffer và counters — dùng cho testing hoặc admin reset."""
    _error_buffer.clear()
    _error_counts.clear()


# ── Persistence ───────────────────────────────────────────────────────────────

async def _persist_to_db(entry: dict) -> None:
    """Lưu lỗi vào Supabase table `error_logs` (nếu table tồn tại)."""
    try:
        from core.supabase_client import get_supabase
        supabase = get_supabase()
        row = {
            "level": entry["level"],
            "path": entry["path"],
            "method": entry["method"],
            "status_code": entry["status_code"],
            "error_type": entry["error_type"],
            "message": entry["message"][:500],
            "stack_trace": entry.get("stack_trace", "")[:2000],
        }
        supabase.table("error_logs").insert(row).execute()
    except Exception as e:
        # Không để persist lỗi gây thêm lỗi
        logger.debug("Failed to persist error to DB: %s", e)


# ── Alerting ──────────────────────────────────────────────────────────────────

async def _send_webhook_alert(entry: dict) -> None:
    """Gửi alert qua webhook nếu được cấu hình."""
    webhook_url = getattr(settings, "error_webhook_url", "")
    if not webhook_url:
        return

    payload = {
        "text": (
            f"🚨 **{entry['level'].upper()}** on `{entry['method']} {entry['path']}`\n"
            f"**Type:** {entry['error_type']}\n"
            f"**Message:** {entry['message'][:200]}\n"
            f"**Time:** {entry['timestamp']}"
        ),
        # Discord/Slack compatible
        "content": (
            f"🚨 **{entry['level'].upper()}** on `{entry['method']} {entry['path']}`\n"
            f"**Type:** {entry['error_type']}\n"
            f"**Message:** {entry['message'][:200]}"
        ),
    }
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(webhook_url, json=payload)
    except Exception as e:
        logger.debug("Failed to send webhook alert: %s", e)


async def _persist_and_alert(entry: dict) -> None:
    """Persist lỗi vào DB và gửi alert cho lỗi critical."""
    await _persist_to_db(entry)
    if entry["level"] == "critical":
        await _send_webhook_alert(entry)
