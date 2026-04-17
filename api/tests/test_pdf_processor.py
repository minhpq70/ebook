"""
Unit Tests — PDF Processor (pure functions only)
Test các hàm xử lý text và kiểm tra encoding tiếng Việt.
Không import chunk_pages vì phụ thuộc langchain_text_splitters (mocked).
"""
import pytest
from services.pdf_processor import (
    _clean_text,
    _count_tokens,
    is_valid_vietnamese_text_optimized,
)


# ── _clean_text ───────────────────────────────────────────────────────────────

class TestCleanText:
    def test_removes_control_characters(self):
        text = "Hello\x00World\x01!\x7f"
        result = _clean_text(text)
        # Control chars are removed (not replaced with space)
        assert "\x00" not in result
        assert "\x01" not in result
        assert "\x7f" not in result

    def test_collapses_whitespace(self):
        text = "Xin   chào    bạn"
        assert _clean_text(text) == "Xin chào bạn"

    def test_collapses_excessive_newlines(self):
        text = "A\n\n\n\n\nB"
        assert _clean_text(text) == "A\n\nB"

    def test_preserves_double_newlines(self):
        text = "Đoạn 1\n\nĐoạn 2"
        assert _clean_text(text) == "Đoạn 1\n\nĐoạn 2"

    def test_strips_leading_trailing(self):
        assert _clean_text("  hello  ") == "hello"

    def test_empty_string(self):
        assert _clean_text("") == ""

    def test_vietnamese_diacritics_preserved(self):
        text = "Việt Nam đẹp lắm"
        assert _clean_text(text) == "Việt Nam đẹp lắm"

    def test_tabs_collapsed(self):
        text = "A\t\tB\t\tC"
        assert _clean_text(text) == "A B C"


# ── _count_tokens ─────────────────────────────────────────────────────────────

class TestCountTokens:
    def test_english_short(self):
        count = _count_tokens("Hello world")
        assert count == 2

    def test_vietnamese_text(self):
        count = _count_tokens("Xin chào thế giới")
        assert count > 0

    def test_empty_string(self):
        assert _count_tokens("") == 0

    def test_long_text_has_more_tokens(self):
        short = _count_tokens("Hello")
        long = _count_tokens("Hello world, this is a longer sentence with many tokens")
        assert long > short


# ── is_valid_vietnamese_text_optimized ──────────────────────────────────────────────────

class TestVietnameseTextValidation:
    def test_valid_vietnamese(self):
        text = "Đây là một đoạn văn bản tiếng Việt có dấu đầy đủ, bao gồm các ký tự đặc biệt như ă, ô, ơ, ư."
        assert is_valid_vietnamese_text_optimized(text) is True

    def test_broken_encoding(self):
        """Text bị lỗi font VNI/TCVN3 chứa nhiều ký tự lạ."""
        text = "§µ¶·¹¨»¾¼½Æ©ÇÊÈÉË®ÌÐÎÏÑªÒÕÓÔÖ×ÝØÜÞßãä«åæç¬ñõøö÷ùúûüþ" * 3
        assert is_valid_vietnamese_text_optimized(text) is False

    def test_short_text_fails(self):
        """Text quá ngắn → fail."""
        assert is_valid_vietnamese_text_optimized("short") is False

    def test_empty_fails(self):
        assert is_valid_vietnamese_text_optimized("") is False

    def test_english_text_fails(self):
        """English text không có ký tự tiếng Việt → fail."""
        text = "This is a normal English text without any suspicious characters at all for testing purposes here."
        assert is_valid_vietnamese_text_optimized(text) is False

    def test_mixed_valid_vietnamese_english(self):
        text = "Kinh tế Việt Nam (GDP) tăng trưởng 6.5% trong năm 2024, theo báo cáo của World Bank."
        assert is_valid_vietnamese_text_optimized(text) is True
