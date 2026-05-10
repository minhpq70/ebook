# Hướng Dẫn Setup Server Hoàn Chỉnh (Self-Hosted Supabase)

Tài liệu chi tiết Step-by-Step để chuyển Ebook Platform từ Vercel/Render sang máy chủ VPS vật lý độc lập (Ubuntu 22.04 LTS / 24.04 LTS).

**Không cần code lại bất cứ dòng nào** — chỉ cần cấu hình lại biến môi trường.

---

## BƯỚC 0: Clone Mã Nguồn

```bash
cd /home/tinhvan/apps
git clone https://github.com/minhpq70/ebook.git ebook-platform
cd ebook-platform
```

---

## BƯỚC 1: Chạy Script Cài Đặt Hệ Thống

File `setup_server.sh` sẽ tự động cài: Docker, Python 3.12, Node.js 20, PM2, Nginx, Redis, và các thư viện hệ thống cho PaddleOCR (libgl1, libglib2.0). Tesseract OCR được giữ lại làm fallback.

```bash
chmod +x setup_server.sh
./setup_server.sh
```

> [!NOTE]
> Sau khi chạy xong, **đăng xuất và đăng nhập lại** để quyền Docker có hiệu lực:
> ```bash
> exit
> # SSH lại vào server
> ```

---

## BƯỚC 2: Khởi Động Supabase Self-Hosted (Docker)

```bash
cd /opt
sudo git clone --depth 1 https://github.com/supabase/supabase
cd supabase/docker

sudo cp .env.example .env
sudo docker compose pull
sudo docker compose up -d
```

> [!NOTE]
> Supabase (Postgres, Storage, Kong) sẽ chiếm cổng `8000`. Backend FastAPI sẽ chạy ở cổng `8080`.
>
> - **SUPABASE_URL**: `http://127.0.0.1:8000`
> - **Keys**: Mở `/opt/supabase/docker/.env` để lấy `ANON_KEY` và `SERVICE_ROLE_KEY`
>
> Truy cập Studio: `http://<IP_MAY_CHU>:8000` → tạo Bucket `books` + `covers` ở Storage, chạy SQL schema từ `supabase/migrations/`.

---

## BƯỚC 3: Triển Khai Backend (FastAPI)

```bash
cd /home/tinhvan/apps/ebook-platform/api

# Tạo môi trường ảo Python 3.12
python3.12 -m venv venv
source venv/bin/activate

# Cài dependencies (bao gồm PaddleOCR + VietOCR)
pip install --no-cache-dir -r requirements.txt
```

> [!IMPORTANT]
> `requirements.txt` đã bao gồm `paddlepaddle`, `paddleocr`, `torch`, `vietocr`.
> PaddleOCR + VietOCR được cài qua pip, **không cần cài riêng binary** như Tesseract.
> Thời gian cài lần đầu: ~10-15 phút (PyTorch ~200MB, PaddlePaddle ~200MB).

### Cấu hình .env

```bash
cat <<EOF > .env
# ── OpenAI (Embedding) ──
OPENAI_API_KEY=sk-xxxx...
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_MAX_TOKENS=2000

# ── Provider: Google AI Studio (Chat/RAG mặc định) ──
GOOGLE_AI_STUDIO_API_KEY=AIzaSy...
GOOGLE_AI_STUDIO_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/

# ── Provider: Anthropic (tùy chọn) ──
ANTHROPIC_API_KEY=
ANTHROPIC_BASE_URL=

# ── Legacy aliases (backward compat) ──
OPENAI_CHAT_MODEL=gemma-4-31b-it
OPENAI_CHAT_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
OPENAI_CHAT_API_KEY=AIzaSy...

# ── Supabase (thay bằng key từ bước 2) ──
SUPABASE_URL=http://127.0.0.1:8000
SUPABASE_SERVICE_KEY=<SERVICE_ROLE_KEY_TỪ_BƯỚC_2>
SUPABASE_ANON_KEY=<ANON_KEY_TỪ_BƯỚC_2>

# ── RAG Config ──
RAG_CHUNK_SIZE=500
RAG_CHUNK_OVERLAP=50
RAG_TOP_K=5
RAG_VECTOR_WEIGHT=0.7
RAG_FTS_WEIGHT=0.3

# ── Auth ──
JWT_SECRET=<CHUỖI_NGẪU_NHIÊN_ÍT_NHẤT_32_KÝ_TỰ>

# ── App ──
APP_ENV=production
APP_CORS_ORIGINS=https://your-domain.com

# ── Google Sheets Logging (tùy chọn) ──
GOOGLE_SA_JSON=
SHEET_ID=
SHEET_TAB=Logs

# ── Redis & Worker ──
REDIS_ENABLED=true
REDIS_URL=redis://127.0.0.1:6379/0
INGESTION_WORKER_ENABLED=true
EOF
```

### Khởi chạy Backend với PM2

```bash
pm2 start "venv/bin/uvicorn main:app --host 127.0.0.1 --port 8080" --name "ebook-api"
```

---

## BƯỚC 4: Triển Khai Frontend (Next.js)

```bash
cd /home/tinhvan/apps/ebook-platform/web

cat <<EOF > .env.local
NEXT_PUBLIC_API_URL=http://localhost:8080/api/v1
EOF

npm install
npm run build

pm2 start npm --name "ebook-web" -- start -- -p 3000
```

*(Backend: 8080, Frontend: 3000, Supabase: 8000)*

---

## BƯỚC 5: Cấu Hình Nginx + Domain

```bash
sudo nano /etc/nginx/sites-available/ebook
```

Paste nội dung:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    client_max_body_size 200M;   # Cho phép upload PDF lớn

    # API Backend
    location /api/ {
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 600s;   # OCR/Ingestion có thể chạy lâu
        proxy_pass http://127.0.0.1:8080/api/;
    }

    # Frontend
    location / {
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Host $http_host;
        proxy_pass http://127.0.0.1:3000;
    }
}
```

Kích hoạt:

```bash
sudo ln -s /etc/nginx/sites-available/ebook /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# PM2 auto-restart khi reboot
pm2 save
pm2 startup
```

> [!TIP]
> **Cài SSL miễn phí:**
> ```bash
> sudo apt install certbot python3-certbot-nginx -y
> sudo certbot --nginx -d your-domain.com
> ```

---

## BƯỚC 6: Xác Nhận OCR Engine

Sau khi deploy, kiểm tra OCR đã hoạt động:

```bash
cd /home/tinhvan/apps/ebook-platform/api
source venv/bin/activate
python3 -c "
from services.ocr_engine import is_ocr_available
status = is_ocr_available()
print('OCR Status:')
for engine, ok in status.items():
    print(f'  {engine}: {\"✅\" if ok else \"❌\"} ')
"
```

Kết quả mong đợi:
```
OCR Status:
  paddleocr: ✅
  vietocr: ✅
  tesseract: ✅
```

> [!NOTE]
> **Pipeline OCR 2 tầng:**
> - **Tầng 1**: PaddleOCR (detection + recognition) — nhanh, ~85-90% chính xác
> - **Tầng 2**: VietOCR fallback cho dòng có confidence < 0.85 — ~92-97% chính xác cho tiếng Việt
> - **Tầng 3**: Tesseract fallback cuối cùng nếu PaddleOCR không khả dụng
> - PDF text-based: **bỏ qua OCR hoàn toàn** → không tốn resource

---

## BƯỚC 7: Di Dời Dữ Liệu Từ Supabase Cloud (Tùy Chọn)

Nếu có dữ liệu cũ trên Supabase Cloud muốn chuyển về:

### Database (Bảng + Vectors)

```bash
# Export từ Cloud
pg_dump "postgres://[user]:[password]@[host]:6543/postgres" -C -f supabase_backup.sql

# Import vào Local Docker
psql -h 127.0.0.1 -p 5432 -U postgres -d postgres -f supabase_backup.sql
```

### File Storage (PDF + Ảnh bìa)

1. Tải từ Dashboard Storage của Supabase Cloud (hoặc dùng `rclone`)
2. Truy cập Studio Local: `http://<IP>:8000`
3. Tạo Bucket `books` + `covers` → upload file tương ứng

---

## Tóm Tắt Kiến Trúc

```
Internet → Nginx (:80/443)
              ├─ /api/*  → FastAPI (:8080)
              │              ├─ OCR: PaddleOCR + VietOCR (pip)
              │              ├─ Embedding: OpenAI API
              │              ├─ Chat/RAG: Google AI Studio (Gemma 4)
              │              └─ Cache: Redis (:6379)
              │
              └─ /*      → Next.js (:3000)
                              └─ Static frontend

Supabase Docker (:8000)
  ├─ PostgreSQL + pgvector (vector search)
  ├─ Storage (PDF + Cover images)
  └─ Kong API Gateway
```
