"""
Google Sheets Logger
Ghi log câu hỏi người dùng (query, tokens, chi phí) vào Google Sheet.

CÁCH THIẾT LẬP CREDENTIALS (chọn 1 trong 3):

1. Environment variable GOOGLE_SA_JSON (khuyên dùng cho production):
   - Tạo service account key JSON từ Google Cloud Console
   - Chạy: python convert_sa_json.py (sẽ generate base64 encoded string)
   - Set: GOOGLE_SA_JSON="base64_string" trong .env

2. File service_account.json (development only):
   - Đặt file tại api/service_account.json
   - KHÔNG commit lên git!

3. Google Cloud default credentials (GCP production):
   - Sử dụng GOOGLE_APPLICATION_CREDENTIALS hoặc default service account
   - Tự động detect nếu không có GOOGLE_SA_JSON
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


def _get_credentials():
    """Lấy Google credentials theo thứ tự ưu tiên."""
    import os
    import base64
    
    # 1. Từ environment variable GOOGLE_SA_JSON
    sa_json = os.getenv("GOOGLE_SA_JSON")
    if sa_json:
        try:
            # Thử decode base64 trước
            try:
                json_str = base64.b64decode(sa_json).decode('utf-8')
            except:
                # Nếu không phải base64, coi là JSON string trực tiếp
                json_str = sa_json
            
            creds_dict = json.loads(json_str)
            from google.oauth2.service_account import Credentials
            scopes = ["https://www.googleapis.com/auth/spreadsheets"]
            return Credentials.from_service_account_info(creds_dict, scopes=scopes)
        except Exception as e:
            logger.warning("sheets_logger: lỗi parse GOOGLE_SA_JSON — %s", e)
    
    # 2. Từ file service_account.json
    sa_path = _get_sa_path()
    if sa_path:
        try:
            from google.oauth2.service_account import Credentials
            scopes = ["https://www.googleapis.com/auth/spreadsheets"]
            return Credentials.from_service_account_file(str(sa_path), scopes=scopes)
        except Exception as e:
            logger.warning("sheets_logger: lỗi load từ file — %s", e)
    
    # 3. Từ Google Cloud default credentials
    try:
        from google.auth import default
        creds, _ = default(scopes=["https://www.googleapis.com/auth/spreadsheets"])
        return creds
    except Exception as e:
        logger.warning("sheets_logger: không tìm thấy credentials — %s", e)
    
    return None


def _init_sheet():
    """Khởi tạo kết nối tới Google Sheet (lazy, chỉ chạy 1 lần)."""
    global _sheet
    if _sheet is not None:
        return _sheet

    try:
        import gspread

        creds = _get_credentials()
        if creds is None:
            logger.warning("sheets_logger: không tìm thấy credentials, bỏ qua Sheets logging")
            return None

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
