# Quy trình Phát triển & Triển khai (CI/CD Workflow)

Tài liệu này dùng để tra cứu mỗi khi bạn code thêm tính năng mới cho dự án Ebook Platform và muốn đưa thay đổi đó lên môi trường thật. Hiện hệ thống chạy trên các thành phần chính:

1. **Supabase**: Database PostgreSQL + pgvector + Storage
2. **Redis**: Cache, queue cho ingestion jobs, persisted metrics snapshot
3. **Render.com**: Hosting cho Backend FastAPI và worker ingestion
4. **Vercel**: Hosting cho Frontend Next.js

---

## 1. Môi trường Local (Khi đang lập trình)

Khi code và test tại máy cá nhân, nên chạy ít nhất frontend + backend. Nếu đang làm phần upload/ingestion, nên chạy thêm worker riêng.

**Terminal 1 (Chạy Backend API):**
```bash
cd api
source venv/bin/activate
uvicorn main:app --port 8001 --reload
```

**Terminal 2 (Tuỳ chọn - Chạy Worker ingestion riêng):**
```bash
cd api
source venv/bin/activate
python worker.py
```

**Terminal 3 (Chạy Frontend):**
```bash
cd web
npm run dev
```

> **Lưu ý Environment Variables ở Local:**
> - File `api/.env`: chứa kết nối Supabase, Redis, OpenAI, JWT và các setting runtime
> - File `web/.env.local`: trỏ API về máy cá nhân, ví dụ `NEXT_PUBLIC_API_URL=http://localhost:8001/api/v1`

---

## 2. Quy trình cập nhật & đưa lên Production

Khi bạn viết xong code ở máy và đã test ổn, hãy làm theo quy trình sau.

### Bước 1: Kiểm tra thay đổi liên quan Database / Supabase

Nếu thay đổi của bạn có liên quan đến:

- bảng mới
- cột mới
- index mới
- function SQL mới hoặc sửa function SQL cũ
- tối ưu `hybrid_search`

thì phải apply migration trên Supabase trước hoặc cùng đợt deploy backend.

Thư mục migration:
```bash
supabase/migrations/
```

Ví dụ migration mới:
```bash
supabase/migrations/005_hybrid_search_optimization.sql
```

**Đọc migration trước khi chạy:**
```bash
sed -n '1,240p' supabase/migrations/005_hybrid_search_optimization.sql
```

**Cách apply migration**

**Cách A - Dùng Supabase CLI**
```bash
supabase link --project-ref <PROJECT_REF>
supabase db push
```

**Cách B - Dùng Supabase SQL Editor**
1. Mở [Supabase Dashboard](https://supabase.com/dashboard)
2. Vào **SQL Editor**
3. Paste nội dung migration
4. Chạy query

**Kiểm tra sau khi apply**

Kiểm tra index:
```sql
select indexname
from pg_indexes
where tablename = 'book_chunks';
```

Kiểm tra function:
```sql
select pg_get_functiondef('hybrid_search(uuid, vector, text, integer, double precision, double precision)'::regprocedure);
```

### Bước 2: Commit và Push mã nguồn lên GitHub

```bash
git add .
git commit -m "feat: [tên tính năng vừa làm]"
git push origin main
```

### Bước 3: Deploy Backend API trên Render.com

Render đóng vai trò là service HTTP chính.

1. Truy cập [Render Dashboard](https://dashboard.render.com)
2. Vào Web Service backend của bạn
3. Nếu đã cấu hình GitHub Auto-Deploy, bước này diễn ra tự động
4. Nếu không tự động:
   - Nhấp **Manual Deploy**
   - Chọn **Deploy latest commit**
   - Chờ trạng thái **Live**

### Bước 4: Deploy Worker ingestion riêng trên Render.com

Từ khi hệ thống có Redis-backed ingestion queue, nên deploy worker riêng thay vì để API process ôm hết tác vụ nặng.

**Khuyến nghị:**

Tạo thêm một service riêng trên Render:

- cùng repository
- cùng biến môi trường backend
- không phục vụ HTTP

**Build Command:**
```bash
cd api && pip install -r requirements.txt
```

**Start Command:**
```bash
cd api && python worker.py
```

Nếu chưa tách worker riêng, backend vẫn có thể chạy worker loop trong cùng process khi:

```env
INGESTION_WORKER_ENABLED=true
```

Nhưng cách này chỉ nên xem là giải pháp tạm hoặc cho môi trường nhỏ.

### Bước 5: Deploy Frontend trên Vercel

1. Sau khi `git push`, Vercel thường tự động build
2. Kiểm tra trạng thái trong [Vercel Dashboard](https://vercel.com/dashboard)
3. Khi build báo xanh, frontend mới đã live

> **Lưu ý Environment Variables trên Vercel:**
> - Đi tới `Settings > Environment Variables`
> - Đảm bảo `NEXT_PUBLIC_API_URL` trỏ về backend thật, ví dụ:
>   `https://ebook-api-7v44.onrender.com/api/v1`
> - Tuyệt đối không để `localhost`

---

## 2.1. Biến môi trường backend hiện tại

Ngoài các biến cũ, hệ thống hiện có thêm các biến quan trọng sau.

### Redis / Queue / Worker
```env
REDIS_URL=redis://localhost:6379
INGESTION_QUEUE_NAME=queue:ingestion_jobs
INGESTION_WORKER_ENABLED=true
INGESTION_WORKER_CONCURRENCY=1
INGESTION_WORKER_POLL_TIMEOUT=5
```

### Upload / Ingestion
```env
MAX_UPLOAD_SIZE_MB=150
PDF_PAGE_BATCH_SIZE=16
INGESTION_STORE_BATCH_SIZE=50
INGESTION_PROGRESS_TTL=86400
```

### Embedding
```env
EMBEDDING_BATCH_SIZE=100
EMBEDDING_MAX_CONCURRENCY=4
EMBEDDING_MAX_RETRIES=5
EMBEDDING_CACHE_COMPRESSION_ENABLED=true
EMBEDDING_CACHE_PRECISION=6
```

### Retrieval / Query
```env
QUERY_EXPANSION_TTL=21600
RERANKER_MAX_CANDIDATES=24
RETRIEVAL_PREFETCH_NEIGHBORS=1
```

### Memory / Runtime
```env
MEMORY_MONITOR_ENABLED=true
MEMORY_SOFT_LIMIT_MB=512
MEMORY_HARD_LIMIT_MB=768
GC_THRESHOLD_GEN0=700
GC_THRESHOLD_GEN1=10
GC_THRESHOLD_GEN2=10
```

### Metrics persistence
```env
METRICS_SNAPSHOT_TTL=86400
METRICS_PERSIST_INTERVAL_SECONDS=60
```

> Lưu ý:
> - Với `pydantic-settings`, env vars sẽ map vào các field snake_case trong `api/core/config.py`
> - Nếu không set, hệ thống dùng default trong code

---

## 2.2. Flow deploy khuyến nghị khi có migration Supabase

Khi thay đổi liên quan cả SQL lẫn backend, thứ tự an toàn nên là:

1. Review migration trong `supabase/migrations/`
2. Apply migration lên Supabase
3. Push code lên GitHub
4. Deploy Backend API
5. Deploy Worker ingestion
6. Kiểm tra health + metrics + smoke test query thật

Flow này đặc biệt quan trọng nếu bạn sửa:

- function `hybrid_search`
- index của `book_chunks`
- schema `books` / `book_chunks`
- queue/worker logic mà phụ thuộc Redis hoặc trạng thái sách

---

## 2.3. Checklist sau deploy backend

Sau khi deploy, nên kiểm tra tối thiểu:

### API health
```bash
curl https://<backend-domain>/health
```

### Runtime metrics
```bash
curl https://<backend-domain>/api/v1/metrics/runtime
```

### Queue / Worker
- Upload một file PDF nhỏ
- Kiểm tra trạng thái sách đi qua:
  - `queued`
  - `processing`
  - `ready`

### Supabase
- Kiểm tra `book_chunks` đã được insert
- Kiểm tra `hybrid_search` vẫn trả kết quả đúng

### Worker
- Kiểm tra log worker
- Đảm bảo không có job bị kẹt mãi ở `queued`

---

## 2.4. Kiểm tra migration hybrid_search

Migration mới:
```bash
supabase/migrations/005_hybrid_search_optimization.sql
```

Migration này làm các việc chính:

- thêm GIN index cho full-text search trên `book_chunks.content`
- thay function `hybrid_search(...)`
- kết hợp vector rank + lexical rank bằng reciprocal rank fusion

Sau khi apply, nên kiểm tra:

```sql
select indexname
from pg_indexes
where tablename = 'book_chunks';
```

Bạn nên thấy index như:

- `book_chunks_content_fts_idx`

---

## 2.5. Kiến trúc deploy hiện tại

Hiện hệ thống phù hợp nhất với mô hình:

### Thành phần 1: Frontend
- Vercel

### Thành phần 2: Backend API
- Render Web Service
- Chạy `uvicorn`
- Phục vụ HTTP API

### Thành phần 3: Worker ingestion
- Render Web Service hoặc Background Worker riêng
- Chạy `python worker.py`
- Poll Redis queue để xử lý `ingest` / `reingest`

### Thành phần 4: Supabase
- PostgreSQL + pgvector
- Storage bucket `books`, `covers`
- SQL functions/migrations

### Thành phần 5: Redis
- Cache
- Queue cho ingestion jobs
- Persist metrics snapshot

---

## 3. Quản lý Admin mặc định

Database Supabase hiện đang lưu trữ:

- **Tài khoản Admin mặc định:** `admin`
- **Mật khẩu:** `admin123`

Bạn có thể thay đổi sau khi login vào hệ thống.

---

## 4. Tóm tắt lỗi phổ biến & cách xử lý

- **Frontend báo `Failed to Fetch` hoặc quay mãi**:
  Frontend đang gọi sai API hoặc backend Render chưa deploy kịp code mới. Kiểm tra lại backend deploy và `NEXT_PUBLIC_API_URL`.

- **Lỗi 500 khi thao tác sách hoặc query**:
  Có thể Database/Supabase chưa apply migration mới. Kiểm tra lại các file trong `supabase/migrations/`.

- **Upload xong nhưng sách đứng mãi ở `queued`**:
  Worker ingestion chưa chạy hoặc không kết nối được Redis. Kiểm tra worker service và `REDIS_URL`.

- **Hybrid search trả kết quả kém hoặc lỗi RPC sau deploy**:
  Có thể backend mới nhưng Supabase chưa apply migration `005_hybrid_search_optimization.sql`.

- **Worker chạy nhưng re-ingest không hoàn tất**:
  Kiểm tra:
  - quyền đọc file từ bucket `books`
  - log worker
  - trạng thái Redis queue

- **API bị trả `503` do quá tải bộ nhớ**:
  Memory guard đang kích hoạt. Kiểm tra:
  - `/health`
  - `/api/v1/metrics/runtime`
  - soft/hard limit trong env
