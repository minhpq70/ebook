# Ebook Platform — Private RAG (POC)

Nền tảng xuất bản điện tử với Private RAG: AI chỉ nhận query + chunks, **không gửi toàn bộ sách**.

## Stack
- **Frontend**: Next.js 14 (App Router + TypeScript + Tailwind)
- **Backend**: FastAPI (Python)
- **Vector DB**: Supabase (PostgreSQL + pgvector)
- **AI**: OpenAI GPT-4o-mini + text-embedding-3-small

## Cấu trúc

```
ebook-platform/
├── api/              # FastAPI backend
├── web/              # Next.js frontend
└── supabase/
    └── migrations/
        └── 001_init.sql   # ← Chạy cái này trong Supabase SQL Editor
```

## Setup

### 1. Supabase
1. Tạo project trên [supabase.com](https://supabase.com)
2. Vào **SQL Editor**, copy và chạy nội dung file `supabase/migrations/001_init.sql`
3. Vào **Storage** → tạo bucket tên là `books` (Public hoặc Private đều được)
4. Lấy **Project URL** và **Service Role Key** từ Settings → API

### 2. Backend (FastAPI)

```bash
cd api

# Tạo virtual environment
python -m venv venv
source venv/bin/activate   # macOS/Linux

# Cài dependencies
pip install -r requirements.txt

# Cấu hình .env
cp .env.example .env
# Điền OPENAI_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY vào .env

# Chạy server
uvicorn main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### 3. Frontend (Next.js)

```bash
cd web
# .env.local đã có sẵn (NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1)
npm run dev
```

App: http://localhost:3000

## Sử dụng

1. Truy cập http://localhost:3000
2. Click **Upload sách** → upload file PDF
3. Đợi xử lý (chunking + embedding — thường 1-3 phút tùy sách)
4. Sau khi status = "Sẵn sàng" → Click **Đọc ngay**
5. Click **Hỏi AI** → chọn tác vụ → đặt câu hỏi

### Tác vụ AI
| Tác vụ | Mô tả |
|--------|-------|
| 💬 Hỏi đáp | Hỏi bất kỳ câu hỏi về nội dung sách |
| 🔍 Giải thích | Giải thích đoạn văn khó hiểu |
| 📝 Tóm tắt chương | Tóm tắt một chương cụ thể |
| 📚 Tóm tắt sách | Tổng quan nội dung sách |
| ✨ Gợi ý liên quan | Gợi ý chủ đề và nội dung liên quan |

## RAG Flow (Privacy)

```
Bạn đọc hỏi
    ↓
Embed query (OpenAI)
    ↓
Hybrid search trong pgvector (vector + full-text)
    ↓
Lấy top-5 chunks liên quan
    ↓
Gửi [query + chunks] → GPT-4o-mini   ← ⚠ KHÔNG gửi toàn bộ sách
    ↓
Trả lời + trích nguồn
```

## API Endpoints

| Method | Path | Mô tả |
|--------|------|-------|
| POST | `/api/v1/books/upload` | Upload PDF + ingest |
| GET | `/api/v1/books` | Danh sách sách |
| GET | `/api/v1/books/{id}` | Chi tiết sách |
| DELETE | `/api/v1/books/{id}` | Xóa sách |
| POST | `/api/v1/rag/query` | RAG query |

## Migration sang PostgreSQL self-hosted

Khi ready migrate khỏi Supabase:
1. Cài PostgreSQL + pgvector extension
2. Thay `SUPABASE_URL` và `SUPABASE_SERVICE_KEY` bằng connection string PostgreSQL
3. Thay `supabase_client.py` bằng `asyncpg` hoặc `psycopg2`
4. Functions `hybrid_search` trong SQL giữ nguyên (tương thích)


