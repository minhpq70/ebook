"""
Unit Tests — Monitoring helpers
Test memory guard decision logic thuần.
"""
from unittest.mock import patch

from services.monitoring import get_memory_guard_decision


class TestMemoryGuardDecision:
    @patch("services.monitoring._current_python_heap_mb", return_value=900.0)
    def test_hard_limit_blocks_all(self, _mock_heap):
        decision = get_memory_guard_decision("/api/v1/books")
        assert decision["block"] is True
        assert decision["level"] == "hard"

    @patch("services.monitoring._current_python_heap_mb", return_value=600.0)
    def test_soft_limit_blocks_heavy_path(self, _mock_heap):
        decision = get_memory_guard_decision("/api/v1/rag/query")
        assert decision["block"] is True
        assert decision["level"] == "soft"

    @patch("services.monitoring._current_python_heap_mb", return_value=600.0)
    def test_soft_limit_allows_light_path(self, _mock_heap):
        decision = get_memory_guard_decision("/health")
        assert decision["block"] is False
