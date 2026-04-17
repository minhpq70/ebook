"""
Unit Tests — Metrics Analytics
Test các chỉ số suy diễn từ snapshot.
"""
from services.metrics_analytics import build_metrics_analytics


class TestMetricsAnalytics:
    def test_builds_derived_rates(self):
        snapshot = {
            "uptime_seconds": 120,
            "requests": {
                "totals": {"GET /health": 60, "POST /api/v1/rag/query": 30},
                "status_codes": {"200": 80, "500": 10},
                "hottest_routes": [{"route": "GET /health", "count": 60}],
                "error_routes": [{"route": "POST /api/v1/rag/query", "count": 10}],
            },
            "queries": {
                "counts": {"qa": 20, "summarize_book": 10},
                "retrieval_latency": {"avg": 45.0, "p95_recent": 70.0},
                "rag_latency": {"avg": 120.0, "p95_recent": 200.0},
            },
            "embedding": {
                "batch_latency": {"avg": 15.0},
            },
            "cache": {
                "embedding:hit": 90,
                "embedding:miss": 10,
                "query_result:hit": 30,
                "query_result:miss": 10,
            },
            "ingestion": {
                "states": {"ready": 9, "error": 1},
            },
        }

        analytics = build_metrics_analytics(snapshot)

        assert analytics["throughput"]["requests_per_minute"] == 45.0
        assert analytics["throughput"]["queries_per_minute"] == 15.0
        assert analytics["reliability"]["request_error_rate"] == 0.1111
        assert analytics["reliability"]["ingestion_error_rate"] == 0.1
        assert analytics["cache"]["hit_rates"]["embedding"] == 0.9
        assert analytics["cache"]["hit_rates"]["query_result"] == 0.75
