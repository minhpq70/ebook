"""
Unit Tests — Prometheus Exporter
Test output text cơ bản của metrics exporter.
"""
from services.prometheus_exporter import render_prometheus_metrics


class TestPrometheusExporter:
    def test_renders_key_metrics(self):
        metrics_snapshot = {
            "uptime_seconds": 120,
            "requests": {
                "totals": {"GET /health": 3},
                "status_codes": {"200": 3},
            },
            "queries": {
                "counts": {"qa": 2},
                "retrieval_latency": {"avg": 40.0},
                "rag_latency": {"avg": 80.0},
            },
            "cache": {"embedding:hit": 5},
            "ingestion": {"states": {"ready": 1}},
        }
        runtime_snapshot = {
            "memory": {
                "python_heap_mb": 12.5,
                "python_heap_peak_mb": 18.0,
            }
        }

        output = render_prometheus_metrics(metrics_snapshot, runtime_snapshot)

        assert "ebook_uptime_seconds 120" in output
        assert 'ebook_http_requests_total{method="GET",path="/health"} 3' in output
        assert 'ebook_rag_queries_total{task_type="qa"} 2' in output
        assert 'ebook_cache_events_total{cache="embedding",outcome="hit"} 5' in output
        assert "ebook_python_heap_megabytes 12.5" in output
