"""
Unit Tests — RAG Engine
Test prompt construction, TOC detection, và context building.
Không cần kết nối OpenAI — chỉ test logic thuần.
"""
import pytest
from models.schemas import ChunkInfo
from services.rag_engine import (
    is_toc_query,
    _build_context_block,
    _build_user_message,
    SYSTEM_PROMPTS,
)


# ── is_toc_query ─────────────────────────────────────────────────────────────

class TestIsTocQuery:
    @pytest.mark.parametrize("query", [
        "Cho xem mục lục",
        "MỤC LỤC của sách là gì?",
        "Liệt kê các chương",
        "danh sách chương",
        "Table of Contents",
        "danh mục nội dung",
        "nội dung chính của sách",
        "cấu trúc sách",
        "bố cục cuốn sách",
        "Outline của sách",
    ])
    def test_detects_toc_queries(self, query: str):
        assert is_toc_query(query) is True

    @pytest.mark.parametrize("query", [
        "Tác giả nói gì về kinh tế?",
        "Giải thích đoạn này",
        "Tóm tắt chương 3",
        "Ý nghĩa của câu nói",
        "So sánh hai quan điểm",
    ])
    def test_ignores_non_toc_queries(self, query: str):
        assert is_toc_query(query) is False

    def test_case_insensitive(self):
        assert is_toc_query("MỤC LỤC") is True
        assert is_toc_query("mục lục") is True


# ── _build_context_block ─────────────────────────────────────────────────────

class TestBuildContextBlock:
    def test_single_chunk(self):
        chunks = [ChunkInfo(id="1", chunk_index=0, page_number=5, content="Nội dung A")]
        result = _build_context_block(chunks)
        assert "[Đoạn 1 (Trang 5)]" in result
        assert "Nội dung A" in result

    def test_multiple_chunks(self):
        chunks = [
            ChunkInfo(id="1", chunk_index=0, page_number=1, content="Đoạn 1"),
            ChunkInfo(id="2", chunk_index=1, page_number=2, content="Đoạn 2"),
        ]
        result = _build_context_block(chunks)
        assert "[Đoạn 1 (Trang 1)]" in result
        assert "[Đoạn 2 (Trang 2)]" in result
        assert "---" in result

    def test_no_page_number(self):
        chunks = [ChunkInfo(id="1", chunk_index=0, page_number=None, content="No page")]
        result = _build_context_block(chunks)
        assert "(Trang" not in result

    def test_empty_chunks(self):
        result = _build_context_block([])
        assert result == ""


# ── _build_user_message ──────────────────────────────────────────────────────

class TestBuildUserMessage:
    def test_qa_message(self):
        msg = _build_user_message("Test query", "Context here", "qa")
        assert "Câu hỏi: Test query" in msg
        assert "Context here" in msg
        assert "Đoạn trích từ sách" in msg

    def test_summarize_chapter_label(self):
        msg = _build_user_message("Tóm tắt", "Context", "summarize_chapter")
        assert "Yêu cầu tóm tắt chương:" in msg

    def test_unknown_task_type(self):
        msg = _build_user_message("Query", "Context", "unknown_type")
        assert "Yêu cầu: Query" in msg


# ── SYSTEM_PROMPTS ────────────────────────────────────────────────────────────

class TestSystemPrompts:
    def test_all_task_types_have_prompts(self):
        expected_types = ["qa", "explain", "summarize_chapter", "summarize_book", "suggest"]
        for t in expected_types:
            assert t in SYSTEM_PROMPTS
            assert len(SYSTEM_PROMPTS[t]) > 50

    def test_qa_prompt_has_anti_hallucination(self):
        """QA prompt phải có quy tắc chống sai lệch."""
        prompt = SYSTEM_PROMPTS["qa"]
        assert "TUYỆT ĐỐI KHÔNG" in prompt or "SAO CHÉP NGUYÊN VĂN" in prompt

    def test_prompts_are_vietnamese(self):
        """Tất cả prompt phải bằng tiếng Việt."""
        for prompt in SYSTEM_PROMPTS.values():
            assert "tiếng Việt" in prompt.lower() or "việt" in prompt.lower()
