# Quy Trình Xử Lý Sách — Từ Upload Đến Hỏi Đáp

> Tài liệu mô tả chi tiết từng bước khi một cuốn sách PDF (bao gồm cả PDF scan thuần ảnh) được upload vào hệ thống cho đến khi bạn đọc có thể hỏi đáp.

---

## Tổng Quan Pipeline

```
PDF Upload → Validation → Metadata AI → Storage → [Ingestion Pipeline] → Ready → Q&A
                                                          │
                                          ┌───────────────┤
                                          ▼               ▼
                                    Text Extract     OCR (nếu scan)
                                          │               │
                                          └───────┬───────┘
                                                  ▼
                                            Chunking (300 tokens, overlap 80)
                                                  │
                                                  ▼
                                         Embedding (OpenAI text-embedding-3-small)
                                                  │
                                                  ▼
                                         Lưu vectors vào Supabase
                                                  │
                                                  ▼
                                    TOC + Cover + AI Summary
```

---

## Phase 1: Upload & Validation

**File:** `routers/books.py` → `upload_book()`

1. **Kiểm tra file**: PDF header (`%PDF-`), MIME type, kích thước (tối đa 150MB)
2. **Đọc bytes** vào memory
3. **Trích xuất metadata bằng AI**: Nếu admin không nhập đầy đủ title/author/publisher:
   - `metadata_extractor.extract_early_text()`: Lấy text từ 3 trang đầu (PyMuPDF + OCR fallback)
   - Gửi text lên Chat Model (Gemma 4) với prompt "thủ thư chuyên nghiệp" → trả về JSON `{title, author, publisher, published_year}`
4. **Upload PDF lên Supabase Storage** (bucket `books`)
5. **Tạo record trong bảng `books`** (status = `queued`)
6. **Đưa vào hàng đợi ingestion** → trả về `book_id` ngay cho frontend

> ⏱️ Phase này mất ~2-5 giây. Frontend nhận `book_id` để poll tiến độ.

---

## Phase 2: Ingestion Pipeline (chạy nền)

**File:** `services/ingestion.py` → `run_ingestion_pipeline()`

### Bước 2.1: Đếm tổng số trang
- Dùng PyMuPDF (`fitz`) mở PDF, đếm `len(doc)`

### Bước 2.2: Trích xuất text theo batch trang

**File:** `services/pdf_processor.py` → `iter_pdf_page_batches()`

Mỗi batch = 16 trang (cấu hình `PDF_PAGE_BATCH_SIZE`). Với **từng trang**:

```
Trang PDF
   │
   ▼
PyMuPDF get_text() ──→ Có text hợp lệ? ──→ ✅ Dùng text này
   │                         │
   │                         ▼ Không (< 50 ký tự hoặc không phải tiếng Việt)
   │
   ▼
OCR bằng Tesseract (vie model)
   │
   ├─ Render trang thành ảnh (200 DPI, crop 5% margins)
   ├─ pytesseract.image_to_string(img, lang="vie", timeout=30)
   └─ Trả về OCR text
```

> 📌 **PDF scan thuần ảnh**: Mọi trang sẽ đi qua nhánh OCR vì `get_text()` trả về rỗng. Tesseract với model `vie` xử lý tiếng Việt.

### Bước 2.3: Chunking

**File:** `services/pdf_processor.py` → `chunk_pages()`

- Dùng `RecursiveCharacterTextSplitter` từ LangChain
- **Chunk size**: 300 tokens (tối ưu cho tiếng Việt)
- **Overlap**: 80 tokens (giữ ngữ cảnh giữa các chunk)
- **Separators**: `\n\n` → `\n` → `. ` → ` ` (ưu tiên tách theo đoạn văn)
- Đếm tokens bằng `tiktoken` (`cl100k_base` encoding)
- Mỗi chunk có: `content`, `page_number`, `chunk_index`, `token_count`

### Bước 2.4: Embedding

**File:** `services/embedding.py` → `embed_batch()`

- Model: **OpenAI text-embedding-3-small** (1536 dimensions)
- Batch size: 100 texts/lần gọi API
- Concurrency: 4 batch song song
- **Caching**: Redis cache — nếu chunk đã embed trước đó → dùng cache, không gọi API lại
- Retry: exponential backoff (tối đa 5 lần) cho lỗi rate limit/timeout
- Dedup: gom text giống nhau → chỉ embed 1 lần

### Bước 2.5: Lưu vectors vào Supabase

**File:** `services/ingestion.py` → `_store_chunks()`

- Insert vào bảng `chunks` theo batch 50 rows
- Mỗi row: `book_id`, `content`, `page_number`, `chunk_index`, `embedding` (vector 1536D), `token_count`
- Supabase sử dụng pgvector extension cho vector search

### Bước 2.6: Bổ sung metadata

1. **Trích xuất Mục lục (TOC)**
   - `metadata_extractor.extract_toc()`: Lấy từ PDF metadata + quét text trang đầu/cuối + OCR fallback
   - Lưu thành 1 chunk đặc biệt (`page_number = -1`)

2. **Trích xuất ảnh bìa**
   - `metadata_extractor.get_cover_image_bytes()`: Render trang 1 thành JPEG (150 DPI)
   - Upload lên Supabase Storage bucket `covers`

3. **Tạo AI Summary**
   - `metadata_extractor.generate_ai_summary()`: Lấy 15 trang đầu → gửi lên Chat Model → tóm tắt 3-5 câu

4. **Cập nhật status = `ready`** trong bảng `books`

> ⏱️ Phase này mất ~30 giây (PDF text) đến ~5-10 phút (PDF scan 200 trang, phụ thuộc OCR).

---

## Phase 3: Bạn Đọc Hỏi Đáp (Chat/RAG)

**File:** `routers/rag.py` → `query_book()` hoặc `query_book_stream()`

### Bước 3.1: Nhận câu hỏi từ frontend

```json
{
  "book_id": "abc-123",
  "query": "Tác giả muốn nói gì ở chương 3?",
  "task_type": "qa"
}
```

Task types: `qa` (hỏi đáp), `explain` (giải thích), `summarize_chapter`, `summarize_book`, `suggest` (gợi ý đọc thêm)

### Bước 3.2: Retrieval — Tìm chunks liên quan

**File:** `services/retrieval.py` → `retrieve_chunks()`

```
Câu hỏi gốc
   │
   ▼
Query Expansion (Gemma 4)
   ├─ Sinh 2-3 paraphrases tiếng Việt
   └─ Ví dụ: "ý chính chương 3" → "nội dung chương 3", "chủ đề chương ba"
   │
   ▼
Centroid Embedding
   ├─ Embed tất cả query variants
   └─ Tính vector trung bình → embedding đại diện
   │
   ▼
Hybrid Search (Supabase RPC)
   ├─ Vector search (cosine similarity, weight 70%)
   ├─ Full-text search (tsvector tiếng Việt, weight 30%)
   └─ Kết hợp điểm → top 24 candidates
   │
   ▼
Reranking
   ├─ Cross-encoder scoring (embedding similarity giữa query ↔ chunk)
   └─ Chọn top K chunks (mặc định K=8)
   │
   ▼
Context Expansion
   ├─ Prefetch chunks lân cận (trước/sau) cho top hits
   └─ Giữ ngữ cảnh liên tục, tránh cắt giữa ý
```

### Bước 3.3: Prompt Assembly

**File:** `services/rag_engine.py` → `run_rag_query()`

- **System prompt**: Định nghĩa vai trò AI (chuyên gia phân tích sách, trả lời bằng tiếng Việt)
- **Context block**: Ghép nội dung các chunks đã retrieve (`[Trang X, Đoạn Y]: nội dung...`)
- **User message**: Câu hỏi + context + hướng dẫn task type

### Bước 3.4: Gọi Chat Model (Gemma 4 31B)

- Gửi prompt lên Chat Model qua OpenAI-compatible API
- **Streaming**: Text xuất hiện dần (SSE events) giống ChatGPT
- **Non-streaming**: Chờ full response rồi trả về

### Bước 3.5: Response + Logging

- Trả về: `answer` + `sources` (danh sách chunks đã dùng, kèm page number)
- **Log**: Ghi vào file `queries.log` + Supabase `query_logs` + Google Sheets
- **Metrics**: Ghi latency, token count, cost ước tính

---

## Sơ Đồ Tổng Thể

```
┌─────────────────────────────────────────────────────────────────┐
│                        ADMIN UPLOAD                             │
│  PDF file → Validation → AI Metadata → Supabase Storage       │
│                                          → books table (queued) │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │   WORKER    │
                    └──────┬──────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                   INGESTION PIPELINE                            │
│                                                                 │
│  Batch 16 trang ──→ Mỗi trang:                                │
│                      ├─ Text-based? → PyMuPDF get_text()       │
│                      └─ Scan/ảnh?   → OCR Tesseract (vie)      │
│                                                                 │
│  Text ──→ Chunking (300 tokens, overlap 80)                    │
│       ──→ Embedding (OpenAI text-embedding-3-small)            │
│       ──→ Store vectors (Supabase pgvector)                    │
│                                                                 │
│  + TOC extraction + Cover image + AI Summary                   │
│  → books table status = "ready"                                │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      BẠN ĐỌC HỎI ĐÁP                         │
│                                                                 │
│  Câu hỏi ──→ Query Expansion (Gemma 4)                        │
│          ──→ Centroid Embedding                                │
│          ──→ Hybrid Search (vector 70% + FTS 30%)              │
│          ──→ Reranking (cross-encoder)                         │
│          ──→ Context Expansion (chunks lân cận)                │
│          ──→ Prompt Assembly + Gemma 4 Chat                    │
│          ──→ Streaming Response (SSE)                          │
│          ──→ Logging (file + Supabase + Google Sheets)         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Lưu Ý Về PDF Scan

| Đặc điểm | PDF text-based | PDF scan (ảnh) |
|-----------|---------------|----------------|
| `get_text()` | Trả về text đầy đủ | Trả về rỗng hoặc < 50 ký tự |
| OCR | Không cần | Tự động fallback sang Tesseract (hiện tại) |
| Tốc độ ingestion | ~30 giây (100 trang) | ~5-10 phút (200 trang, phụ thuộc OCR) |
| Chất lượng text | Cao (chính xác 100%) | Phụ thuộc chất lượng scan + OCR engine |
| Yêu cầu server | Nhẹ | Cần OCR engine + model tiếng Việt |

> ⚠️ **Trên Render**: Cần đảm bảo OCR engine và language pack `vie` đã được cài trong Dockerfile/build command. Nếu không, OCR sẽ fail silently và fallback về text rỗng.

### 🔜 Kế hoạch nâng cấp OCR

Hiện tại dùng Tesseract (chất lượng tiếng Việt ~70-85%). Đã lên kế hoạch chuyển sang pipeline 2 tầng:
- **Tầng 1**: PaddleOCR (detection + recognition, ~85-90%)
- **Tầng 2**: VietOCR fallback cho các dòng confidence thấp (~92-97%)

→ Chi tiết tại: [OCR_Upgrade_Plan.md](./OCR_Upgrade_Plan.md)

