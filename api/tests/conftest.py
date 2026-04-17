"""
Pytest conftest — Setup cho test environment.
Mock các external dependencies nặng để test thuần logic.
"""
import sys
import os
from unittest.mock import MagicMock

# Thêm project root vào path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set env vars trước khi import config
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-unit-tests-only-32chars!")
os.environ.setdefault("SUPABASE_URL", "https://fake.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "fake-key")
os.environ.setdefault("OPENAI_API_KEY", "fake-key")

# Mock heavy modules chưa cài locally để tránh ImportError khi collecting
# Chỉ các module dùng cho I/O hoặc cloud — logic thuần vẫn dùng thật
for mod_name in [
    "fitz",
    "pytesseract",
    "redis",
    "redis.asyncio",
    "supabase",
    "langchain_text_splitters",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()
