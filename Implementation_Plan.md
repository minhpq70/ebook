# 🚀 Kế Hoạch Triển Khai Tối Ưu Hiệu Năng Ebook Platform

## 📊 Các Vấn Đề Hiệu Năng Hiện Tại

### 1. Điểm nghẽn xử lý PDF
- **Xử lý OCR**: trước đây xử lý tuần tự với 300 DPI cho toàn bộ PDF
- **Sử dụng bộ nhớ**: dễ phải nạp quá nhiều dữ liệu PDF/chunk vào RAM cùng lúc
- **Ràng buộc CPU**: OCR và trích xuất PDF vẫn là tác vụ nặng, chưa tách sang worker riêng

### 2. Điểm chưa tối ưu ở embedding
- **Gọi API tuần tự**: trước đây các batch embedding chưa được tối ưu song song tốt
- **Tính lại embedding lặp lại**: nếu nội dung trùng nhau sẽ tốn chi phí không cần thiết
- **Lãng phí bộ nhớ/cache**: embedding cache cần tối ưu thêm về cách lưu trữ

### 3. Hiệu năng cơ sở dữ liệu
- **Chỉ mục HNSW**: đã tối ưu phần migration, nhưng hybrid search ở tầng SQL/RPC vẫn còn dư địa cải thiện
- **Tối ưu truy vấn**: vẫn còn phần logic đang tối ưu ở app layer thay vì DB layer
- **Kết nối**: đã có connection reuse, nhưng chưa có mô hình scale/read replica

### 4. Hạ tầng cache
- **Chưa có cache nhiều tầng thực sự**: hiện chủ yếu là Redis + in-memory metrics
- **Cache warming**: chưa triển khai
- **Consistency/distributed locking**: chưa triển khai

---

## 🎯 Mục Tiêu Hiệu Năng

| Chỉ số | Hiện tại | Mục tiêu | Cải thiện |
|--------|---------|----------|-----------|
| Xử lý PDF (1000 trang) | ~5-10 phút | ~1-2 phút | **Nhanh hơn 5x** |
| Embedding (1000 chunks) | ~2-3 phút | ~30 giây | **Nhanh hơn 6x** |
| Thời gian phản hồi truy vấn | ~3-5 giây | ~1-2 giây | **Nhanh hơn 3x** |
| Sử dụng bộ nhớ | Cao | Tối ưu hơn | **Giảm 50%** |
| Tỷ lệ cache hit | 0% | 80% | **Tính năng mới** |
| Người dùng đồng thời | ~10 | ~100 | **Tăng 10x** |

---

## 📋 Các Giai Đoạn Triển Khai

### Phase 1: Sửa lỗi trọng yếu (Tuần 1) ✅ HOÀN THÀNH

#### 1.1 Tối ưu OCR thông minh
**Tệp:** `api/services/pdf_processor.py`
- [x] Triển khai phát hiện OCR thông minh (bỏ qua OCR nếu text tiếng Việt hợp lệ)
- [x] Giảm DPI từ 300 xuống 200 cho tác vụ OCR
- [x] Thêm crop lề trang để giảm vùng xử lý
- [~] Xử lý song song bằng semaphore: một phần. Hiện đã tối ưu OCR và ingest theo batch, nhưng chưa có semaphore OCR async hoàn chỉnh như thiết kế ban đầu
- [~] Confidence scoring cho OCR: một phần. Hiện có fallback logic, nhưng chưa có thang điểm confidence định lượng riêng

#### 1.2 Hạ tầng cache Redis
**Tệp:** `api/core/redis_client.py`, `api/services/embedding.py`, `api/services/retrieval.py`
- [x] Thiết lập kết nối Redis với connection pooling
- [x] Triển khai cache embedding với TTL (24 giờ)
- [x] Thêm cache kết quả query (1 giờ)
- [x] Cache metadata sách (6 giờ)
- [x] Thêm chiến lược cache invalidation

#### 1.3 Tối ưu chỉ mục cơ sở dữ liệu
**Tệp:** `supabase/migrations/002_performance_indexes.sql`
- [x] Tối ưu tham số HNSW index (`m=32`, `ef_construction=128`)
- [x] Thêm compound index cho hybrid search
- [x] Tạo partial index cho sách active
- [x] Thêm covering index cho các truy vấn phổ biến

#### 1.4 Connection pooling
**Tệp:** `api/core/supabase_client.py`, `api/core/openai_client.py`
- [x] Triển khai connection pooling cho Supabase
- [x] Thêm connection reuse cho OpenAI client
- [x] Cấu hình pool size và timeout phù hợp

### Phase 2: Tính năng nâng cao (Tuần 2)

#### 2.1 Xử lý PDF dạng streaming/incremental
**Tệp:** `api/services/pdf_processor.py`, `api/services/ingestion.py`
- [x] Triển khai xử lý PDF tăng dần theo batch
- [x] Thêm xử lý chunk tiết kiệm bộ nhớ
- [~] Hỗ trợ file lớn (>100MB): một phần. Upload limit hiện đã cấu hình được (`max_upload_size_mb`, mặc định 150MB), và tác vụ nặng đã được đưa vào Redis queue/worker; tuy nhiên request vẫn đọc file vào memory một lần trước khi upload lên storage
- [x] Theo dõi tiến độ cho tác vụ dài

#### 2.2 Async batch embedding
**Tệp:** `api/services/embedding.py`
- [x] Triển khai embedding đồng thời với semaphore
- [x] Thêm batching request và deduplication
- [x] Triển khai exponential backoff cho rate limit
- [x] Thêm nén embedding cho storage/cache
  Ghi chú: hiện mới nén ở tầng Redis embedding cache, chưa nén vector trong Postgres/pgvector

#### 2.3 Tối ưu truy vấn
**Tệp:** `api/services/retrieval.py`, `api/services/reranker.py`
- [x] Tối ưu hybrid search algorithm
  Ghi chú: đã tối ưu ở cả app layer và DB layer. App layer có candidate preparation + neighbor prefetch; DB layer đã có migration tối ưu `hybrid_search` bằng FTS GIN index + reciprocal rank fusion
- [x] Triển khai pre-fetch kết quả truy vấn/ngữ cảnh lân cận
- [x] Thêm cache cho query expansion
- [x] Tối ưu reranking cho tập ứng viên lớn

#### 2.4 Quản lý bộ nhớ
**Tệp:** `api/main.py`, `api/core/config.py`
- [x] Triển khai memory monitoring
- [x] Thêm tối ưu garbage collection
- [~] Cấu hình worker processes phù hợp: một phần. Đã có Redis-backed ingestion queue, worker loop chạy được trong app process và có `api/worker.py` cho mode standalone; chưa có triển khai supervisor/process manager production-ready
- [x] Thêm circuit breaker dựa trên bộ nhớ
  Ghi chú: hiện có soft/hard guard theo Python heap và loại endpoint; worker queue đã có nhưng deployment model cho worker riêng vẫn chưa hoàn thiện

### Phase 3: Giám sát & Mở rộng quy mô (Tuần 3)

#### 3.1 Giám sát hiệu năng
**Tệp:** `api/services/monitoring.py`, `api/routers/metrics.py`
- [x] Thêm thu thập performance metrics
- [~] Triển khai dashboard/query analytics: một phần. Đã có `/metrics/summary`, `/metrics/analytics`, `/metrics/prometheus`, nhưng chưa có dashboard UI riêng
- [ ] Thêm error tracking và alerting
- [~] Tạo performance regression tests: một phần. Đã có regression tests cho logic metrics/embedding/retrieval, nhưng chưa có benchmark/performance regression test đúng nghĩa

#### 3.2 Hạ tầng auto-scaling
**Tệp:** `docker-compose.yml`, `api/Dockerfile`
- [ ] Triển khai horizontal scaling
- [ ] Thêm cấu hình load balancer
- [ ] Cấu hình Redis cluster cho high availability
- [ ] Thêm database read replicas

#### 3.3 Cache nâng cao
**Tệp:** `api/services/cache_manager.py`
- [ ] Triển khai cache nhiều tầng (L1/L2)
- [ ] Thêm chiến lược cache warming
- [ ] Triển khai giao thức cache consistency
- [ ] Thêm distributed locking cho cache updates

---

## 📌 Tóm Tắt Trạng Thái Thực Tế Của Dự Án

### Đã hoàn thành
- Phase 1 gần như hoàn tất; 2 mục còn lại chỉ đạt mức một phần so với thiết kế lý tưởng ban đầu
- Phase 2 phần lớn đã được triển khai trong codebase hiện tại
- Phase 3.1 đã triển khai được phần monitoring/metrics backend khá đầy đủ

### Đang ở mức một phần
- OCR song song hoàn chỉnh và confidence scoring đầy đủ
- Hỗ trợ file rất lớn theo kiểu streaming end-to-end
- Worker process model tách khỏi FastAPI hoàn toàn
- Dashboard UI cho query analytics
- Performance regression benchmark đúng nghĩa

### Chưa bắt đầu đáng kể
- Phase 3.2 Auto-scaling Infrastructure
- Phase 3.3 Advanced Caching

---

## 🛠 Chi Tiết Kỹ Thuật Đã Được Hiện Thực

### Xử lý PDF tăng dần theo batch

Hệ thống hiện tại đã chuyển từ cách gom toàn bộ trang/chunk vào bộ nhớ sang cách:

1. Đếm tổng số trang PDF
2. Trích xuất text theo batch trang
3. Chunk từng batch ngay khi có text
4. Embed từng batch
5. Ghi từng batch xuống DB
6. Cập nhật progress trong Redis

Điểm đạt được:

- Giảm peak memory tốt hơn so với pipeline cũ
- Cho phép frontend poll tiến độ
- Giảm rủi ro fail toàn pipeline khi tài liệu lớn

### Embedding pipeline hiện tại

Embedding service hiện có:

- Cache embedding Redis
- Dedup text trùng nhau trong cùng batch
- Gọi API theo batch có concurrency control
- Retry/backoff cho lỗi rate limit/kết nối
- Nén embedding payload khi lưu Redis

### Retrieval hiện tại

Retrieval service hiện có:

- Cache query result
- Cache query expansion
- Candidate trimming trước rerank
- Neighbor prefetch để giảm mất ngữ cảnh ở biên chunk

### Memory management hiện tại

Hệ thống hiện có:

- GC tuning ở startup
- Runtime snapshot bằng `tracemalloc`
- Memory guard hai mức:
  - `soft`: chặn endpoint nặng nếu heap vượt soft limit
  - `hard`: chặn gần như mọi request không thiết yếu khi heap vượt hard limit

### Worker hóa ingestion hiện tại

Hệ thống hiện đã có lớp queue/worker cơ bản:

- Upload sách và re-ingest không còn chạy pipeline nặng trực tiếp trong request path
- Request path hiện:
  1. validate file
  2. upload PDF lên storage
  3. tạo `book record`
  4. đưa job vào Redis queue
- Worker sẽ:
  1. lấy job từ queue
  2. tải PDF từ storage
  3. chạy `run_ingestion_pipeline()`

Các thành phần liên quan:

- `api/services/ingestion_queue.py`
- `api/services/ingestion_worker.py`
- `api/worker.py`

Trạng thái hiện tại:

- Có thể chạy worker trong chính FastAPI process
- Có thể chạy standalone worker bằng `api/worker.py`
- Chưa có hạ tầng supervisor/deployment riêng cho worker ở production

### Monitoring hiện tại

Hệ thống monitoring hiện có:

- `/health` kèm runtime snapshot
- `/api/v1/metrics/runtime`
- `/api/v1/metrics/summary`
- `/api/v1/metrics/analytics`
- `/api/v1/metrics/prometheus`
- `/api/v1/metrics/persisted`

Ngoài ra còn có:

- Metrics registry trong memory
- Persist metrics snapshot định kỳ sang Redis
- Restore metrics khi app restart

---

## 🔜 Bước Tiếp Theo Hợp Lý Nhất

Nếu tiếp tục ưu tiên hoàn thành Phase 2, các bước quan trọng nhất còn lại là:

1. Tách ingestion/OCR sang worker queue riêng
2. Tối ưu hybrid search ở tầng SQL/RPC thay vì chỉ ở app layer
3. Hỗ trợ upload/ingest file rất lớn theo streaming thực sự
4. Bổ sung worker model/process model rõ ràng cho backend

Nếu chuyển trọng tâm sang Phase 3, các bước hợp lý là:

1. Làm dashboard admin UI cho metrics/analytics
2. Thêm alerting và error tracking
3. Tích hợp Prometheus/Grafana thực sự
4. Thiết kế cache nhiều tầng và hạ tầng scale-out
