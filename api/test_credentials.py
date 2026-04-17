#!/usr/bin/env python3
"""
Test Google Sheets credentials
Chạy script này để verify credentials hoạt động đúng.
"""

import os
import sys
import base64
import json
from pathlib import Path

# Add current directory to path
sys.path.append(str(Path(__file__).parent))

def test_credentials():
    """Test loading và validate Google credentials."""
    try:
        from services.sheets_logger import _get_credentials
        creds = _get_credentials()

        if creds is None:
            print("❌ Không tìm thấy credentials")
            return False

        # Test authenticate
        import gspread
        gc = gspread.authorize(creds)

        # Test open spreadsheet
        from core.config import settings
        spreadsheet = gc.open_by_key(settings.sheet_id)
        print("✅ Credentials hoạt động tốt!")
        print(f"📊 Connected to sheet: {spreadsheet.title}")
        return True

    except Exception as e:
        print(f"❌ Lỗi test credentials: {e}")
        return False

if __name__ == "__main__":
    success = test_credentials()
    sys.exit(0 if success else 1)