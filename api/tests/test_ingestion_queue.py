"""
Unit Tests — Ingestion Queue helpers
Test payload structure cho ingestion jobs.
"""
from services.ingestion_queue import _build_job_payload


class TestIngestionQueue:
    def test_build_job_payload(self):
        payload = _build_job_payload(book_id="book-123", job_type="reingest")

        assert payload["book_id"] == "book-123"
        assert payload["job_type"] == "reingest"
        assert payload["job_id"]
