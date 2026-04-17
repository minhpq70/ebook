# Ebook Platform Implementation Deep Dive

Tài liệu này mô tả phần triển khai thực tế đã được thực hiện sau khi hoàn tất phase 1, tập trung vào phase 2 và phase 3 của backend. Mục tiêu là giúp đọc hiểu sâu hơn về kiến trúc hiện tại, các thay đổi đã áp dụng trong codebase, và các trade-off kỹ thuật đang tồn tại.

## 1. Mục tiêu tổng thể

Sau phase 1, hệ thống đã có:

- Tối ưu OCR cơ bản
- Redis cache cho embedding/query/metadata
- Tối ưu index DB
- Connection reuse cho Supabase/OpenAI

Các bước tiếp theo được triển khai thực tế tập trung vào:

- Giảm peak memory khi ingest PDF lớn
- Tăng throughput cho embedding
- Tối ưu retrieval/reranking để giảm chi phí xử lý
- Thêm progress tracking cho ingestion dài
- Thêm runtime monitoring, metrics nội bộ, memory guard
- Persist metrics để không mất hoàn toàn số liệu khi process restart

## 2. Tổng quan các thay đổi đã triển khai

### Phase 2 đã triển khai

- Chuyển ingest từ kiểu gom toàn bộ PDF vào RAM sang xử lý theo lô trang
- Thêm `ingestion progress` cache trong Redis
- Thêm endpoint theo dõi tiến độ ingestion
- Tối ưu `embed_batch()` với dedup, concurrency, retry/backoff
- Giảm số candidate bị embed trong reranker
- Cache query expansion
- Prefetch nhẹ các chunk hàng xóm để cải thiện ngữ cảnh retrieval
- Tuning GC cơ bản ở startup

### Phase 3 đã triển khai

- Thêm runtime monitoring dùng `tracemalloc`
- Thêm memory guard middleware
- Thêm metrics registry trong memory
- Thu thập metrics cho request, query, retrieval, RAG, embedding, cache, ingestion
- Expose metrics qua API
- Persist metrics snapshot vào Redis theo chu kỳ
- Restore metrics snapshot khi app khởi động lại
- Thêm analytics suy diễn từ metrics snapshot
- Thêm export Prometheus text để tích hợp dashboard ngoài dễ hơn

## 3. Ingestion pipeline mới

Các file chính:

- `api/services/pdf_processor.py`
- `api/services/ingestion.py`
- `api/routers/books.py`
- `api/core/redis_client.py`
- `api/models/schemas.py`

### 3.1. Vấn đề của cách cũ

Pipeline cũ chạy theo dạng:

1. Extract toàn bộ trang PDF
2. Chunk toàn bộ nội dung
3. Embed toàn bộ chunks
4. Lưu toàn bộ xuống DB

Điểm yếu:

- Peak memory cao khi PDF lớn
- Không có tiến độ trung gian để frontend poll
- Toàn bộ công việc nặng dồn vào một mẻ lớn

### 3.2. Cách mới

`pdf_processor.py` được mở rộng thêm:

- `get_pdf_page_count(pdf_bytes)`
- `iter_pdf_page_batches(pdf_bytes, batch_size)`
- `chunk_pages(pages, start_chunk_index=0)`

Ý tưởng:

- Mỗi lần chỉ extract một batch trang
- Batch đó được chunk ngay
- Batch chunks được embed ngay
- Embedding được insert xuống DB ngay
- Sau đó mới chuyển sang batch tiếp theo

### 3.3. Lợi ích

- Giảm peak memory đáng kể
- Hỗ trợ file lớn tốt hơn
- Có thể cập nhật `progress` theo số trang đã xử lý
- Giảm rủi ro hỏng cả pipeline sau khi đã xử lý được một phần lớn tài liệu

### 3.4. Chunk index liên tục

Một bug quan trọng khi chuyển sang batching là `chunk_index` có thể bị reset về `0` ở mỗi batch, làm trùng chỉ số chunk trong cùng một sách.

Đã sửa bằng cách:

- Cho `chunk_pages()` nhận `start_chunk_index`
- `ingestion.py` duy trì `next_chunk_index`
- TOC chunk cũng dùng chỉ số tiếp theo thay vì `-1`

Điều này đảm bảo:

- `chunk_index` tăng liên tục theo toàn bộ sách
- Retrieval/prefetch neighbor theo `chunk_index` hoạt động ổn định hơn

## 4. Ingestion progress tracking

Các file chính:

- `api/services/ingestion.py`
- `api/core/redis_client.py`
- `api/routers/books.py`
- `api/models/schemas.py`

### 4.1. Dữ liệu progress

Redis hiện lưu key dạng:

- `ingestion:progress:{book_id}`

Payload gồm:

- `book_id`
- `status`
- `message`
- `total_pages`
- `processed_pages`
- `total_chunks`
- `stored_chunks`

### 4.2. Luồng cập nhật

Trong `run_ingestion_pipeline()`:

- Bắt đầu pipeline: lưu trạng thái `processing`
- Sau mỗi batch trang: cập nhật số trang/chunk đã xử lý
- Hoàn tất: cập nhật `ready`
- Lỗi: cập nhật `error`

### 4.3. API mới

Endpoint:

- `GET /api/v1/books/{book_id}/ingestion-status`

Hành vi:

- Nếu Redis có progress mới nhất thì trả progress đó
- Nếu không có thì fallback sang trạng thái `books.status`

Điều này cho phép frontend poll trong các tác vụ ingest hoặc re-ingest dài.

## 5. Embedding pipeline tối ưu hơn

File chính:

- `api/services/embedding.py`

### 5.1. Vấn đề cũ

`embed_batch()` trước đây:

- Kiểm tra cache tuần tự
- Gửi các batch tuần tự
- Không dedup nội dung trùng nhau trong cùng request
- Không có backoff rõ ràng cho lỗi transient

### 5.2. Các thay đổi đã làm

Đã thêm:

- `_group_texts_by_value()`: gom text trùng nhau
- `_embed_request_with_retry()`: retry với exponential backoff
- Semaphore concurrency cho các batch embedding
- Ghi metrics hit/miss embedding cache

### 5.3. Hiệu quả

Nếu một tài liệu có nhiều đoạn lặp:

- Chỉ cần tính embedding một lần
- Các vị trí còn lại dùng lại cùng vector

Nếu OpenAI bị rate limit hoặc timeout tạm thời:

- Batch sẽ retry thay vì fail ngay

### 5.4. Giới hạn hiện tại

- Chưa có compression embedding ở tầng storage
- Chưa có distributed worker cho embedding
- Concurrency hiện là trong một process FastAPI

## 6. Query expansion cache

File chính:

- `api/services/query_expander.py`
- `api/core/redis_client.py`

### 6.1. Vấn đề

Query expansion bằng LLM tạo thêm recall, nhưng:

- Tăng latency
- Có thể gọi lặp lại cho cùng một query phổ biến

### 6.2. Cách triển khai

Đã thêm cache Redis cho query expansion:

- Key: `query:expand:{hash}`

Luồng:

1. Normalize query
2. Tính hash
3. Thử lấy variants từ Redis
4. Nếu miss mới gọi LLM
5. Dedup các paraphrase trùng
6. Lưu lại vào Redis

### 6.3. Lợi ích

- Giảm chi phí OpenAI cho các query lặp
- Giảm latency cho các câu hỏi phổ biến

## 7. Retrieval và reranking tối ưu hơn

Các file chính:

- `api/services/retrieval.py`
- `api/services/reranker.py`

### 7.1. Candidate trimming trước rerank

Trước đây:

- Hybrid search trả về candidates
- Reranker embed toàn bộ candidates đó

Nếu `top_k` nhỏ mà candidate set lớn:

- Tốn embedding không cần thiết
- Tăng latency

Đã thêm:

- `_prepare_rerank_candidates()` trong retrieval
- `_trim_candidates_for_reranking()` trong reranker

Ý tưởng:

- Chỉ giữ tập ứng viên đủ rộng để rerank tốt
- Nhưng không embed quá nhiều chunks vô ích

### 7.2. Neighbor prefetch

Đã thêm `_expand_context_neighbors()` trong `retrieval.py`.

Mục tiêu:

- Nếu top hit nằm ở gần ranh giới chunk, có thể mất ý nghĩa ngữ cảnh
- Hệ thống sẽ lấy thêm một số chunk hàng xóm theo `chunk_index`

Chiến lược:

- Lấy top hits chính
- Tìm các `chunk_index - 1` và `chunk_index + 1` cho vài hit đầu
- Query thêm từ DB
- Merge lại với danh sách chính

### 7.3. Lợi ích

- Giảm các câu trả lời thiếu context ở đầu/cuối đoạn
- Giữ được tính liên tục ngữ nghĩa tốt hơn

### 7.4. Trade-off

- Nếu neighbor prefetch quá cao sẽ làm giảm precision
- Hiện tại đây là prefetch nhẹ, không phải expansion mạnh

## 8. Runtime monitoring và memory guard

Các file chính:

- `api/services/monitoring.py`
- `api/main.py`
- `api/core/config.py`
- `api/routers/metrics.py`

### 8.1. Runtime snapshot

`monitoring.py` dùng `tracemalloc` để theo dõi:

- Python heap hiện tại
- Python heap peak
- GC counts
- GC thresholds
- Soft/hard memory limit

### 8.2. Endpoint runtime

API:

- `GET /api/v1/metrics/runtime`

Trả về snapshot runtime để giám sát nhẹ.

### 8.3. Health endpoint

`GET /health` hiện trả thêm `runtime` để kiểm tra nhanh tình trạng process.

### 8.4. Memory guard

Middleware trong `main.py`:

- Chặn request khi heap Python vượt `memory_hard_limit_mb`
- Trả `503`
- Không chặn `/health` và `/api/v1/metrics/runtime`

Mục tiêu:

- Tránh tiếp tục nhận request nặng khi process đang ở trạng thái nguy hiểm

### 8.5. Giới hạn

`tracemalloc` chỉ phản ánh tốt Python heap, không phải toàn bộ RSS của process. Nghĩa là:

- Nó rất hữu ích cho xu hướng memory leak Python-side
- Nhưng chưa thay thế hoàn toàn việc đo RSS thực của OS

## 9. Metrics registry nội bộ

File chính:

- `api/services/metrics_registry.py`

### 9.1. Mục tiêu

Tạo một lớp thống kê nhẹ trong memory để:

- Không cần hệ thống observability ngoài
- Có thể xem nhanh trạng thái request/query/cache
- Hỗ trợ phase 3 analytics nội bộ

### 9.2. Metrics hiện có

Registry đang thu thập:

- Request counts theo route
- Status code counts
- Request latency theo route
- Error route counts
- Query counts theo `task_type`
- Query latency
- Retrieval latency
- RAG latency
- Embedding batch latency
- Cache hit/miss
- Ingestion states và ingestion latency

### 9.3. Dữ liệu thống kê

`MetricSeries` giữ:

- `count`
- `total`
- `min`
- `max`
- `recent`

Và xuất summary gồm:

- `avg`
- `min`
- `max`
- `p95_recent`

Lưu ý:

- `p95_recent` chỉ tính trên cửa sổ `recent`, không phải toàn bộ lịch sử tiến trình

## 10. Instrumentation các đường chính

### 10.1. HTTP request metrics

Trong `main.py` có middleware `collect_request_metrics`.

Mỗi request được ghi:

- `method`
- `path`
- `status_code`
- `latency_ms`

### 10.2. RAG query metrics

Trong `api/routers/rag.py`:

- Blocking query ghi `task_type`, latency, số source chunks
- Streaming query cũng ghi tương tự khi stream kết thúc

Trong `api/services/rag_engine.py`:

- Ghi `rag_latency`
- Ghi `tokens_used` nếu có

### 10.3. Retrieval metrics

Trong `api/services/retrieval.py`:

- Query result cache hit/miss
- Tổng latency retrieval
- Candidate count

### 10.4. Embedding metrics

Trong `api/services/embedding.py`:

- Embedding cache hit/miss
- Batch latency
- Total inputs
- Uncached inputs

### 10.5. Ingestion metrics

Trong `api/services/ingestion.py`:

- Trạng thái `ready` hoặc `error`
- Tổng latency ingest
- Tổng số chunks đã lưu

## 11. Metrics API

File chính:

- `api/routers/metrics.py`

### 11.1. Public-ish runtime endpoint

- `GET /api/v1/metrics/runtime`

Dùng để xem nhanh memory/runtime snapshot.

### 11.2. Admin summary endpoint

- `GET /api/v1/metrics/summary`

Yêu cầu admin auth.

Trả về:

- Totals theo route
- Status codes
- Latency summary theo route
- Hottest routes
- Error routes
- Query counts/latency
- Retrieval latency
- RAG latency
- Embedding stats
- Cache counters
- Ingestion stats

### 11.3. Admin analytics endpoint

- `GET /api/v1/metrics/analytics`

Yêu cầu admin auth.

Endpoint này không chỉ trả counters thô mà còn suy diễn thêm các chỉ số vận hành:

- `requests_per_minute`
- `queries_per_minute`
- `ingestions_per_hour`
- `request_error_rate`
- `ingestion_error_rate`
- cache hit rate theo từng loại cache
- latency trung bình/p95 cho retrieval và RAG
- hotspot routes và query mix

Logic này nằm trong:

- `api/services/metrics_analytics.py`

Mục tiêu là giúp đọc nhanh tình trạng hệ thống mà không cần tự chia nhỏ từ raw snapshot.

### 11.4. Prometheus export endpoint

- `GET /api/v1/metrics/prometheus`

Yêu cầu admin auth.

Endpoint này trả về `text/plain` theo kiểu Prometheus exposition format để dễ tích hợp với:

- Prometheus scrape
- Grafana dashboard
- các hệ thống giám sát bên ngoài

Hiện tại exporter đang xuất các metric chính:

- uptime
- tổng HTTP requests theo route
- tổng response theo status code
- tổng RAG queries theo task type
- cache hit/miss
- ingestion states
- Python heap memory
- retrieval avg latency
- RAG avg latency

Logic export nằm trong:

- `api/services/prometheus_exporter.py`

## 12. Persist metrics vào Redis

Các file chính:

- `api/main.py`
- `api/core/redis_client.py`
- `api/services/metrics_registry.py`
- `api/routers/metrics.py`

### 12.1. Vấn đề

Metrics registry hiện nằm trong memory của process. Nếu process restart:

- Tất cả số liệu runtime sẽ mất

### 12.2. Cách triển khai

Đã thêm:

- `CacheManager.get_metrics_snapshot()`
- `CacheManager.set_metrics_snapshot()`
- Background task persist định kỳ
- Restore khi startup
- Persist lần cuối ở shutdown

Key Redis:

- `metrics:snapshot`

### 12.3. Luồng startup

Khi app khởi động:

1. Tuning GC
2. Start `tracemalloc`
3. Đọc `metrics:snapshot` từ Redis nếu có
4. `MetricsRegistry.restore(snapshot)`
5. Tạo background task persist định kỳ

### 12.4. Luồng shutdown

Khi app dừng:

1. Hủy task persist định kỳ
2. Ghi snapshot cuối cùng vào Redis

### 12.5. Endpoint persisted metrics

API:

- `GET /api/v1/metrics/persisted`

Yêu cầu admin auth.

Trả về snapshot gần nhất đã lưu ở Redis.

### 12.6. Giới hạn restore

Restore hiện là restore mức summary, không phải replay toàn bộ raw history. Điều đó có nghĩa:

- Counters và summary cơ bản được giữ lại
- `recent` window không khôi phục đầy đủ dữ liệu gốc
- `p95_recent` sau restore chỉ mang tính gần đúng

Đây là trade-off chấp nhận được cho monitoring nhẹ.

## 13. Cấu hình mới đã thêm

Trong `api/core/config.py` đã bổ sung các setting sau:

### Ingestion và embedding

- `pdf_page_batch_size`
- `ingestion_store_batch_size`
- `embedding_batch_size`
- `embedding_max_concurrency`
- `embedding_max_retries`
- `ingestion_progress_ttl`

### Retrieval và rerank

- `query_expansion_ttl`
- `reranker_max_candidates`
- `retrieval_prefetch_neighbors`

### Runtime

- `gc_threshold_gen0`
- `gc_threshold_gen1`
- `gc_threshold_gen2`
- `memory_monitor_enabled`
- `memory_soft_limit_mb`
- `memory_hard_limit_mb`

### Metrics persistence

- `metrics_snapshot_ttl`
- `metrics_persist_interval_seconds`

## 14. Test coverage đã thêm

Các test đã thêm hoặc cập nhật:

- `api/tests/test_embedding.py`
- `api/tests/test_retrieval.py`
- `api/tests/test_metrics_registry.py`
- cập nhật `api/tests/test_pdf_processor.py`
- cập nhật `api/tests/test_query_expander.py`
- cập nhật `api/tests/test_reranker.py`
- cập nhật `api/tests/conftest.py`

### Nội dung test chính

- Dedup text trong embedding
- `chunk_index` liên tục khi batch ingest
- Query expansion cache behavior
- Candidate trimming cho rerank
- Metrics snapshot và restore

## 15. Những endpoint mới/cập nhật quan trọng

### Books

- `GET /api/v1/books/{book_id}/ingestion-status`

### Metrics

- `GET /api/v1/metrics/runtime`
- `GET /api/v1/metrics/summary`
- `GET /api/v1/metrics/persisted`
- `GET /api/v1/metrics/analytics`
- `GET /api/v1/metrics/prometheus`

### Health

- `GET /health`
  Bây giờ bao gồm thêm thông tin runtime

## 16. Các giới hạn hiện tại

Hệ thống đã tốt hơn đáng kể, nhưng vẫn còn các giới hạn sau:

### Ingestion

- Vẫn chạy trong process FastAPI, chưa tách thành worker queue
- OCR vẫn là CPU-bound tại process hiện tại

### Monitoring

- Metrics registry là in-memory + snapshot summary, chưa phải observability stack đầy đủ
- Chưa có chart/dashboard UI riêng
- Prometheus exporter hiện mới cover nhóm metric chính, chưa đầy đủ như production observability stack lớn

### Memory

- Memory guard dựa trên Python heap, chưa phải RSS thật của OS

### Retrieval analytics

- Chưa có persistence chi tiết theo time-series
- Chưa có breakdown theo từng sách hoặc từng user

## 17. Hướng đi tiếp theo hợp lý

Nếu tiếp tục nâng hệ thống, các bước hợp lý nhất là:

### 17.1. Tách worker nền

Cho ingestion/re-ingestion chạy ở worker riêng:

- Celery / RQ / Dramatiq / Arq
- Giảm áp lực lên FastAPI process

### 17.2. Prometheus-style export

Đã có endpoint text export cơ bản, nhưng bước tiếp theo nên là:

- scrape từ Prometheus
- vẽ dashboard Grafana
- chuẩn hóa naming/label strategy
- thêm histogram buckets hoặc integration với exporter chuẩn hơn

### 17.3. Query analytics bền vững hơn

Lưu thống kê theo time-series vào:

- Redis sorted set
- Supabase table
- hoặc external TSDB

### 17.4. RSS-based memory monitoring

Nếu muốn bảo vệ memory thật tốt hơn:

- đo RSS thực của process
- hoặc tích hợp `psutil`

## 18. Kết luận

Sau các bước triển khai này, backend hiện tại đã tiến từ một hệ thống RAG POC cơ bản sang một hệ thống có các đặc điểm production-friendly hơn:

- ingest theo lô
- tracking tiến độ
- retrieval và rerank tiết kiệm chi phí hơn
- monitoring runtime
- guard khi quá tải memory
- metrics request/query/cache/ingestion
- persistence snapshot metrics qua Redis

Điểm quan trọng nhất là các thay đổi này không chỉ là checklist, mà đã được nối trực tiếp vào codepath thật của hệ thống:

- upload sách
- ingest nền
- retrieval
- rerank
- RAG query blocking/streaming
- health/metrics/admin observability

Đây là nền đủ tốt để tiếp tục đi tiếp sang worker hóa, analytics dài hạn, và observability chuẩn production.
