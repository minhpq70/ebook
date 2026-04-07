# Quy trình Phát triển & Triển khai (CI/CD Workflow)

Tài liệu này dùng để tra cứu mỗi khi bạn code thêm tính năng mới cho dự án Ebook Platform và muốn đưa những thay đổi đó lên môi trường Production (thực tế). Toàn bộ hệ thống chạy trên 3 nền tảng chính:
1. **Supabase**: Quản lý Database & Lưu trữ PDF/Ảnh bìa.
2. **Render.com**: Hosting cho Backend (FastAPI - Python).
3. **Vercel**: Hosting cho Frontend (Next.js - React).

---

## 1. Môi trường Local (Khi đang lập trình)

Khi code và test tính năng tại máy cá nhân, bạn cần khởi chạy cả Frontend và Backend.

**Terminal 1 (Chạy Backend):**
```bash
cd api
source venv/bin/activate
uvicorn main:app --port 8001 --reload
```

**Terminal 2 (Chạy Frontend):**
```bash
cd web
npm run dev
```

> **Lưu ý Environment Variables (Biến môi trường) ở Local:** 
> - File `api/.env`: chứa kết nối Supabase và OpenAI SDK (`DATABASE_URL`, `SUPABASE_URL`, `OPENAI_API_KEY`).
> - File `web/.env.local`: trỏ API về máy cá nhân `NEXT_PUBLIC_API_URL=http://localhost:8001/api/v1`

---

## 2. Quy trình Cập nhật & Đẩy Lên Mạng (ProductionDeploy)

Khi bạn viết xong code ở máy, test thấy ổn thỏa, hãy làm theo quy trình 4 Bước sau đây để Hệ thống chính thức áp dụng:

### Bước 1: Khai báo thay đổi cho Database (Nếu có)
Nếu trong quá trình code, bạn **có gắn thêm tính năng liên quan đến Database** (ví dụ: tạo bảng mới, đổi tên cột, viết function mới như thuật toán Hybrid Search), bạn phải đăng nhập vào [Supabase Dashboard](https://supabase.com/dashboard) và chạy mã `.sql` đó trong mục **SQL Editor**. 
*(Nếu chỉ sửa logic code Python hay giao diện React thì bỏ qua Bước 1 này).*

### Bước 2: Commit và Push mã nguồn lên GitHub
Tạo bản lưu (commit) và đẩy (push) code mới nhất lên kho lưu trữ GitHub:
```bash
git add .
git commit -m "feat: [tên tính năng vừa làm]"
git push origin main
```

### Bước 3: Deploy Backend trên Render.com
Render đóng vai trò là "bộ não" API xử lý mọi yêu cầu của ứng dụng.
1. Truy cập [Render Dashboard](https://dashboard.render.com).
2. Vào Web Service backend của bạn (`ebook-api-xyz`).
3. Nếu bạn đã cấu hình Github Auto-Deploy, bước này tự động diễn ra.
4. Nếu *không* cấu hình tự động (như trường hợp báo lỗi Not Found), hãy thủ công:
   - Nhấp vào nút **Manual Deploy** góc trên bên phải.
   - Chọn **Deploy latest commit** và chờ cho đến khi có trạng thái **Live** (màu xanh).

### Bước 4: Deploy Frontend trên Vercel
Vercel chứa Giao diện người dùng. Bản chất Vercel rất nhạy với GitHub.
1. Ngay khi bạn gõ lệnh `git push` ở Bước 2, Vercel **đã tự động** kích hoạt quá trình Build.
2. Nếu muốn kiểm tra trạng thái, bạn có thể vào [Vercel Dashboard](https://vercel.com/dashboard) xem ứng dụng đang được Compile. Chừng 1-2 phút là xong.
3. Khi báo xanh, website Front-end của bạn đã sở hữu giao diện/code mới! 

> **Lưu ý Environment Variables trên Vercel:**
> - Đi tới Settings > Environment Variables
> - Đảm bảo rằng `NEXT_PUBLIC_API_URL` trỏ về tên miền thực tế của Render (ví dụ: `https://ebook-api-7v44.onrender.com/api/v1`). Tuyệt đối không để `localhost`.

---

## 3. Quản lý Admin mặc định
Database Supabase hiện đang lưu trữ:
- **Tài khoản Admin mặc định:** `admin`
- **Mật khẩu:** `admin123`
*(Bạn có thể thay đổi bằng cách login vào hệ thống web sau đó cập nhật thông tin trong Profile).*

---

## Tóm tắt lỗi phổ biến & Xử lý:
- **Lỗi truy cập Vercel báo `Failed to Fetch` hoặc vòng xoay vô tận**: Do Frontend (Vercel) gọi nhầm API localhost hoặc API của Render chưa deploy kịp code mới nhất. -> Làm lại **Bước 3**.
- **Lỗi 500 khi thao tác xóa/chỉnh sửa sách**: Do Database chưa đồng bộ luồng logic mới. -> Kiểm tra lại **Bước 1** (Xem có quên chạy đoạn SQL nào không).
