"""
Performance Metrics Registry
- Lưu metrics runtime trong bộ nhớ tiến trình
- Tổng hợp request/query/cache/ingestion stats
- Phục vụ dashboard nội bộ đơn giản cho phase 3
"""
from __future__ import annotations

import threading
import time
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field


@dataclass
class MetricSeries:
    count: int = 0
    total: float = 0.0
    minimum: float | None = None
    maximum: float | None = None
    recent: deque[float] = field(default_factory=lambda: deque(maxlen=200))

    def add(self, value: float) -> None:
        self.count += 1
        self.total += value
        self.minimum = value if self.minimum is None else min(self.minimum, value)
        self.maximum = value if self.maximum is None else max(self.maximum, value)
        self.recent.append(value)

    def summary(self) -> dict:
        avg = self.total / self.count if self.count else 0.0
        recent_values = list(self.recent)
        p95 = 0.0
        if recent_values:
            sorted_values = sorted(recent_values)
            idx = min(len(sorted_values) - 1, int(len(sorted_values) * 0.95))
            p95 = sorted_values[idx]
        return {
            "count": self.count,
            "avg": round(avg, 2),
            "min": round(self.minimum or 0.0, 2),
            "max": round(self.maximum or 0.0, 2),
            "p95_recent": round(p95, 2),
        }

    @classmethod
    def from_summary(cls, payload: dict) -> "MetricSeries":
        series = cls()
        series.count = int(payload.get("count", 0))
        avg = float(payload.get("avg", 0.0))
        series.total = avg * series.count
        series.minimum = float(payload.get("min", 0.0)) if series.count else None
        series.maximum = float(payload.get("max", 0.0)) if series.count else None
        recent_p95 = payload.get("p95_recent")
        if recent_p95 is not None and series.count:
            series.recent.append(float(recent_p95))
        return series


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.started_at = time.time()
        self.request_latency = defaultdict(MetricSeries)
        self.request_counts = Counter()
        self.status_counts = Counter()
        self.error_counts = Counter()
        self.query_counts = Counter()
        self.query_latency = defaultdict(MetricSeries)
        self.retrieval_latency = MetricSeries()
        self.rag_latency = MetricSeries()
        self.embedding_batch_latency = MetricSeries()
        self.ingestion_latency = MetricSeries()
        self.cache_counts = Counter()
        self.ingestion_states = Counter()

    def record_request(self, path: str, method: str, status_code: int, latency_ms: float) -> None:
        key = f"{method} {path}"
        with self._lock:
            self.request_counts[key] += 1
            self.status_counts[str(status_code)] += 1
            self.request_latency[key].add(latency_ms)
            if status_code >= 400:
                self.error_counts[key] += 1

    def record_query(self, task_type: str, latency_ms: float, source_count: int) -> None:
        with self._lock:
            self.query_counts[task_type] += 1
            self.query_latency[task_type].add(latency_ms)
            self.query_latency["sources_per_query"].add(float(source_count))

    def record_retrieval(self, latency_ms: float, candidate_count: int) -> None:
        with self._lock:
            self.retrieval_latency.add(latency_ms)
            self.query_latency["retrieval_candidates"].add(float(candidate_count))

    def record_rag_latency(self, latency_ms: float, tokens_used: int | None = None) -> None:
        with self._lock:
            self.rag_latency.add(latency_ms)
            if tokens_used is not None:
                self.query_latency["rag_tokens"].add(float(tokens_used))

    def record_embedding_batch(self, latency_ms: float, total_inputs: int, uncached_inputs: int) -> None:
        with self._lock:
            self.embedding_batch_latency.add(latency_ms)
            self.query_latency["embedding_batch_inputs"].add(float(total_inputs))
            self.query_latency["embedding_uncached_inputs"].add(float(uncached_inputs))

    def record_cache(self, cache_name: str, hit: bool) -> None:
        suffix = "hit" if hit else "miss"
        with self._lock:
            self.cache_counts[f"{cache_name}:{suffix}"] += 1

    def record_ingestion(self, status: str, latency_ms: float | None = None, chunks: int | None = None) -> None:
        with self._lock:
            self.ingestion_states[status] += 1
            if latency_ms is not None:
                self.ingestion_latency.add(latency_ms)
            if chunks is not None:
                self.query_latency["ingestion_chunks"].add(float(chunks))

    def snapshot(self) -> dict:
        with self._lock:
            uptime_s = int(time.time() - self.started_at)
            hottest_routes = self.request_counts.most_common(10)
            noisiest_errors = self.error_counts.most_common(10)
            return {
                "uptime_seconds": uptime_s,
                "requests": {
                    "totals": dict(self.request_counts),
                    "status_codes": dict(self.status_counts),
                    "latency": {k: v.summary() for k, v in self.request_latency.items()},
                    "hottest_routes": [{"route": route, "count": count} for route, count in hottest_routes],
                    "error_routes": [{"route": route, "count": count} for route, count in noisiest_errors],
                },
                "queries": {
                    "counts": dict(self.query_counts),
                    "latency": {k: v.summary() for k, v in self.query_latency.items()},
                    "retrieval_latency": self.retrieval_latency.summary(),
                    "rag_latency": self.rag_latency.summary(),
                },
                "embedding": {
                    "batch_latency": self.embedding_batch_latency.summary(),
                },
                "cache": dict(self.cache_counts),
                "ingestion": {
                    "states": dict(self.ingestion_states),
                    "latency": self.ingestion_latency.summary(),
                },
            }

    def restore(self, payload: dict) -> None:
        """Khôi phục một phần metrics từ snapshot persisted."""
        if not payload:
            return
        with self._lock:
            self.started_at = time.time() - int(payload.get("uptime_seconds", 0))

            requests = payload.get("requests", {})
            self.request_counts = Counter(requests.get("totals", {}))
            self.status_counts = Counter(requests.get("status_codes", {}))
            self.error_counts = Counter({
                item["route"]: item["count"]
                for item in requests.get("error_routes", [])
                if "route" in item and "count" in item
            })
            self.request_latency = defaultdict(MetricSeries)
            for key, value in requests.get("latency", {}).items():
                self.request_latency[key] = MetricSeries.from_summary(value)

            queries = payload.get("queries", {})
            self.query_counts = Counter(queries.get("counts", {}))
            self.query_latency = defaultdict(MetricSeries)
            for key, value in queries.get("latency", {}).items():
                self.query_latency[key] = MetricSeries.from_summary(value)
            self.retrieval_latency = MetricSeries.from_summary(queries.get("retrieval_latency", {}))
            self.rag_latency = MetricSeries.from_summary(queries.get("rag_latency", {}))

            embedding = payload.get("embedding", {})
            self.embedding_batch_latency = MetricSeries.from_summary(embedding.get("batch_latency", {}))

            self.cache_counts = Counter(payload.get("cache", {}))

            ingestion = payload.get("ingestion", {})
            self.ingestion_states = Counter(ingestion.get("states", {}))
            self.ingestion_latency = MetricSeries.from_summary(ingestion.get("latency", {}))


_REGISTRY = MetricsRegistry()


def get_metrics_registry() -> MetricsRegistry:
    return _REGISTRY
