# Phương án Tích hợp — AI Book Engine (API-Only)

> **Mục đích:** Phân tích cách rút gọn hệ thống hiện tại thành một **dịch vụ API thuần** (headless), chỉ cung cấp 2 chức năng cốt lõi cho hệ thống NXB:
> 1. Nhận file PDF → xử lý → tạo vector embedding
> 2. Nhận câu hỏi + book_id → trả lời bằng AI

---

## 1. So sánh Hệ thống Hiện tại vs. Phương án Rút gọn

### Hệ thống hiện tại (Full-stack)

```
┌─────────────────────────────────────────────────────────┐
│  FRONTEND (Next.js — Vercel)                            │
│  - Trang chủ, danh sách sách, chi tiết sách            │
│  - Giao diện upload sách (cho Admin)                    │
│  - Giao diện chat AI                                    │
│  - Quản lý danh mục, metadata                          │
│  - Đăng nhập / Phân quyền Admin                        │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│  BACKEND (FastAPI — Render.com)                         │
│  - Auth (JWT, đăng nhập, phân quyền)                   │
│  - Upload sách (lưu file, metadata, danh mục)          │
│  - Ingestion pipeline (extract, chunk, embed, store)   │
│  - RAG Engine (retrieval + AI chat)                    │
│  - Admin API (config AI, logs, chỉnh metadata)         │
│  - Google Sheets logger                                │
│  - Quản lý danh mục sách                               │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│  DATABASE (Supabase)                                    │
│  - books, book_chunks, categories, users                │
│  - query_logs                                          │
│  - Supabase Storage (PDF, ảnh bìa)                     │
└─────────────────────────────────────────────────────────┘
```

### Phương án rút gọn (API-Only)

```
┌─────────────────────────────────────────────────────────┐
│  HỆ THỐNG NXB (Đã có sẵn)                              │
│  - Phần mềm biên mục → gọi API ingest                  │
│  - Trang đọc sách → nhúng widget chat AI                │
└────────────┬───────────────────────┬────────────────────┘
             │ POST /ingest          │ POST /chat
             ▼                       ▼
┌─────────────────────────────────────────────────────────┐
│  AI BOOK ENGINE (FastAPI — API Only)                    │
│  - Xác thực bằng API Key (shared secret)               │
│  - POST /ingest  → Nhận PDF, xử lý, tạo embedding     │
│  - POST /chat    → Nhận câu hỏi + book_id, trả lời AI │
│  - GET  /status  → Kiểm tra trạng thái sách            │
│  - DELETE /books → Xóa sách khi NXB yêu cầu           │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│  DATABASE (Supabase)                                    │
│  - books (chỉ id, status, total_pages)                  │
│  - book_chunks (content + embedding)                   │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Những gì GIỮ LẠI (Cốt lõi)

### 2.1. Ingestion Pipeline ✅
Đây là trái tim của hệ thống — không thể bỏ.

| Module | File hiện tại | Chức năng |
|--------|-------------|-----------|
| PDF Processor | `services/pdf_processor.py` | Đọc PDF → trích xuất text → chia chunks |
| Embedding Service | `services/embedding.py` | Gọi OpenAI tạo vector cho mỗi chunk |
| Ingestion Orchestrator | `services/ingestion.py` | Điều phối toàn bộ pipeline |
| Chunk Storage | `services/ingestion.py` | Lưu chunks + vectors vào Supabase |

### 2.2. RAG Engine ✅
Chức năng hỏi đáp AI — lý do chính của dịch vụ.

| Module | File hiện tại | Chức năng |
|--------|-------------|-----------|
| Retrieval | `services/retrieval.py` | Tìm kiếm vector + full-text search |
| Query Expander | `services/query_expander.py` | Mở rộng câu hỏi tăng recall |
| Reranker | `services/reranker.py` | Xếp hạng lại kết quả tìm kiếm |
| RAG Engine | `services/rag_engine.py` | Xây prompt + gọi OpenAI + streaming |

### 2.3. Database ✅ (rút gọn)

Chỉ cần 2 bảng chính:

```sql
-- Bảng books: chỉ lưu trạng thái, không cần metadata phong phú
CREATE TABLE books (
    id UUID PRIMARY KEY,
    external_id TEXT,          -- ID sách từ hệ thống NXB (để mapping)
    status TEXT DEFAULT 'processing',  -- processing | ready | error
    total_pages INT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Bảng book_chunks: giữ nguyên
CREATE TABLE book_chunks (
    id UUID PRIMARY KEY,
    book_id UUID REFERENCES books(id),
    chunk_index INT,
    page_number INT,
    content TEXT,
    embedding VECTOR(1536)
);
```

### 2.4. Xác thực API ✅ (đơn giản hóa)

Thay vì JWT + login, chỉ cần **API Key** (shared secret):

```
Authorization: Bearer sk-nxb-abc123xyz
```

NXB được cấp 1 API Key, gắn vào header mỗi request. Đơn giản, không cần quản lý user.

---

## 3. Những gì BỎ ĐI

### 3.1. Toàn bộ Frontend ❌

| Thành phần | Lý do bỏ |
|-----------|----------|
| Trang chủ, danh sách sách | NXB đã có trang riêng |
| Giao diện upload sách | NXB gọi API từ phần mềm biên mục |
| Giao diện chi tiết sách | NXB đã có trang đọc sách |
| Giao diện chat AI | NXB tự nhúng widget chat vào trang đọc sách |
| Quản lý danh mục | Không cần — NXB quản lý danh mục ở hệ thống của họ |

→ **Bỏ toàn bộ thư mục `web/`** và dịch vụ Vercel.

### 3.2. Các module Backend không cần ❌

| Module | File | Lý do bỏ |
|--------|------|----------|
| Auth (JWT, login, register) | `core/auth.py`, `routers/auth.py` | Thay bằng API Key đơn giản |
| Users management | `routers/users.py` | Không có user cuối |
| Categories | `routers/categories.py` | NXB quản lý danh mục riêng |
| Admin config UI | `routers/admin.py` (phần config) | Cấu hình bằng biến môi trường |
| Google Sheets logger | `services/sheets_logger.py` | Có thể bỏ hoặc giữ tùy nhu cầu |
| Metadata extractor (bìa, AI summary) | `services/metadata_extractor.py` | NXB đã có metadata, ảnh bìa riêng |
| Embed/public API | `routers/embed.py` | Không cần nhúng iframe |
| Book CRUD (upload qua form) | `routers/books.py` | Thay bằng endpoint `/ingest` đơn giản |

### 3.3. Database tables không cần ❌

| Bảng | Lý do bỏ |
|------|----------|
| `users` | Không có user cuối |
| `categories` | NXB quản lý riêng |
| `query_logs` | Tùy chọn — có thể giữ để theo dõi |

### 3.4. Dịch vụ hosting bỏ ❌

| Dịch vụ | Lý do bỏ |
|---------|----------|
| **Vercel** | Không có frontend |
| **Supabase Storage** | NXB tự lưu file PDF — chỉ truyền bytes qua API |

---

## 4. API Endpoints Sau Rút gọn

Toàn bộ dịch vụ chỉ còn **4-5 endpoints**:

### 4.1. Ingest sách mới

```
POST /api/v1/ingest
Authorization: Bearer {API_KEY}
Content-Type: multipart/form-data

Body:
  - file: (file PDF)
  - external_id: "ISBN-978-604-xxx" (ID sách từ hệ thống NXB)
```

Response:
```json
{
  "book_id": "uuid-xxx",
  "external_id": "ISBN-978-604-xxx",
  "status": "processing",
  "message": "Đang xử lý, ước tính 3-5 phút"
}
```

### 4.2. Kiểm tra trạng thái

```
GET /api/v1/books/{book_id}/status
Authorization: Bearer {API_KEY}
```

Response:
```json
{
  "book_id": "uuid-xxx",
  "status": "ready",
  "total_pages": 944,
  "total_chunks": 1823
}
```

### 4.3. Hỏi đáp AI (Streaming)

```
POST /api/v1/chat
Authorization: Bearer {API_KEY}
Content-Type: application/json

Body:
{
  "book_id": "uuid-xxx",
  "question": "Mục lục cuốn sách này gồm những gì?",
  "task_type": "qa"
}
```

Response: **Server-Sent Events (SSE)** — text AI xuất hiện dần từng từ.

### 4.4. Xóa sách

```
DELETE /api/v1/books/{book_id}
Authorization: Bearer {API_KEY}
```

### 4.5. (Tùy chọn) Hỏi đáp không streaming

```
POST /api/v1/chat/sync
Authorization: Bearer {API_KEY}
```

Response: JSON đầy đủ, chờ AI trả lời xong mới trả về.

---

## 5. Cấu trúc Thư mục Sau Rút gọn

```
api/
├── main.py                    # FastAPI app (rút gọn)
├── core/
│   ├── config.py              # Cấu hình (OpenAI key, Supabase, API key)
│   ├── openai_client.py       # OpenAI client
│   ├── supabase_client.py     # Supabase client
│   └── api_key_auth.py        # ← MỚI: Xác thực bằng API Key
├── routers/
│   ├── ingest.py              # ← MỚI: POST /ingest
│   ├── chat.py                # ← MỚI: POST /chat (gộp từ rag.py)
│   └── books.py               # GET /status, DELETE /books
├── services/
│   ├── pdf_processor.py       # Giữ nguyên
│   ├── embedding.py           # Giữ nguyên
│   ├── ingestion.py           # Rút gọn (bỏ upload storage, metadata)
│   ├── retrieval.py           # Giữ nguyên
│   ├── query_expander.py      # Giữ nguyên
│   ├── reranker.py            # Giữ nguyên
│   └── rag_engine.py          # Giữ nguyên
├── models/
│   └── schemas.py             # Rút gọn
├── requirements.txt           # Bỏ pytesseract, Pillow
└── .env
```

**Bỏ hoàn toàn:**
- `web/` (toàn bộ frontend)
- `routers/auth.py`, `routers/users.py`, `routers/categories.py`, `routers/embed.py`
- `routers/admin.py` (hoặc giữ lại phần reingest nếu cần)
- `services/metadata_extractor.py` (NXB đã có metadata)
- `services/sheets_logger.py` (tùy chọn)
- `services/ai_config_service.py` (cấu hình qua .env)

---

## 6. Cách NXB Tích hợp

### 6.1. Phần mềm biên mục (Backend → Backend)

```
Biên mục viên xuất bản sách
        │
        ▼
┌──────────────────┐     POST /ingest (gửi PDF)     ┌──────────────┐
│  Phần mềm NXB   │ ──────────────────────────────▶ │ AI Book      │
│  (Biên mục)      │                                 │ Engine API   │
│                  │ ◀────────────────────────────── │              │
└──────────────────┘   { book_id, status }           └──────────────┘
```

NXB chỉ cần gọi 1 API khi xuất bản sách, lưu lại `book_id` trả về để mapping với sách trong hệ thống của họ.

### 6.2. Trang đọc sách (Frontend → Backend)

```
Bạn đọc mở sách trên web NXB
        │
        ▼
┌──────────────────┐    POST /chat (book_id + câu hỏi)   ┌──────────────┐
│  Trang đọc sách  │ ──────────────────────────────────▶  │ AI Book      │
│  của NXB         │                                      │ Engine API   │
│  (có widget AI)  │ ◀─────── SSE stream (câu trả lời) ─ │              │
└──────────────────┘                                      └──────────────┘
```

NXB nhúng một component chat (JavaScript) vào trang đọc sách, truyền `book_id` và gọi trực tiếp endpoint `/chat`.

---

## 7. Tổng kết

| Tiêu chí | Hệ thống Full-stack (hiện tại) | API-Only (rút gọn) |
|----------|-------------------------------|---------------------|
| Số endpoint API | ~15-20 | **4-5** |
| Số file code | ~40+ files | **~15 files** |
| Dịch vụ hosting | 3 (Vercel + Render + Supabase) | **2 (Render + Supabase)** |
| Chi phí hosting | $0-32/tháng | **$0-25/tháng** |
| Bảng database | 5 bảng | **2 bảng** |
| Thời gian triển khai | Đã hoàn thiện | ~1-2 ngày refactor |
| Bảo trì | Phức tạp (full-stack) | **Đơn giản (chỉ backend)** |
| Phù hợp với | Sản phẩm độc lập | **Tích hợp vào hệ thống có sẵn** |

**Kết luận:** Khi chỉ cần tích hợp API với hệ thống NXB, có thể loại bỏ **~60-70% codebase hiện tại** (toàn bộ frontend, auth, quản lý danh mục, metadata). Phần còn lại là **lõi AI thuần túy**: nhận PDF → xử lý → hỏi đáp. Đơn giản, nhẹ, dễ bảo trì.
