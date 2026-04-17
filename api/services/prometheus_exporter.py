"""
Prometheus Exporter
- Convert metrics snapshot + runtime snapshot sang text exposition format đơn giản
"""
from __future__ import annotations


def _sanitize_label_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _metric_line(name: str, value: float | int, labels: dict[str, str] | None = None) -> str:
    if labels:
        joined = ",".join(f'{key}="{_sanitize_label_value(val)}"' for key, val in labels.items())
        return f"{name}{{{joined}}} {value}"
    return f"{name} {value}"


def render_prometheus_metrics(metrics_snapshot: dict, runtime_snapshot: dict) -> str:
    """Sinh output text/plain kiểu Prometheus."""
    lines: list[str] = []

    lines.append("# HELP ebook_uptime_seconds Process uptime in seconds")
    lines.append("# TYPE ebook_uptime_seconds gauge")
    lines.append(_metric_line("ebook_uptime_seconds", metrics_snapshot.get("uptime_seconds", 0)))

    request_totals = metrics_snapshot.get("requests", {}).get("totals", {})
    lines.append("# HELP ebook_http_requests_total Total HTTP requests by route")
    lines.append("# TYPE ebook_http_requests_total counter")
    for route, count in request_totals.items():
        method, path = route.split(" ", 1)
        lines.append(_metric_line("ebook_http_requests_total", count, {"method": method, "path": path}))

    request_status = metrics_snapshot.get("requests", {}).get("status_codes", {})
    lines.append("# HELP ebook_http_status_total Total HTTP responses by status code")
    lines.append("# TYPE ebook_http_status_total counter")
    for status_code, count in request_status.items():
        lines.append(_metric_line("ebook_http_status_total", count, {"status": str(status_code)}))

    query_counts = metrics_snapshot.get("queries", {}).get("counts", {})
    lines.append("# HELP ebook_rag_queries_total Total RAG queries by task type")
    lines.append("# TYPE ebook_rag_queries_total counter")
    for task_type, count in query_counts.items():
        lines.append(_metric_line("ebook_rag_queries_total", count, {"task_type": task_type}))

    cache_counts = metrics_snapshot.get("cache", {})
    lines.append("# HELP ebook_cache_events_total Cache hits and misses")
    lines.append("# TYPE ebook_cache_events_total counter")
    for key, count in cache_counts.items():
        cache_name, outcome = key.rsplit(":", 1)
        lines.append(_metric_line("ebook_cache_events_total", count, {"cache": cache_name, "outcome": outcome}))

    ingestion_states = metrics_snapshot.get("ingestion", {}).get("states", {})
    lines.append("# HELP ebook_ingestion_total Total ingestions by final state")
    lines.append("# TYPE ebook_ingestion_total counter")
    for state, count in ingestion_states.items():
        lines.append(_metric_line("ebook_ingestion_total", count, {"state": state}))

    runtime_memory = runtime_snapshot.get("memory", {})
    lines.append("# HELP ebook_python_heap_megabytes Python heap memory in MB")
    lines.append("# TYPE ebook_python_heap_megabytes gauge")
    lines.append(_metric_line("ebook_python_heap_megabytes", runtime_memory.get("python_heap_mb", 0.0)))
    lines.append(_metric_line("ebook_python_heap_peak_megabytes", runtime_memory.get("python_heap_peak_mb", 0.0)))

    queries = metrics_snapshot.get("queries", {})
    lines.append("# HELP ebook_retrieval_latency_avg_ms Average retrieval latency in ms")
    lines.append("# TYPE ebook_retrieval_latency_avg_ms gauge")
    lines.append(_metric_line("ebook_retrieval_latency_avg_ms", queries.get("retrieval_latency", {}).get("avg", 0.0)))
    lines.append(_metric_line("ebook_rag_latency_avg_ms", queries.get("rag_latency", {}).get("avg", 0.0)))

    return "\n".join(lines) + "\n"
