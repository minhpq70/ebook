"""
Metrics Analytics Service
- Suy diễn các chỉ số vận hành từ metrics snapshot
- Dùng cho admin dashboard hoặc phân tích nhanh không cần TSDB ngoài
"""
from __future__ import annotations


def _safe_divide(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def build_metrics_analytics(snapshot: dict) -> dict:
    """Tạo analytics mức cao từ snapshot metrics hiện tại."""
    requests = snapshot.get("requests", {})
    queries = snapshot.get("queries", {})
    cache = snapshot.get("cache", {})
    ingestion = snapshot.get("ingestion", {})
    uptime_seconds = max(int(snapshot.get("uptime_seconds", 0)), 1)

    total_requests = sum((requests.get("totals") or {}).values())
    total_errors = sum(
        count for code, count in (requests.get("status_codes") or {}).items()
        if str(code).startswith(("4", "5"))
    )
    total_queries = sum((queries.get("counts") or {}).values())
    total_ingestions = sum((ingestion.get("states") or {}).values())

    cache_hit_rates = {}
    cache_names = {
        key.rsplit(":", 1)[0]
        for key in cache.keys()
        if ":" in key
    }
    for cache_name in sorted(cache_names):
        hits = float(cache.get(f"{cache_name}:hit", 0))
        misses = float(cache.get(f"{cache_name}:miss", 0))
        cache_hit_rates[cache_name] = round(_safe_divide(hits, hits + misses), 4)

    return {
        "throughput": {
            "requests_per_minute": round(total_requests / (uptime_seconds / 60), 2),
            "queries_per_minute": round(total_queries / (uptime_seconds / 60), 2),
            "ingestions_per_hour": round(total_ingestions / (uptime_seconds / 3600), 2),
        },
        "reliability": {
            "request_error_rate": round(_safe_divide(total_errors, total_requests), 4),
            "ingestion_error_rate": round(
                _safe_divide(
                    float((ingestion.get("states") or {}).get("error", 0)),
                    float(total_ingestions),
                ),
                4,
            ),
        },
        "latency": {
            "retrieval_avg_ms": queries.get("retrieval_latency", {}).get("avg", 0.0),
            "retrieval_p95_ms": queries.get("retrieval_latency", {}).get("p95_recent", 0.0),
            "rag_avg_ms": queries.get("rag_latency", {}).get("avg", 0.0),
            "rag_p95_ms": queries.get("rag_latency", {}).get("p95_recent", 0.0),
            "embedding_batch_avg_ms": snapshot.get("embedding", {}).get("batch_latency", {}).get("avg", 0.0),
        },
        "cache": {
            "hit_rates": cache_hit_rates,
            "raw_counts": cache,
        },
        "hotspots": {
            "hottest_routes": requests.get("hottest_routes", []),
            "error_routes": requests.get("error_routes", []),
            "query_mix": queries.get("counts", {}),
        },
    }
