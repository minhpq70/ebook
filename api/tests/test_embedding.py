"""
Unit Tests — Embedding helpers
Test logic gom dedup text và preserve vị trí output.
"""
from services.embedding import _group_texts_by_value


class TestGroupTextsByValue:
    def test_groups_duplicate_texts(self):
        grouped, results = _group_texts_by_value(["a", "b", "a", "c", "b"])

        assert grouped == {
            "a": [0, 2],
            "b": [1, 4],
            "c": [3],
        }
        assert results == [[], [], [], [], []]

    def test_ignores_blank_texts(self):
        grouped, results = _group_texts_by_value(["", "  ", "x"])

        assert grouped == {"x": [2]}
        assert results == [[], [], []]
