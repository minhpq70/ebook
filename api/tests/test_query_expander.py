"""
Unit Tests — Query Expander
Test expand_query với mock OpenAI.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from services.query_expander import expand_query, embed_expanded_queries


class TestExpandQuery:
    @pytest.mark.asyncio
    @patch("services.query_expander.get_chat_openai")
    @patch("services.query_expander.get_cache_manager")
    async def test_returns_original_plus_paraphrases(self, mock_get_cache_manager, mock_get_chat_openai):
        """expand_query trả về [query_gốc, paraphrase1, paraphrase2]."""
        mock_client = AsyncMock()
        mock_get_chat_openai.return_value = mock_client
        mock_cache = AsyncMock()
        mock_cache.get_query_expansion.return_value = None
        mock_get_cache_manager.return_value = mock_cache

        # Mock response
        mock_choice = MagicMock()
        mock_choice.message.content = "Phiên bản 1 câu hỏi\nPhiên bản 2 câu hỏi"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        result = await expand_query("Tác giả nói gì?")

        assert len(result) == 3
        assert result[0] == "Tác giả nói gì?"  # query gốc luôn đầu
        assert result[1] == "Phiên bản 1 câu hỏi"
        assert result[2] == "Phiên bản 2 câu hỏi"
        mock_cache.set_query_expansion.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("services.query_expander.get_chat_openai")
    @patch("services.query_expander.get_cache_manager")
    async def test_graceful_fallback_on_error(self, mock_get_cache_manager, mock_get_chat_openai):
        """Nếu OpenAI lỗi → trả về [query_gốc] thay vì crash."""
        mock_client = AsyncMock()
        mock_get_chat_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        mock_cache = AsyncMock()
        mock_cache.get_query_expansion.return_value = None
        mock_get_cache_manager.return_value = mock_cache

        result = await expand_query("Test query")

        assert result == ["Test query"]

    @pytest.mark.asyncio
    @patch("services.query_expander.get_chat_openai")
    @patch("services.query_expander.get_cache_manager")
    async def test_empty_response(self, mock_get_cache_manager, mock_get_chat_openai):
        """OpenAI trả về empty string → vẫn có query gốc."""
        mock_client = AsyncMock()
        mock_get_chat_openai.return_value = mock_client
        mock_cache = AsyncMock()
        mock_cache.get_query_expansion.return_value = None
        mock_get_cache_manager.return_value = mock_cache

        mock_choice = MagicMock()
        mock_choice.message.content = ""
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        result = await expand_query("Test")

        assert result == ["Test"]

    @pytest.mark.asyncio
    @patch("services.query_expander.get_chat_openai")
    @patch("services.query_expander.get_cache_manager")
    async def test_limits_to_2_paraphrases(self, mock_get_cache_manager, mock_get_chat_openai):
        """Chỉ lấy tối đa 2 paraphrases dù GPT trả nhiều hơn."""
        mock_client = AsyncMock()
        mock_get_chat_openai.return_value = mock_client
        mock_cache = AsyncMock()
        mock_cache.get_query_expansion.return_value = None
        mock_get_cache_manager.return_value = mock_cache

        mock_choice = MagicMock()
        mock_choice.message.content = "P1\nP2\nP3\nP4"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        result = await expand_query("Query")

        assert len(result) == 3  # original + max 2

    @pytest.mark.asyncio
    @patch("services.query_expander.get_chat_openai")
    @patch("services.query_expander.get_cache_manager")
    async def test_returns_cached_variants_without_openai(self, mock_get_cache_manager, mock_get_chat_openai):
        mock_cache = AsyncMock()
        mock_cache.get_query_expansion.return_value = ["Query", "P1", "P2"]
        mock_get_cache_manager.return_value = mock_cache

        result = await expand_query("Query")

        assert result == ["Query", "P1", "P2"]
        mock_get_chat_openai.assert_not_called()


class TestEmbedExpandedQueries:
    @pytest.mark.asyncio
    @patch("services.embedding.embed_batch", new_callable=AsyncMock)
    async def test_returns_centroid(self, mock_embed_batch):
        """Kết quả phải là centroid (normalized mean) của embeddings."""
        import numpy as np

        mock_embed_batch.return_value = [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ]

        result = await embed_expanded_queries(["q1", "q2"])

        # Mean = [0.5, 0.5, 0.0], normalized
        expected = np.array([0.5, 0.5, 0.0])
        expected = expected / np.linalg.norm(expected)

        assert len(result) == 3
        for r, e in zip(result, expected):
            assert r == pytest.approx(e, abs=1e-6)
