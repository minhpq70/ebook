"""
Unit Tests — Retrieval helpers
Test candidate preparation và prefetch helper logic thuần.
"""
from models.schemas import ChunkInfo
from services.retrieval import _prepare_rerank_candidates


def _make_chunk(idx: int, score: float) -> ChunkInfo:
    return ChunkInfo(
        id=f"c{idx}",
        chunk_index=idx,
        page_number=idx + 1,
        content=f"Chunk {idx}",
        score=score,
    )


class TestPrepareRerankCandidates:
    def test_trims_to_best_scores(self):
        candidates = [_make_chunk(0, 0.1), _make_chunk(1, 0.9), _make_chunk(2, 0.5)]

        result = _prepare_rerank_candidates(candidates, top_k=1)

        assert [chunk.id for chunk in result] == ["c1", "c2", "c0"]

    def test_handles_empty(self):
        assert _prepare_rerank_candidates([], top_k=2) == []
