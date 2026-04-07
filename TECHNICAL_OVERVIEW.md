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
| Kích thước file PDF tối đa | ~100 MB | Nén PDF trước khi upload |
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
│                   FRONTEND (Vercel)                               │
│              Next.js / React — Giao diện người dùng               │
└──────────────────────┬───────────────────────────────────────────┘
                       │ HTTPS API
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                   BACKEND (Render.com)                            │
│              FastAPI / Python — Xử lý logic nghiệp vụ            │
│   ┌─────────────┐ ┌───────────────┐ ┌─────────────────────────┐  │
│   │ Upload &    │ │ Tìm kiếm     │ │  Hỏi đáp AI            │  │
│   │ Xử lý PDF  │ │ Vector       │ │  (RAG Engine)           │  │
│   └─────────────┘ └───────────────┘ └─────────────────────────┘  │
└──────────┬──────────────┬───────────────────┬────────────────────┘
           │              │                   │
           ▼              ▼                   ▼
┌────────────────┐ ┌──────────────┐  ┌──────────────────┐
│   Supabase     │ │   Supabase   │  │   OpenAI API     │
│   Storage      │ │   Database   │  │   (GPT-4o-mini)  │
│ (Lưu PDF/Ảnh)  │ │ (pgvector)   │  │  Embedding + Chat│
└────────────────┘ └──────────────┘  └──────────────────┘
```

### Công nghệ sử dụng

| Thành phần | Công nghệ | Vai trò |
|-----------|-----------|---------|
| Giao diện | Next.js, React, TypeScript | Hiển thị danh sách sách, giao diện chat AI |
| Backend | FastAPI, Python | Xử lý API, pipeline upload, RAG engine |
| Database | PostgreSQL + pgvector (Supabase) | Lưu trữ metadata, chunks, vector embedding |
| Lưu trữ file | Supabase Storage | Lưu file PDF gốc và ảnh bìa |
| AI Models | OpenAI GPT-4o-mini + text-embedding-3-small | Hỏi đáp thông minh + tạo vector |
| Hosting Frontend | Vercel | Deploy tự động từ GitHub |
| Hosting Backend | Render.com | Deploy tự động từ GitHub |

---

## 7. Câu hỏi Thường gặp

**Q: Tại sao upload sách mất vài phút?**  
A: Phần lớn thời gian dành cho việc gọi OpenAI API để tạo vector embedding cho từng đoạn văn bản. Đây là bước không thể bỏ qua vì vector là nền tảng để AI tìm kiếm và trả lời chính xác. Quá trình này chạy tự động ở chế độ nền, người dùng không cần chờ đợi.

**Q: Sách càng nhiều thì hệ thống có chậm đi không?**  
A: Không. Mỗi câu hỏi chỉ tìm kiếm trong phạm vi 1 cuốn sách, nên dù có hàng trăm cuốn sách khác trong hệ thống, tốc độ trả lời vẫn giữ nguyên 2-5 giây.

**Q: Hệ thống có thể xử lý sách bằng tiếng nước ngoài không?**  
A: Có. OpenAI hỗ trợ đa ngôn ngữ, bao gồm tiếng Anh, tiếng Trung, tiếng Nhật, v.v. Tuy nhiên, giao diện và prompt hiện tại được tối ưu cho tiếng Việt.

**Q: Dữ liệu có an toàn không?**  
A: File PDF và dữ liệu được lưu trên Supabase (hạ tầng AWS), có mã hóa khi truyền tải (TLS) và khi lưu trữ (encryption at rest). API có xác thực JWT, chỉ Admin mới có quyền upload/xóa sách.
