# Hướng dẫn thay đổi Model AI

Hệ thống sử dụng **2 client OpenAI riêng biệt**, cho phép đổi model một cách linh hoạt mà không ảnh hưởng lẫn nhau.

---

## Kiến trúc 2 Client

```
┌──────────────────────────────────────────────────────┐
│  get_openai()          → EMBEDDING                   │
│  File: api/core/openai_client.py                     │
│  Dùng: OPENAI_API_KEY (luôn gọi OpenAI)             │
│  Model: OPENAI_EMBEDDING_MODEL                      │
├──────────────────────────────────────────────────────┤
│  get_chat_openai()     → CHAT / RAG                  │
│  File: api/core/openai_client.py                     │
│  Dùng: OPENAI_CHAT_API_KEY → hoặc OPENAI_API_KEY    │
│  Model: OPENAI_CHAT_MODEL                            │
│  Base URL: OPENAI_CHAT_BASE_URL (tuỳ chọn)          │
└──────────────────────────────────────────────────────┘
```

### RAG dùng cả 2 model

Hệ thống có **2 model, không phải 3**. Chat và RAG dùng chung một model — chúng chỉ khác nhau ở prompt (RAG có thêm ngữ cảnh từ sách).

**RAG = quá trình 2 bước:**

```
Người dùng hỏi: "Tóm tắt chương 3"
         │
         ▼
┌─ Bước 1: RETRIEVE (Tìm kiếm) ──────────────────────┐
│  Dùng: Embedding Model (text-embedding-3-small)      │
│  Hành động: Chuyển câu hỏi thành vector              │
│             → Tìm các đoạn sách liên quan trong DB   │
│  Kết quả: Top 5-8 đoạn sách phù hợp nhất            │
└──────────────────────────────────────────────────────┘
         │
         ▼
┌─ Bước 2: GENERATE (Sinh trả lời) ───────────────────┐
│  Dùng: Chat Model (gpt-4o-mini hoặc Gemma4)         │
│  Hành động: Gửi câu hỏi + các đoạn sách cho LLM    │
│             → LLM viết câu trả lời dựa trên ngữ cảnh│
│  Kết quả: Câu trả lời hoàn chỉnh cho người dùng     │
└──────────────────────────────────────────────────────┘
```

> **Tóm lại**: Đổi **Chat model** sẽ thay đổi cách hệ thống **viết câu trả lời** (cả RAG lẫn tóm tắt, giải thích). Đổi **Embedding model** sẽ thay đổi cách hệ thống **tìm kiếm** đoạn sách liên quan.

---

## 1. Embedding Client (`get_openai()`)

Dùng để tạo vector embedding cho các đoạn sách (chunking) và cho câu hỏi của người dùng khi tìm kiếm.

### Biến môi trường

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `OPENAI_API_KEY` | *(bắt buộc)* | API key của OpenAI |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | Tên model embedding |

### Các model embedding phổ biến

| Model | Chiều vector | Chi phí | Ghi chú |
|-------|-------------|---------|---------|
| `text-embedding-3-small` | 1536 | Rẻ nhất | ✅ Đang dùng, phù hợp cho tiếng Việt |
| `text-embedding-3-large` | 3072 | Đắt hơn 6x | Chính xác hơn, cần thêm dung lượng DB |
| `text-embedding-ada-002` | 1536 | Trung bình | Model cũ, không khuyến khích |

> **⚠️ CẢNH BÁO**: Nếu đổi model embedding, bạn **PHẢI re-ingest toàn bộ sách** vì chiều vector thay đổi sẽ không tương thích với dữ liệu cũ trong Supabase.

### Cách đổi

Trên **Render Dashboard → Environment Variables**, sửa:

```
OPENAI_EMBEDDING_MODEL=text-embedding-3-large
```

---

## 2. Chat/RAG Client (`get_chat_openai()`)

Dùng để sinh câu trả lời từ ngữ cảnh sách (hỏi đáp, tóm tắt, giải thích).

### Biến môi trường

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `OPENAI_CHAT_MODEL` | `gpt-4o-mini` | Tên model chat |
| `OPENAI_CHAT_BASE_URL` | *(trống = dùng OpenAI)* | URL API thay thế |
| `OPENAI_CHAT_API_KEY` | *(trống = dùng OPENAI_API_KEY)* | API key riêng cho chat |
| `OPENAI_MAX_TOKENS` | `4000` | Số token tối đa cho câu trả lời |

### Logic hoạt động

```
Nếu OPENAI_CHAT_BASE_URL có giá trị:
  → Gọi API tại base_url đó (Gemma, Qwen, Ollama...)
  → Dùng OPENAI_CHAT_API_KEY (nếu có), không thì dùng OPENAI_API_KEY

Nếu OPENAI_CHAT_BASE_URL trống/không đặt:
  → Gọi API OpenAI mặc định (https://api.openai.com/v1)
  → Dùng OPENAI_API_KEY
```

---

## 3. Các kịch bản thường gặp

### Kịch bản A: Dùng toàn bộ OpenAI (Mặc định)

Embedding và Chat đều dùng OpenAI. Đây là cấu hình đơn giản nhất.

```env
OPENAI_API_KEY=sk-proj-xxx
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_CHAT_MODEL=gpt-4o-mini
# KHÔNG đặt OPENAI_CHAT_BASE_URL và OPENAI_CHAT_API_KEY
```

### Kịch bản B: Embedding OpenAI + Chat dùng Gemma4 (Google AI Studio)

```env
OPENAI_API_KEY=sk-proj-xxx
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_CHAT_MODEL=gemma-3-27b-it
OPENAI_CHAT_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
OPENAI_CHAT_API_KEY=AIzaSy...  # Google AI Studio API key
```

### Kịch bản C: Embedding OpenAI + Chat dùng Ollama (Local)

```env
OPENAI_API_KEY=sk-proj-xxx
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_CHAT_MODEL=qwen2.5:14b
OPENAI_CHAT_BASE_URL=http://localhost:11434/v1
# OPENAI_CHAT_API_KEY không cần cho Ollama
```

### Kịch bản D: Nâng cấp model OpenAI Chat

```env
OPENAI_API_KEY=sk-proj-xxx
OPENAI_CHAT_MODEL=gpt-4o        # đổi từ gpt-4o-mini sang gpt-4o
# KHÔNG đặt OPENAI_CHAT_BASE_URL
```

### Kịch bản E: Dùng Model Local qua Proxy (vd: Qwen 3.5 với custom header `x-api-key`)

Nếu bạn có một máy chủ local (ví dụ IP `192.168.50.150:11435`) được bọc qua một proxy yêu cầu xác thực bằng header `x-api-key`, hệ thống mặc định của OpenAI SDK sẽ không hỗ trợ truyền header này trực tiếp (nó dùng `Authorization: Bearer`). 

**Bước 1: Chỉnh sửa `api/.env`:**
```env
OPENAI_CHAT_MODEL=qwen3.5:9b
# Đổi đuôi /api/chat thành /v1 để sử dụng OpenAI Compatibility layer của Ollama/Proxy
OPENAI_CHAT_BASE_URL=http://192.168.50.150:11435/v1
OPENAI_CHAT_API_KEY=Tinhvan@2026
```

**Bước 2: Cập nhật code để gửi đúng header (nếu hệ thống chưa hỗ trợ `x-api-key`):**
Cần sửa file `api/core/openai_client.py`, tìm đoạn tạo client (`_make_client`) và thêm logic truyền `default_headers={"x-api-key": api_key}` khi URL khớp với IP nội bộ hoặc thêm một provider cấu hình riêng.

---

### Kịch bản F: Chuyển lại về Gemini 2.5 Flash (Google AI Studio)

Khi bạn muốn tắt mô hình Local và quay lại **Gemini 2.5 Flash**, chỉ cần cập nhật lại `api/.env` về trạng thái chuẩn như sau (không cần hoàn tác code `x-api-key` nếu bạn đã viết logic an toàn chỉ kích hoạt cho URL local):

```env
OPENAI_CHAT_MODEL=gemini-2.5-flash
OPENAI_CHAT_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
OPENAI_CHAT_API_KEY=AIzaSy... (Điền lại API Key Google AI Studio của bạn)
```

---

## 4. Cách chuyển đổi trên Render

### Chuyển từ Gemma4 → OpenAI (quay về mặc định)

1. Vào [Render Dashboard](https://dashboard.render.com) → chọn dịch vụ API.
2. Vào **Settings → Environment Variables**.
3. **Xóa** (hoặc để trống) 2 biến:
   - `OPENAI_CHAT_BASE_URL`
   - `OPENAI_CHAT_API_KEY`
4. Đảm bảo `OPENAI_CHAT_MODEL=gpt-4o-mini`.
5. Nhấn **Save Changes** → Render tự redeploy.

### Chuyển từ OpenAI → Gemma4

1. Vào **Settings → Environment Variables**.
2. **Thêm/Sửa** 3 biến:
   - `OPENAI_CHAT_MODEL=gemma-3-27b-it`
   - `OPENAI_CHAT_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/`
   - `OPENAI_CHAT_API_KEY=AIzaSy...` (API key từ Google AI Studio)
3. Nhấn **Save Changes**.

---

## 5. Lưu ý quan trọng

| Hạng mục | Chi tiết |
|----------|---------|
| **Đổi Chat model** | An toàn, không ảnh hưởng dữ liệu. Chỉ cần sửa env vars rồi redeploy. |
| **Đổi Embedding model** | **NGUY HIỂM** — phải re-ingest toàn bộ sách vì vector không tương thích. |
| **File cấu hình** | `api/core/config.py` (định nghĩa biến), `api/core/openai_client.py` (tạo client) |
| **Nơi sử dụng Chat** | `api/services/rag_engine.py`, `api/services/query_expander.py`, `api/services/metadata_extractor.py` |
| **Nơi sử dụng Embedding** | `api/services/rag_engine.py` (tìm kiếm vector), `api/services/ingest.py` (tạo embedding khi upload) |
