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
# Điền các biến bắt buộc vào .env:
# - OPENAI_API_KEY
# - SUPABASE_URL, SUPABASE_SERVICE_KEY
# - JWT_SECRET (tạo bằng: python3 -c "import secrets; print(secrets.token_urlsafe(48))")

# (TÙY CHỌN) Thiết lập Google Sheets logging:
# 1. Tạo service account key JSON từ Google Cloud Console
# 2. Chạy: python convert_sa_json.py (sẽ generate base64 encoded string)
# 3. Set GOOGLE_SA_JSON=base64_string trong .env
# 4. Tạo Google Sheet và lấy SHEET_ID từ URL

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
## Deployment

### Render (Khuyên dùng)

1. **Chuẩn bị Google Service Account:**
   ```bash
   # 1. Tạo service account trên Google Cloud Console
   # 2. Download JSON key file
   # 3. Convert thành base64:
   cd api
   python convert_sa_json.py
   # Copy output base64 string
   ```

2. **Deploy trên Render:**
   - Tạo **Web Service** mới
   - Connect GitHub repository
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`

3. **Environment Variables trên Render:**
   ```
   # Required
   OPENAI_API_KEY=sk-proj-...
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_SERVICE_KEY=eyJhbGciOi...
   SUPABASE_ANON_KEY=eyJhbGciOi...
   JWT_SECRET=your-secure-random-jwt-secret

   # Optional - Google Sheets logging
   GOOGLE_SA_JSON=base64_string_from_convert_script
   SHEET_ID=your_google_sheet_id
   SHEET_TAB=Logs

   # App Config
   APP_ENV=production
   APP_CORS_ORIGINS=https://your-frontend-domain.com
   ```

4. **Deploy Frontend:**
   - Tạo **Static Site** trên Render
   - Connect GitHub repo (thư mục `web/`)
   - **Build Command:** `npm run build`
   - **Publish Directory:** `out`
   - Set `NEXT_PUBLIC_API_URL` = URL của backend API

### Test Credentials

```bash
cd api
python test_credentials.py
```
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
=======
# ebook
Khai thác ebook nhờ AI
>>>>>>> db00c2d1c230ad3b4b118cb3d2a5d66ae31e720c
