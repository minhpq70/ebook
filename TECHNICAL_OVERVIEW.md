# Hệ thống Sách điện tử & Hỏi đáp AI — Tổng quan Kỹ thuật

> **Phiên bản:** 1.0 — Tháng 4/2026  
> **Mục đích:** Mô tả quy trình xử lý sách, kiến trúc hệ thống, và quy hoạch năng lực phục vụ

---

## 1. Quy trình Upload & Xử lý Sách

Khi người dùng (Admin) upload một cuốn sách PDF lên hệ thống, quá trình xử lý diễn ra hoàn toàn tự động qua **6 bước** nối tiếp:

### Sơ đồ tổng quan

```
┌──────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Upload  │───▶│  Trích xuất  │───▶│  Tạo Vector  │───▶│   Lưu trữ   │
│   PDF    │    │  Nội dung    │    │  Embedding   │    │  Database    │
└──────────┘    └──────────────┘    └──────────────┘    └──────────────┘
                                                              │
                ┌──────────────┐    ┌──────────────┐          │
                │   Tóm tắt   │◀───│  Trích xuất  │◀─────────┘
                │   bằng AI   │    │   Ảnh bìa    │
                └──────────────┘    └──────────────┘
```

### Chi tiết từng bước

#### Bước 1: Upload file PDF lên kho lưu trữ
- File PDF được gửi từ trình duyệt lên server backend.
- Server chuyển tiếp file lên **Supabase Storage** (kho lưu trữ đám mây).
- Hệ thống ghi nhận thông tin sách vào cơ sở dữ liệu với trạng thái **"Đang xử lý"**.
- Người dùng có thể tiếp tục sử dụng các tính năng khác trong khi chờ đợi.

#### Bước 2: Trích xuất nội dung văn bản
- Server tải PDF về bộ nhớ và đọc nội dung từng trang.
- Mỗi trang được trích xuất thành văn bản thuần (plain text).
- Văn bản được làm sạch: loại bỏ ký tự lỗi, chuẩn hóa khoảng trắng.
- Toàn bộ nội dung được chia nhỏ thành các **đoạn văn bản (chunks)**, mỗi đoạn khoảng 300-500 từ, có phần trùng lặp giữa các đoạn liền kề để không mất ngữ cảnh.

#### Bước 3: Tạo Vector Embedding (⏱ bước chậm nhất)
- Mỗi đoạn văn bản được gửi lên **OpenAI API** để chuyển đổi thành một vector số học 1.536 chiều.
- Vector này đại diện cho "ý nghĩa ngữ nghĩa" của đoạn văn — giúp hệ thống tìm kiếm theo nghĩa chứ không phải theo từ khóa.
- Đây là bước **tốn thời gian nhất** vì phải gọi API bên ngoài nhiều lần qua internet.

#### Bước 4: Lưu trữ vào Cơ sở dữ liệu
- Các đoạn văn bản kèm vector embedding được lưu vào bảng `book_chunks` trong **Supabase PostgreSQL** (có hỗ trợ pgvector).
- Dữ liệu được đánh chỉ mục (index) để tìm kiếm nhanh.

#### Bước 5: Trích xuất Ảnh bìa
- Trang đầu tiên của PDF được render thành ảnh JPEG.
- Ảnh bìa được upload lên kho lưu trữ và gắn vào thông tin sách.

#### Bước 6: Tóm tắt nội dung bằng AI
- Nội dung vài trang đầu của sách (lời nói đầu, mục lục) được gửi cho AI.
- AI tạo một đoạn tóm tắt ngắn gọn về nội dung cuốn sách.
- Trạng thái sách chuyển sang **"Sẵn sàng"** — người dùng có thể bắt đầu hỏi đáp.

---

## 2. Thời gian xử lý ước tính

| Quy mô sách | Số trang | Số đoạn văn bản | Thời gian xử lý |
|-------------|----------|-----------------|-----------------|
| Sách mỏng | 50-100 trang | ~100-200 đoạn | 30 giây – 1 phút |
| Sách trung bình | 200-400 trang | ~400-800 đoạn | 1 – 3 phút |
| Sách dày | 400-700 trang | ~800-1.400 đoạn | 3 – 5 phút |
| Sách rất dày | 700-1.000 trang | ~1.400-2.000 đoạn | 5 – 8 phút |

> **Lưu ý:** Thời gian thực tế phụ thuộc vào tốc độ mạng internet và tải của OpenAI API tại thời điểm xử lý. Trong giờ cao điểm, thời gian có thể tăng thêm 20-30%.

### Phân bổ thời gian theo từng bước (sách 944 trang)

```
Upload PDF .............. ████                           (~10%)
Trích xuất nội dung ..... ██████                         (~15%)
Tạo Vector Embedding .... ████████████████████████████    (~60%) ← chậm nhất
Lưu trữ Database ........ ██████                         (~15%)
Ảnh bìa + Tóm tắt AI ... ██                             (~5%)
```

---

## 3. Quy hoạch Năng lực Hệ thống (Sizing)

### 3.1. Dung lượng lưu trữ

Mỗi cuốn sách khi xử lý sẽ chiếm dung lượng trên 2 thành phần:

| Thành phần | Dữ liệu | Dung lượng / cuốn |
|-----------|----------|-------------------|
| **Supabase Storage** | File PDF gốc | 5-50 MB (tùy sách) |
| **Supabase Database** | Đoạn văn bản + vector embedding | 5-15 MB (tùy số trang) |
| **Supabase Storage** | Ảnh bìa JPEG | 100-300 KB |

### 3.2. Ước tính theo quy mô

| Quy mô | Số sách | Dung lượng Database | Dung lượng Storage | Gói Supabase phù hợp |
|--------|---------|--------------------|--------------------|----------------------|
| Khởi đầu | 1-10 cuốn | ~50-150 MB | ~100-500 MB | **Free** (500 MB DB, 1 GB Storage) |
| Nhỏ | 10-30 cuốn | ~150-450 MB | ~500 MB – 1.5 GB | **Free** (sát giới hạn) |
| Vừa | 30-100 cuốn | ~450 MB – 1.5 GB | ~1.5-5 GB | **Pro** ($25/tháng, 8 GB DB) |
| Lớn | 100-500 cuốn | ~1.5-7.5 GB | ~5-25 GB | **Pro** |
| Rất lớn | 500+ cuốn | 7.5 GB+ | 25 GB+ | **Team** ($599/tháng) |

### 3.3. Tốc độ hỏi đáp AI

Tốc độ trả lời câu hỏi của AI **không bị ảnh hưởng** bởi tổng số sách trong hệ thống, vì:

- Mỗi truy vấn chỉ tìm kiếm trong phạm vi **1 cuốn sách cụ thể**.
- Cơ sở dữ liệu sử dụng thuật toán tìm kiếm vector tối ưu (HNSW Index).
- Thời gian phản hồi trung bình: **2-5 giây** cho bất kỳ quy mô nào.

---

## 4. Chi phí Vận hành

### 4.1. Chi phí cố định hàng tháng

| Dịch vụ | Gói | Chi phí |
|---------|-----|---------|
| **Supabase** (Database + Storage) | Free → Pro | $0 → $25/tháng |
| **Render.com** (Backend API) | Free → Starter | $0 → $7/tháng |
| **Vercel** (Frontend) | Free (Hobby) | $0 |

### 4.2. Chi phí biến đổi (theo lượng sử dụng)

| Hoạt động | Chi phí OpenAI | Ghi chú |
|-----------|---------------|---------|
| Upload 1 cuốn sách (tạo embedding) | ~$0.01 – $0.05 | Trả 1 lần khi upload |
| 1 câu hỏi đáp AI | ~$0.001 – $0.003 | Mỗi lần người dùng hỏi |
| 1.000 câu hỏi đáp AI | ~$1 – $3 | |

> **Ước tính tổng:** Với 50 cuốn sách và 1.000 lượt hỏi đáp/tháng, tổng chi phí vận hành dưới **$30/tháng** (bao gồm cả hạ tầng và AI).

---

## 5. Giới hạn Kỹ thuật Hiện tại

| Giới hạn | Giá trị | Giải pháp nâng cấp |
|----------|---------|-------------------|
| Kích thước file PDF tối đa | ~200 MB | Nén PDF trước khi upload |
| Ngôn ngữ hỗ trợ | Tiếng Việt, Tiếng Anh | Bổ sung thêm ngôn ngữ khi cần |
| Số người dùng đồng thời | ~50-100 (gói Free) | Nâng gói Render/Supabase |
| Định dạng file | Chỉ PDF | Có thể mở rộng sang EPUB, DOCX |

---

## 6. Kiến trúc Hệ thống

```
┌─────────────────────────────────────────────────────────────────┐
│                        NGƯỜI DÙNG                               │
│                    (Trình duyệt Web)                            │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                   FRONTEND (Next.js)                              │
│              Giao diện người dùng — Upload, Chat, Quản lý        │
└──────────────────────┬───────────────────────────────────────────┘
                       │ HTTPS API
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│               BACKEND API (FastAPI — ebook-api)                   │
│          Chỉ phục vụ HTTP — KHÔNG chạy ingestion worker          │
│   ┌─────────────┐ ┌───────────────┐ ┌─────────────────────────┐  │
│   │ Upload &    │ │ Tìm kiếm     │ │  Hỏi đáp AI            │  │
│   │ Queue Job   │ │ Vector       │ │  (RAG Engine)           │  │
│   └─────────────┘ └───────────────┘ └─────────────────────────┘  │
└──────────┬──────────────┬───────────────────┬────────────────────┘
           │              │                   │
           ▼              │                   ▼
┌────────────────┐        │          ┌──────────────────┐
│     Redis      │        │          │   Gemini / AI    │
│  Queue + Cache │        │          │  Embedding + Chat│
└───────┬────────┘        │          └──────────────────┘
        │                 │
        ▼                 ▼
┌────────────────┐ ┌──────────────┐  ┌──────────────────┐
│  WORKER        │ │   Supabase   │  │   Supabase       │
│ (ebook-worker) │ │   Database   │  │   Storage        │
│  Process riêng │ │  (pgvector)  │  │  (PDF + Ảnh bìa) │
│  OCR, Embed,   │ └──────────────┘  └──────────────────┘
│  Chunk, AI     │
└────────────────┘
```

### Kiến trúc Process (PM2)

| Process | Vai trò | Ghi chú |
|---|---|---|
| `ebook-api` | Phục vụ HTTP requests | Không chạy ingestion worker |
| `ebook-worker` | Xử lý ingestion nền (OCR, embed, chunk) | Process riêng, event loop riêng |
| `ebook-web` | Frontend Next.js | |

> **Quan trọng:** Worker PHẢI chạy process riêng. Nếu chạy chung với API (`INGESTION_WORKER_ENABLED=true`), các tác vụ nặng (OCR, embedding) sẽ block event loop → gây lỗi 502/504 cho tất cả API requests.

### Công nghệ sử dụng

| Thành phần | Công nghệ | Vai trò |
|-----------|-----------|---------|
| Giao diện | Next.js, React, TypeScript | Hiển thị danh sách sách, giao diện chat AI |
| Backend | FastAPI, Python | Xử lý API, pipeline upload, RAG engine |
| Worker | Python standalone (`worker.py`) | Ingestion nền: OCR, chunk, embed, AI summary |
| Database | PostgreSQL + pgvector (Supabase) | Lưu trữ metadata, chunks, vector embedding |
| Queue + Cache | Redis | Ingestion queue, embedding cache, progress tracking |
| Lưu trữ file | Supabase Storage | Lưu file PDF gốc và ảnh bìa |
| AI Models | Gemini 2.5 Flash + text-embedding-3-small | Hỏi đáp thông minh + tạo vector |

---

## 7. Câu hỏi Thường gặp

**Q: Tại sao upload sách mất vài phút?**  
A: Bản thân việc upload trả về **trong vài giây**. Phần nặng (OCR, tạo vector embedding, AI summary) chạy ngầm trong worker riêng. Trạng thái sách sẽ chuyển từ `queued` → `processing` → `ready`. Người dùng có thể tiếp tục sử dụng các tính năng khác trong khi chờ đợi.

**Q: Tại sao bị lỗi 502/504 khi upload sách lớn?**  
A: Nguyên nhân thường gặp: worker ingestion đang chạy **chung process** với API. Khi worker xử lý PDF nặng (OCR, embedding), nó block event loop → API không phản hồi được. **Giải pháp:** Đảm bảo `INGESTION_WORKER_ENABLED=false` trong `.env` và chạy `ebook-worker` là process riêng qua PM2.

**Q: Sách càng nhiều thì hệ thống có chậm đi không?**  
A: Không. Mỗi câu hỏi chỉ tìm kiếm trong phạm vi 1 cuốn sách, nên dù có hàng trăm cuốn sách khác trong hệ thống, tốc độ trả lời vẫn giữ nguyên 2-5 giây.

**Q: Hệ thống có thể xử lý sách bằng tiếng nước ngoài không?**  
A: Có. AI hỗ trợ đa ngôn ngữ, bao gồm tiếng Anh, tiếng Trung, tiếng Nhật, v.v. Tuy nhiên, giao diện và prompt hiện tại được tối ưu cho tiếng Việt.

**Q: Dữ liệu có an toàn không?**  
A: File PDF và dữ liệu được lưu trên Supabase (hạ tầng AWS), có mã hóa khi truyền tải (TLS) và khi lưu trữ (encryption at rest). API có xác thực JWT, chỉ Admin mới có quyền upload/xóa sách.

---

## 8. Troubleshooting — Lỗi 502/504 khi Upload

### Triệu chứng
- Upload file PDF lớn → trang poll status liên tục trả 502 Bad Gateway
- Các tab quản trị khác cũng bị treo/lỗi trong khi upload đang chạy
- Console trình duyệt hiển thị hàng loạt `GET /api/v1/books/{id} 502`

### Nguyên nhân gốc
Worker ingestion chạy **chung event loop** với API (cùng process). Khi worker xử lý OCR/embedding (CPU-bound, sync I/O), nó block toàn bộ event loop → API không thể phục vụ bất kỳ request nào.

### Giải pháp (đã áp dụng — Tháng 4/2026)

1. **Tắt worker trong API process:**
   ```env
   # api/.env
   INGESTION_WORKER_ENABLED=false
   ```

2. **Chạy worker riêng qua PM2:**
   ```bash
   pm2 start "venv/bin/python worker.py" --name ebook-worker --cwd /path/to/api
   ```

3. **Kiến trúc mới:**
   ```
   ebook-api    → Chỉ phục vụ HTTP (upload trả về ngay, push job vào Redis queue)
   ebook-worker → Process riêng, poll Redis, xử lý OCR/embed/chunk
   ```

4. **Kết quả:** Upload trả về trong ~5 giây, polling status không bị 502, API luôn responsive.

---

## 9. Cải tiến RAG Retrieval (Tháng 5/2026)

### Vấn đề gốc

| Vấn đề | Nguyên nhân | Ảnh hưởng |
|---|---|---|
| Tóm tắt phần thiếu nội dung | Hybrid search chỉ lấy 5-15 chunks ngẫu nhiên | Bỏ sót ~96% nội dung của phần (VD: Phần 1 có 386 chunks) |
| Mục lục thiếu | Supabase giới hạn 1000 rows/query, trang MỤC LỤC ở cuối sách | Không lấy được chunks trang 1000+ |
| Tiêu đề phần sai | LLM suy đoán từ chunk bị lỗi OCR nặng | Tiêu đề bị hallucinate |
| Ghi chú OCR hiện ra | Prompt yêu cầu ghi `[nguyên văn]` khi không chắc chắn | Bạn đọc thấy nội dung kỹ thuật không liên quan |
| Streaming đứng | Nginx buffer SSE response | Chat bị ngắt giữa chừng |

### Giải pháp đã áp dụng

#### 9.1 Section-Aware Retrieval (`retrieval.py`)

Khi người dùng hỏi "tóm tắt phần 1" hoặc "tóm tắt chương III":

```
Detect section reference → Find page range → Distributed sampling
   "phần 1" → 1         pages 12-151       25 chunks trải đều
```

- `detect_section_reference()`: Nhận diện "phần 1", "phần III", "chapter 2" trong query
- `find_section_page_range()`: Scan chunks theo batch (để bypass giới hạn 1000 rows) tìm header "Phần I", "Phần II"...
- `retrieve_chunks_for_section_summary()`: Chia đều toàn bộ chunks của phần thành 25 lát, lấy chunk dài nhất mỗi lát

#### 9.2 TOC Detection từ trang in sẵn (`retrieval.py`)

Khi người dùng hỏi mục lục:

- Query 20 trang cuối sách (bypass giới hạn 1000 rows)
- Tìm chunks chứa keyword "MỤC LỤC"
- Lấy toàn bộ chunks trong phạm vi trang mục lục
- Fallback: kiểm tra 20 trang đầu nếu không tìm thấy ở cuối

#### 9.3 Prompt Engineering cải tiến (`rag_engine.py`)

- Thầm lặng sửa lỗi OCR — KHÔNG BAO GIờ hiện ghi chú `[nguyên văn]`, `(đã sửa)`, `(tiêu đề được phục hồi từ...)`
- Đoạn lỗi OCR nặng: Bỏ qua và dùng thông tin từ chunks khác
- Tiêu đề chương/phần: Đối chiếu nhiều chunks để tìm tiêu đề chính xác
- Tăng `max_tokens`: Tóm tắt chương/sách → 8000 tokens (thường: 4000)

#### 9.4 Nginx SSE Streaming (`nginx-ebook.conf`)

```nginx
location /api/ {
    proxy_buffering off;          # Tắt buffer cho SSE
    proxy_cache off;
    chunked_transfer_encoding on;
    proxy_http_version 1.1;
    proxy_set_header Connection '';
}
```

#### 9.5 Keyword Supplement Search (`retrieval.py`)

Hybrid search (vector + FTS) đôi khi miss chunks chứa **chính xác** cụm từ trong câu hỏi, vì embedding similarity ưu tiên chunks ở chỗ khác trong sách.

**Giải pháp:** Bước bổ sung sau hybrid search:
1. Trích cụm từ quan trọng từ câu hỏi (≥8 ký tự, bỏ stopwords)
2. ILIKE search trong `book_chunks` tìm chunks chứa cụm đó
3. De-duplicate với hybrid search results
4. Ghép vào đầu kết quả (tối đa 5 chunks bổ sung)

**Ví dụ:** Query "Những nội dung cơ bản của Hiến pháp năm 2013?" → hybrid search trả về trang 45, 397 (sai) → keyword supplement tìm được chunk trang 15 chứa chính xác tiêu đề mục đó.

#### 9.6 Intro Page Context (`rag.py`)

Trang Lời giới thiệu / Lời NXB (trang 1-10) chứa thông tin tiểu sử, bối cảnh quan trọng nhưng hybrid search thường bỏ qua do chunk ngắn, embedding similarity thấp.

**Giải pháp:** Với mọi câu hỏi Q&A, tự động đính kèm chunks từ 10 trang đầu sách như context bổ sung (de-duplicate bằng chunk ID).

#### 9.7 Book Metadata Detection (`rag_engine.py`, `rag.py`)

Phát hiện câu hỏi về thông tin xuất bản/biên tập (biên tập viên, nhà in, tác giả, ISBN...) qua keyword matching → lấy trực tiếp chunks từ 10 trang đầu thay vì hybrid search.

#### 9.8 Prompt Refinements (`rag_engine.py`)

- Cấm mở đầu bằng "Dựa trên các đoạn trích được cung cấp" — trả lời trực tiếp vào nội dung
- TOC format: heading markdown `###` cho tên phần, dấu gạch `-` cho mỗi mục, số trang cuối dòng
- Tóm tắt chương: dùng MỤC LỤC làm khung cấu trúc, mỗi bài viết ≥1-2 câu tóm tắt
- Cache key bao gồm `top_k` để tránh kết quả stale
