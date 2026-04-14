# Hướng Dẫn Setup Server Hoàn Chỉnh (Self-Hosted Supabase)

Tài liệu này cung cấp cho bạn một lộ trình chi tiết Step-by-Step để chuyển Ebook Platform từ Vercel/Render sang một máy chủ VPS vật lý độc lập (Ubuntu 22.04 LTS / 24.04 LTS).

Theo phương án này, **Không cần phải code lại bất cứ dòng nào**, chúng ta sẽ tự xây dựng một "Supabase thu nhỏ" ngay trên server bằng Docker.

---

## BƯỚC 0: Clone Mã Nguồn Từ GitHub Xuống Máy Chủ
Vì máy chủ bạn vừa mua hoàn toàn trống trơn, việc đầu tiên là kéo toàn bộ mã nguồn (bao gồm cả file `setup_server.sh` mà tôi vừa viết cho bạn) về Server.

```bash
# Di chuyển vào thư mục chứa code thường dùng của Linux
cd /var/www

# Kéo dự án từ GitHub của bạn về (thay thế đường link repo bên dưới)
git clone https://github.com/Taikhoancuaban/ebook-platform.git

# Bay vào thư mục chứa code
cd ebook-platform
```

---

## BƯỚC 1: Chạy Script Cài Đặt Khung Cương Hệ Thống (Mới)
Lúc này bạn đã đứng trong thư mục `ebook-platform`, file `setup_server.sh` đã có sẵn. File này sẽ tự động cài các phần mềm thiết yếu: *Docker, PostgreSQL client, Python 3.12, Node.js 20, PM2, Nginx, và đặc biệt là Tesseract OCR (Tiếng Việt) để AI nhận diện ảnh bìa.*

**Thao tác gõ trên Terminal máy chủ:**
```bash
# Cấp quyền thực thi và chạy
chmod +x setup_server.sh
./setup_server.sh
```

---

## BƯỚC 2: Khởi Động Động Cơ Supabase (Docker)
Máy chủ hiện tại đã có Docker. Bây giờ bạn cần mồi máy một bản Supabase Open-Source.

```bash
# Clone bản gốc Supabase Self-Hosted từ kho chính chủ
cd /opt
sudo git clone --depth 1 https://github.com/supabase/supabase
cd supabase/docker

# Copy thiết lập môi trường mặc định
sudo cp .env.example .env

# Chạy hệ thống Supabase Database & Storage lên
sudo docker compose pull
sudo docker compose up -d
```
> [!NOTE] 
> Chạy xong lệnh trên, hệ sinh thái Supabase (Postgres, Storage, Kong API Gateway) sẽ tự động kích hoạt. Nó thường chiếm dụng cổng `8000` cho bộ định tuyến API (Kong). Do đó, Backend FastAPI của bạn sắp tới sẽ phải né cổng 8000 ra, ví dụ đổi sang cổng `8080`.
>  
> - **SUPABASE_URL** của bạn bây giờ sẽ là: `http://127.0.0.1:8000`
> - **SUPABASE_ANON_KEY** và **SERVICE_KEY**: Mở file `/opt/supabase/docker/.env` để lấy (Mục `ANON_KEY` và `SERVICE_ROLE_KEY`).

Lưu ý: Mở Studio quản lý Database bằng cách vào trình duyệt `http://<IP_MAY_CHU>:8000` để thêm bảng, thêm cột thông qua UI như y hệt trên Supabas.com. Cần tạo 1 Bucket tên là `books` và 1 Bucket là `covers` ở phần Storage, và tạo bảng `books` với `book_chunks` dựa trên SQL script dự án.

---

## BƯỚC 3: Triển Khai Backend (FastAPI) Qua PM2
Backend Python yêu cầu môi trường độc lập khép kín. Không dùng Render, chúng ta nhờ `PM2` treo ngầm backend thay.

```bash
# Điều hướng vào thư mục backend
cd /var/www/ebook-platform/api

# Cài đặt môi trường ảo Python 3.12
python3.12 -m venv venv
source venv/bin/activate
pip install --no-cache-dir -r requirements.txt

# Sắp xếp file .env (Điền key mới nhất của Supabase Local và OpenAI vào)
cat <<EOF > .env
OPENAI_API_KEY=sk-xxxx...
SUPABASE_URL=http://127.0.0.1:8000
SUPABASE_SERVICE_KEY=<SERVICE_ROLE_KEY_TỪ_BƯỚC_2>
JWT_SECRET=Hãy_gõ_1_chuỗi_rất_dài_hơn_32_ký_tự_vào_đây
EOF

# Chạy ngầm vô thời hạn bằng lệnh PM2 System, treo ở cổng 8080 
pm2 start "venv/bin/uvicorn main:app --host 127.0.0.1 --port 8080" --name "ebook-api"
```

---

## BƯỚC 4: Triển Khai Frontend (Next.js)
Tương tự Frontend sẽ được dựng mã bằng Node.js và treo bằng PM2.

```bash
# Mở thư mục frontend
cd /var/www/ebook-platform/web

# Tạo trỏ url tới Backend (Cổng 8080 vừa cấu hình)
cat <<EOF > .env.local
NEXT_PUBLIC_API_URL=http://localhost:8080/api/v1
EOF

# Build Web chuẩn hóa
npm install
npm run build

# PM2 treo Web lên cổng máy khách là 3000
pm2 start npm --name "ebook-web" -- start -- -p 3000
```
*(Đến lúc này: Backend đang chạy ở 8080, Frontend đang chạy ở 3000, Supabase ở 8000)*

---

## BƯỚC 5: Mở "Siêu Cửa Thuế" Nginx Và Cắm Domain Ra Ngoài Internet
Hiện tại, server vật lý này phải điều tiết đường đi giữa 2 mảnh ghép (Port 3000 và 8080) thông qua tên miền `vidu-ebook.com`.

```bash
sudo nano /etc/nginx/sites-available/ebook
```
Paste nội dung dưới đây vào:

```nginx
server {
    listen 80;
    server_name vidu-ebook.com;

    # Nửa 1: Request nào gọi vào API thì Nginx lái thẳng vào Backend Python (Port 8080)
    location /api/ {
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Host $http_host;
        proxy_pass http://127.0.0.1:8080/api/;
    }

    # Nửa 2: Tất cả những request còn lại là truy cập tải Giao diện Web (Port 3000)
    location / {
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Host $http_host;
        proxy_pass http://127.0.0.1:3000;
    }
}
```

**Bật công tắc luồng mạng Nginx:**
```bash
sudo ln -s /etc/nginx/sites-available/ebook /etc/nginx/sites-enabled/
sudo nginx -t     # Kiểm tra lỗi cú pháp Nginx
sudo systemctl reload nginx   # Áp dụng
```

**Hoàn tất và lưu trữ vòng đời:**
```bash
# Lệnh này giúp pm2 ghi nhớ lại frontend & backend để nếu sập nguồn server
# bật lên tụi nó vẫn tự động đứng dậy chạy tiếp.
pm2 save
pm2 startup
```

> [!SUCCESS]
> **THÀNH CÔNG RỰC RỠ**
> Giờ đây bạn chỉ việc vào website `vidu-ebook.com`. Giao diện Frontend từ Nginx sẽ kết nối qua Backend. Backend sẽ xử lý OCR qua Tesseract ngay trên Ubuntu, bế file đẩy vào cái kho chứa Docker Local 100% On-Premise của chính bạn. Tất cả dữ liệu không ai có thể xâm phạm kể cả các dịch vụ thứ 3.

---

## BƯỚC 6: Di Dời Dữ Liệu Thực Tế Từ Supabase Cloud Về (Tuỳ Chọn)
Nếu bạn có dữ liệu cũ đang nằm sẵn trên trang web Supabase.com và muốn vác toàn bộ cấu trúc CSDL lẫn File sách đang chứa ở trên đó đem về máy chủ Local mới tinh này mà **không bị sai lệch bất cứ thông tin/mã hóa Vector nào cả**, quy trình rất đơn giản:

### Di chuyển Database (Bảng dữ liệu & Vector RAG)
Vì lõi gốc của cả Cloud và Local đều là PostgreSQL 100%, ta sẽ dùng công cụ Backup kinh điển `pg_dump`:
1. **Lấy URI:** Trên Website của Supabase > Database > Settings > Lấy chuỗi *URI Connection*.
2. **Rút toàn bộ dữ liệu (Export):** Từ Terminal máy chủ Ubuntu của bạn, gõ:
   ```bash
   pg_dump "postgres://[user]:[password]@[host]:6543/postgres" -C -f supabase_backup.sql
   ```
3. **Bơm dữ liệu (Import):** Tiếp tục tiêm cái file Backup cục mịch đó vào thẳng container Supabase Docker Local hiện tại qua port 5432:
   ```bash
   psql -h 127.0.0.1 -p 5432 -U postgres -d postgres -f supabase_backup.sql
   ```

### Di chuyển File Dung Lượng Lớn (PDF sách / Ảnh bìa)
Bucket Storage tuân thủ giao thức AWS S3 nên đường dẫn File trên Cloud và Local lưu hệt nhau.
1. Bạn có thể dùng tiện ích `Rclone` của Linux để Tải hàng loạt, hoặc thủ công vào Dashboard Storage của tài khoản cũ tải Zip xuống theo từng Folder.
2. Truy cập vào giao diện web Studio quản lý của Supabase máy chủ Local mới (Ví dụ vào: `http://[IP_MAY_CHU]:8000`).
3. Tạo 2 Bucket trống là `books` và `covers` (nhớ chỉnh public giống hệt ban đầu). Sau đó kéo thả/upload file ngược lại tương ứng theo thư mục. Các File này sẽ tự động liên kết nối lại khớp 100% với cái Database mà Bước trên bạn chèn vào mạng lưới. Rủi ro hỏng nền là 0%.
