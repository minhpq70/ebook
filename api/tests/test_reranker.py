"""
Unit Tests — Reranker Service
Test cosine similarity, deduplication, và reranking logic.
Mock embedding calls.
"""
import pytest
from unittest.mock import AsyncMock, patch
from models.schemas import ChunkInfo
from services.reranker import _cosine_similarity, _deduplicate_chunks, rerank_chunks


# ── _cosine_similarity ────────────────────────────────────────────────────────

class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = [1.0, 0.0, 0.0]
        assert _cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        assert _cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert _cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_zero_vector_returns_zero(self):
        a = [0.0, 0.0, 0.0]
        b = [1.0, 2.0, 3.0]
        assert _cosine_similarity(a, b) == 0.0

    def test_similar_vectors(self):
        a = [1.0, 2.0, 3.0]
        b = [1.1, 2.1, 3.1]
        sim = _cosine_similarity(a, b)
        assert sim > 0.99  # rất giống nhau


# ── _deduplicate_chunks ──────────────────────────────────────────────────────

def _make_chunk(content: str, idx: int = 0, page_number: int = 1) -> ChunkInfo:
    return ChunkInfo(id=f"c{idx}", chunk_index=idx, page_number=page_number, content=content)


class TestDeduplicateChunks:
    def test_no_duplicates(self):
        chunks = [
            _make_chunk("Đây là nội dung hoàn toàn khác biệt", 0),
            _make_chunk("Và đây cũng là nội dung khác hẳn", 1),
        ]
        result = _deduplicate_chunks(chunks)
        assert len(result) == 2

    def test_exact_duplicates(self):
        chunks = [
            _make_chunk("Nội dung giống hệt nhau trong hai chunks", 0),
            _make_chunk("Nội dung giống hệt nhau trong hai chunks", 1),
        ]
        result = _deduplicate_chunks(chunks)
        assert len(result) == 1

    def test_near_duplicates(self):
        """2 chunks có >95% word overlap bị loại."""
        base = "Kinh tế Việt Nam phát triển mạnh trong giai đoạn đổi mới"
        chunks = [
            _make_chunk(base, 0),
            _make_chunk(base + " hội nhập", 1),  # chỉ thêm 1 từ
        ]
        result = _deduplicate_chunks(chunks, threshold=0.95)
        assert len(result) == 1

    def test_empty_input(self):
        assert _deduplicate_chunks([]) == []

    def test_preserves_order(self):
        chunks = [
            _make_chunk("Alpha bravo charlie", 0),
            _make_chunk("Delta echo foxtrot", 1),
            _make_chunk("Golf hotel india", 2),
        ]
        result = _deduplicate_chunks(chunks)
        assert [c.chunk_index for c in result] == [0, 1, 2]


# ── rerank_chunks ─────────────────────────────────────────────────────────────

class TestRerankChunks:
    @pytest.mark.asyncio
    async def test_empty_chunks(self):
        result = await rerank_chunks("test query", [], top_k=5)
        assert result == []

    @pytest.mark.asyncio
    async def test_fewer_than_top_k(self):
        """Nếu chunks ít hơn top_k → trả về tất cả (không cần rerank)."""
        chunks = [_make_chunk("Chunk A", 0), _make_chunk("Chunk B", 1)]
        result = await rerank_chunks("query", chunks, top_k=5)
        assert len(result) == 2

    @pytest.mark.asyncio
    @patch("services.reranker.embed_text", new_callable=AsyncMock)
    @patch("services.reranker.embed_batch", new_callable=AsyncMock)
    async def test_reranks_by_score(self, mock_embed_batch, mock_embed_text):
        """Chunk có embedding gần query hơn phải được xếp trước."""
        # Query embedding
        query_emb = [1.0, 0.0, 0.0]
        
        # Chunk A: gần query (cosine ~ 1.0)
        # Chunk B: xa query  (cosine ~ 0.0)
        # Chunk C: trung bình
        mock_embed_batch.return_value = [
            [0.0, 1.0, 0.0],   # Chunk A — xa
            [1.0, 0.1, 0.0],   # Chunk B — gần nhất
            [0.5, 0.5, 0.0],   # Chunk C — trung bình
        ]

        chunks = [
            _make_chunk("Chunk A nội dung không liên quan lắm", 0),
            _make_chunk("Chunk B nội dung rất liên quan", 1),
            _make_chunk("Chunk C nội dung trung bình", 2),
        ]

        result = await rerank_chunks(
            "query test", chunks, top_k=2, query_embedding=query_emb
        )

        assert len(result) == 2
        # Chunk B (index 1) phải đứng đầu vì gần query nhất
        assert result[0].chunk_index == 1
