# Kế Hoạch Tích Hợp: Thư Viện Số (.NET) & AI Ebook Platform

Tài liệu này mô tả chi tiết phương án kiến trúc và API để tích hợp Hệ thống Thư viện số hiện tại (System A - viết bằng .NET, chạy trên Windows) với Nền tảng AI Ebook (System B - viết bằng Python/FastAPI, chạy trên Linux).

---

## 1. Chiến Lược Quản Lý ID Sách (BookID Mapping & Deduplication)

**Vấn đề:** Làm sao để biết một cuốn sách trên System A đã được đưa vào System B chưa, tránh việc tải và xử lý lại (vector hóa tốn kém tiền API)?

**Giải pháp đề xuất: Dùng `external_id` làm cầu nối.**
- Mọi cuốn sách trong System B (AI) đều tự sinh ra một `book_id` nội bộ (UUID). Tuy nhiên, bảng `books` trong Database của System B sẽ được thêm một cột phụ là `external_id` (Lưu ID của sách bên System A) và một cột `source_system` (VD: 'Library_NET').
- **Cơ chế chống trùng lặp (Deduplication):** 
  Khi System A gọi lệnh yêu cầu AI học một cuốn sách (truyền sang `external_id = 105`), System B sẽ query trong database:
  1. Nếu đã tồn tại sách có `external_id = 105`: System B dừng ngay lập tức, trả về kết quả 200 OK kèm thông báo "Sách đã tồn tại và sẵn sàng" cùng `book_id` nội bộ. Không thực hiện tải file hay vector hóa nữa.
  2. Nếu chưa tồn tại: System B tạo bản ghi mới, lưu `external_id = 105` và bắt đầu tải file về để xử lý.

---

## 2. Phase 0: Đồng Bộ Dữ Liệu Cũ (Data Migration / CSV Sync)
*Kịch bản: Xử lý các cuốn sách đã được upload thủ công lên System B từ trước khi có tích hợp API.*

**Vấn đề:** Các sách này đã tồn tại trong CSDL của System B nhưng chưa có mã `external_id` từ System A. 
**Giải pháp: Import danh sách ánh xạ từ Excel/CSV.**

1. **Chuẩn bị file CSV:** System A xuất một file CSV gồm 2 cột: `title` (Nhan đề sách) và `book_id` (Mã sách trên System A).
2. **Chạy Script Đồng bộ (System B):**
   - Viết một kịch bản (script) Python hoặc một API Admin để đọc file CSV này.
   - Script duyệt từng dòng CSV, tìm kiếm trong Database của System B xem có cuốn sách nào khớp `title` (nhan đề) không.
   - Nếu tìm thấy và cuốn đó chưa có `external_id` (đang null) ➡️ Tiến hành `UPDATE` ghi mã `book_id` (của System A) vào cột `external_id`.
   - Nếu tìm thấy nhưng đã có `external_id` khớp với `book_id` ➡️ Bỏ qua.
3. **Kết quả:** Sau khi script chạy xong, toàn bộ sách cũ trên System B đều đã mang "chứng minh thư" của System A. Hệ thống Iframe (ở Phase 1) có thể lập tức gọi và chat với các sách này thông qua `?book_ref=external_id` mà không gặp lỗi.

---

## 3. Phase 1: Tích Hợp Qua Mạng (Khuyên Dùng)
*Kịch bản: System A và System B nằm trên 2 máy chủ khác nhau (Windows vs Linux).*

### Bước 1: Gửi sách sang hệ thống AI (System A gọi System B)

Khi biên tập viên upload sách thành công trên phần mềm Thư viện số, System A tự động trigger một HTTP Request sang System B.

**API do System B cung cấp:**
- **Endpoint:** `POST /api/v1/integration/books/ingest`
- **Headers:** 
  - `Authorization: Bearer <SHARED_EMBED_SECRET>` (Khóa bí mật dùng chung giữa 2 hệ thống).
- **Body (JSON):**
  ```json
  {
    "external_id": "105",
    "pdf_url": "https://library.com/downloads/temp-token-123.pdf", 
    "metadata": {
      "title": "Lịch sử Việt Nam",
      "author": "Trần Trọng Kim"
    },
    "webhook_callback": "https://library.com/api/webhooks/ai-ingestion-status"
  }
  ```
*(Lưu ý: `pdf_url` nên là một link có thời hạn hoặc có token bảo mật mà System B có thể gọi để tải file PDF về).*

**Phản hồi từ System B:** Trả về `202 Accepted` ngay lập tức, báo hiệu đã nhận lệnh và cho tiến trình chạy ngầm.

### Bước 2: Webhook thông báo kết quả (System B gọi System A)

Việc OCR và Vector hóa có thể mất từ vài chục giây đến vài phút tùy độ dài sách. Sau khi xong, System B sẽ gọi ngược lại System A.

**Gợi ý API Webhook cho System A (.NET) tự xây dựng:**
- **Endpoint:** `POST /api/webhooks/ai-ingestion-status` (Theo đường dẫn `webhook_callback` gửi ở bước 1)
- **Headers:** `Authorization: Bearer <SHARED_EMBED_SECRET>`
- **Body (JSON):**
  ```json
  {
    "external_id": "105",
    "internal_book_id": "uuid-abc-123",
    "status": "COMPLETED", // hoặc "FAILED"
    "message": "Đã xử lý 450 trang sách, vector hóa thành công."
  }
  ```
Khi System A nhận được Webhook này, nó sẽ update trạng thái trong CSDL nội bộ là: *Sách ID 105 đã có AI hỗ trợ*.

### Bước 3: Tích hợp Giao diện Chat vào Thư viện số (Iframe)

Trên trang chi tiết cuốn sách ID 105 của System A, chèn một thẻ Iframe trỏ về giao diện Chat của System B.

**Vấn đề: Iframe làm sao biết đang nói về cuốn sách nào?**
Ta sẽ truyền `external_id` (hoặc `internal_book_id`) trực tiếp vào chuỗi Query String của URL Iframe. 

**Cơ chế bảo mật (JWT):**
Để chống việc user copy link Iframe mang ra ngoài dùng chùa, Backend của System A (C#) sẽ dùng `<SHARED_EMBED_SECRET>` sinh ra một mã JWT có thời hạn ngắn (ví dụ 60 phút) chứa thông tin sách.

**Mã nguồn nhúng trên System A (HTML/JS):**
```html
<!-- System A sinh ra iframe url này từ phía server -->
<iframe 
  src="https://ai.domain.com/chat/embed?token=eyJhbGciOiJIUz...&book_ref=105" 
  width="100%" 
  height="600px" 
  frameborder="0">
</iframe>
```
*Logic trên System B:* Khi nhận request load Iframe, nó giải mã `token`, nếu hợp lệ và token đúng là cho cuốn sách có `external_id = 105`, nó mới hiển thị giao diện UI chat và chỉ khoanh vùng RAG tìm kiếm tài liệu trong cuốn sách đó.

---

## 4. Phase 2: Tích Hợp Cùng Máy Chủ (Tùy Chọn)
*(Chỉ dùng nếu System A sau này được deploy cùng trên máy chủ Linux/Docker chứa System B).*

Sự khác biệt duy nhất nằm ở **Bước 1**. Thay vì System A phải mở một public URL tải file `pdf_url` (vừa chậm vừa tốn băng thông), System A chỉ cần ghi file vào một thư mục dùng chung (Share Volume).

**API Bước 1 sẽ đổi thành:**
```json
{
  "external_id": "105",
  "local_file_path": "/var/shared_uploads/books/105.pdf",
  "metadata": {...}
}
```
System B chỉ việc dùng lệnh đọc file từ đường dẫn `/var/shared_uploads/books/105.pdf`, bỏ qua được toàn bộ khâu tải file qua mạng HTTP, giúp tiết kiệm 100% chi phí băng thông nội bộ và tốc độ xử lý tức thời.

Các bước Webhook và Iframe Chat vẫn giữ nguyên kiến trúc bảo mật như Phase 1.
