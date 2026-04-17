"""
Unit Tests — Metrics Registry
Test tổng hợp request/query/cache/ingestion metrics.
"""
from services.metrics_registry import MetricsRegistry


class TestMetricsRegistry:
    def test_request_and_error_summary(self):
        registry = MetricsRegistry()

        registry.record_request("/health", "GET", 200, 12.5)
        registry.record_request("/health", "GET", 500, 30.0)

        snapshot = registry.snapshot()

        assert snapshot["requests"]["totals"]["GET /health"] == 2
        assert snapshot["requests"]["status_codes"]["200"] == 1
        assert snapshot["requests"]["status_codes"]["500"] == 1
        assert snapshot["requests"]["error_routes"][0]["route"] == "GET /health"

    def test_query_cache_and_ingestion_summary(self):
        registry = MetricsRegistry()

        registry.record_query("qa", latency_ms=120.0, source_count=5)
        registry.record_retrieval(latency_ms=40.0, candidate_count=12)
        registry.record_rag_latency(latency_ms=80.0, tokens_used=320)
        registry.record_cache("embedding", True)
        registry.record_cache("embedding", False)
        registry.record_ingestion("ready", latency_ms=1500.0, chunks=42)

        snapshot = registry.snapshot()

        assert snapshot["queries"]["counts"]["qa"] == 1
        assert snapshot["cache"]["embedding:hit"] == 1
        assert snapshot["cache"]["embedding:miss"] == 1
        assert snapshot["ingestion"]["states"]["ready"] == 1
        assert snapshot["queries"]["retrieval_latency"]["count"] == 1
        assert snapshot["queries"]["rag_latency"]["count"] == 1

    def test_restore_from_snapshot(self):
        registry = MetricsRegistry()
        snapshot = {
            "uptime_seconds": 120,
            "requests": {
                "totals": {"GET /health": 3},
                "status_codes": {"200": 2, "500": 1},
                "latency": {
                    "GET /health": {
                        "count": 3,
                        "avg": 20.0,
                        "min": 10.0,
                        "max": 30.0,
                        "p95_recent": 30.0,
                    }
                },
                "hottest_routes": [{"route": "GET /health", "count": 3}],
                "error_routes": [{"route": "GET /health", "count": 1}],
            },
            "queries": {
                "counts": {"qa": 2},
                "latency": {
                    "qa": {
                        "count": 2,
                        "avg": 120.0,
                        "min": 100.0,
                        "max": 140.0,
                        "p95_recent": 140.0,
                    }
                },
                "retrieval_latency": {"count": 1, "avg": 40.0, "min": 40.0, "max": 40.0, "p95_recent": 40.0},
                "rag_latency": {"count": 1, "avg": 80.0, "min": 80.0, "max": 80.0, "p95_recent": 80.0},
            },
            "embedding": {
                "batch_latency": {"count": 1, "avg": 15.0, "min": 15.0, "max": 15.0, "p95_recent": 15.0},
            },
            "cache": {"embedding:hit": 5},
            "ingestion": {
                "states": {"ready": 1},
                "latency": {"count": 1, "avg": 1500.0, "min": 1500.0, "max": 1500.0, "p95_recent": 1500.0},
            },
        }

        registry.restore(snapshot)
        restored = registry.snapshot()

        assert restored["requests"]["totals"]["GET /health"] == 3
        assert restored["queries"]["counts"]["qa"] == 2
        assert restored["cache"]["embedding:hit"] == 5
        assert restored["ingestion"]["states"]["ready"] == 1
