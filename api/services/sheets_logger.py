"""
Google Sheets Logger
Ghi log câu hỏi người dùng (query, tokens, chi phí) vào Google Sheet.

LƯU Ý RENDER:
  - Cần upload file service_account.json lên Render dưới dạng Secret File
    (Dashboard → Service → Environment → Secret Files → /etc/secrets/service_account.json)
  - Hoặc encode JSON thành base64 rồi lưu vào env var GOOGLE_SA_JSON
"""
import json
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Cấu hình ──────────────────────────────────────────────────────────────────
SHEET_ID = "1zRUPQikOBC3Fc11R2SYVdhsUcGKVlhJXRwJs9PvcNdk"
SHEET_TAB = "Logs"          # tên tab trong spreadsheet
SA_FILE_PATHS = [            # tìm file theo thứ tự ưu tiên
    Path(__file__).parent.parent / "service_account.json",   # local
    Path("/etc/secrets/service_account.json"),                # Render Secret File
]
# ─────────────────────────────────────────────────────────────────────────────

_sheet = None   # cache worksheet object


def _get_sa_path() -> Optional[Path]:
    for p in SA_FILE_PATHS:
        if p.exists():
            return p
    return None


def _init_sheet():
    """Khởi tạo kết nối tới Google Sheet (lazy, chỉ chạy 1 lần)."""
    global _sheet
    if _sheet is not None:
        return _sheet

    try:
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
        ]

        sa_path = _get_sa_path()
        if sa_path is None:
            logger.warning("sheets_logger: không tìm thấy service_account.json, bỏ qua Sheets logging")
            return None

        creds = Credentials.from_service_account_file(str(sa_path), scopes=scopes)
        gc = gspread.authorize(creds)
        spreadsheet = gc.open_by_key(SHEET_ID)

        # Tìm hoặc tạo tab "Logs"
        try:
            ws = spreadsheet.worksheet(SHEET_TAB)
        except gspread.WorksheetNotFound:
            ws = spreadsheet.add_worksheet(title=SHEET_TAB, rows=10000, cols=10)
            # Ghi header
            ws.append_row([
                "Thời gian", "Loại", "Book ID", "Task Type",
                "Tokens", "Chi phí (USD)", "Câu hỏi"
            ], value_input_option="RAW")

        _sheet = ws
        logger.info("sheets_logger: kết nối Google Sheets thành công")
        return _sheet

    except Exception as e:
        logger.error("sheets_logger: lỗi khởi tạo — %s", e)
        return None


async def log_query(
    mode: str,          # "QUERY" hoặc "STREAM"
    book_id: str,
    task_type: str,
    query: str,
    tokens_used: Optional[int] = None,
    cost_usd: Optional[str] = None,
):
    """Ghi 1 dòng log vào Google Sheet (chạy bất đồng bộ, không block request)."""
    def _write():
        try:
            ws = _init_sheet()
            if ws is None:
                return
            row = [
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                mode,
                book_id[:8] + "…",     # rút ngắn cho dễ đọc
                task_type,
                tokens_used if tokens_used is not None else "stream",
                cost_usd if cost_usd is not None else "stream",
                query,
            ]
            ws.append_row(row, value_input_option="RAW")
        except Exception as e:
            logger.error("sheets_logger: lỗi ghi row — %s", e)

    # Chạy trong thread pool để không block event loop
    await asyncio.to_thread(_write)
