# Tính năng người dùng — Ebook Platform

Tài liệu này liệt kê tất cả các tính năng mà người dùng có thể khai thác qua giao diện web khi tương tác với sách điện tử đã upload lên hệ thống.

---

## 1. Trang chủ — Duyệt thư viện sách

| Tính năng | Mô tả |
|-----------|-------|
| **Xem danh sách sách** | Hiển thị toàn bộ sách đã upload, nhóm theo danh mục |
| **Lọc theo danh mục** | Chọn tab Kinh tế / Văn hóa Xã hội / Chính trị để lọc sách |
| **Tìm kiếm** | Thanh tìm kiếm trên header (tìm theo tiêu đề) |
| **Xem bìa sách** | Ảnh bìa tự động trích xuất từ trang đầu PDF |
| **Xem metadata** | Tiêu đề, tác giả, nhà xuất bản hiển thị trên card |

**Trang**: `/` → `web/src/app/page.tsx`

---

## 2. Chi tiết sách — Thông tin & Chat AI

| Tính năng | Mô tả |
|-----------|-------|
| **Xem thông tin chi tiết** | Tiêu đề, tác giả, NXB, năm xuất bản, danh mục, số trang, dung lượng |
| **Tóm tắt AI** | Bản tóm tắt nội dung do AI tự động tạo khi upload |
| **Chat hỏi đáp** | Giao diện chat trực tiếp để hỏi về nội dung sách |

**Trang**: `/books/[id]` → `web/src/app/books/[id]/page.tsx`

---

## 3. Đọc sách PDF + AI Assistant (Tính năng chính)

Đây là trang cốt lõi — kết hợp **đọc PDF** bên trái và **AI chat** bên phải.

### 3.1 Đọc PDF

| Tính năng | Mô tả |
|-----------|-------|
| **Xem PDF trực tuyến** | Hiển thị PDF đầy đủ ngay trong trình duyệt |
| **Chọn văn bản** | Bôi đen đoạn text → tự động điền vào ô chat với chế độ "Giải thích" |

### 3.2 AI Assistant — 5 chế độ hỏi đáp hiện tại

#### 💬 Hỏi đáp (`qa`)

Chế độ mặc định, đa năng nhất. AI trả lời mọi câu hỏi dựa trên nội dung sách.

| Thuộc tính | Chi tiết |
|------------|---------|
| **Vai trò AI** | Trợ lý đọc sách thông minh |
| **Nguồn dữ liệu** | Hybrid vector + FTS + keyword supplement + intro context |
| **Temperature** | 0.2 (câu hỏi thường), 0.0 (hỏi mục lục) |
| **Đặc biệt - Mục lục** | Tự động phát hiện trang MỤC LỤC in sẵn trong sách, format heading + bullet points |
| **Đặc biệt - Metadata** | Câu hỏi về biên tập/NXB/tác giả → lấy trực tiếp 10 trang đầu sách |
| **Đặc biệt - Keyword** | Bổ sung ILIKE search cho cụm từ chính xác từ câu hỏi (bắt tiêu đề mục) |
| **Đặc biệt - Intro** | Tự động đính kèm trang Lời giới thiệu/Lời NXB cho mọi Q&A |
| **Đặc biệt - OCR** | Thầm lặng sửa lỗi chính tả OCR, bỏ qua đoạn lỗi nặng, không hiện ghi chú |
| **Format** | Trả lời trực tiếp, KHÔNG mở đầu bằng "Dựa trên các đoạn trích" |

**Ví dụ câu hỏi:**
- "Tác giả nói gì về kinh tế thị trường?"
- "Liệt kê mục lục cuốn sách"
- "Chương 5 đề cập đến những vấn đề gì?"
- "Quan điểm của tác giả về hội nhập quốc tế là gì?"

---

#### 🔍 Giải thích (`explain`)

AI đóng vai giáo viên/chuyên gia, giải thích sâu các khái niệm và đoạn văn khó.

| Thuộc tính | Chi tiết |
|------------|---------|
| **Vai trò AI** | Giáo viên / chuyên gia giải thích |
| **Phong cách** | Đơn giản, dễ hiểu, có ví dụ minh họa |
| **Kích hoạt tự động** | Khi bôi đen text trong PDF → tự chuyển sang chế độ này |

**Ví dụ câu hỏi:**
- "Giải thích khái niệm 'an ninh phi truyền thống'"
- "Đoạn này có nghĩa là gì: '...trích dẫn...'"
- "Tại sao tác giả lại dùng từ 'kiến tạo' trong ngữ cảnh này?"

---

#### 📝 Tóm tắt chương (`summarize_chapter`)

Tóm tắt ngắn gọn một chương hoặc phần cụ thể.

| Thuộc tính | Chi tiết |
|------------|----------|
| **Vai trò AI** | Chuyên gia tóm tắt nội dung |
| **Định dạng** | Bullet points, nêu bật luận điểm chính |
| **Phạm vi** | Tập trung vào chương/phần được yêu cầu |
| **Retrieval thông minh** | Khi hỏi "tóm tắt phần X": tự động xác định phạm vi trang của phần đó, lấy mẫu 25 chunks phân tán đều trên toàn bộ phần |
| **Max tokens** | 8000 (gấp đôi Q&A thường) |
| **OCR** | Đối chiếu nhiều chunks để xác định tiêu đề chính xác, bỏ qua đoạn lỗi nặng |

**Ví dụ câu hỏi:**
- "Tóm tắt chương 3"
- "Nội dung chính của phần 'Đổi mới tư duy' là gì?"
- "Tóm tắt phần mở đầu của cuốn sách"

---

#### 📚 Tóm tắt sách (`summarize_book`)

Cung cấp cái nhìn tổng quan về toàn bộ cuốn sách.

| Thuộc tính | Chi tiết |
|------------|---------|
| **Vai trò AI** | Chuyên gia phân tích sách |
| **Lưu ý** | AI chỉ tóm tắt từ các đoạn trích, không phải toàn bộ sách |
| **Nội dung** | Chủ đề chính, luận điểm trung tâm, điểm nổi bật |

**Ví dụ câu hỏi:**
- "Tóm tắt toàn bộ cuốn sách này"
- "Cuốn sách này nói về điều gì?"
- "Chủ đề trung tâm của sách là gì?"

---

#### ✨ Gợi ý (`suggest`)

AI gợi ý nội dung, chủ đề người đọc nên khám phá thêm.

| Thuộc tính | Chi tiết |
|------------|---------|
| **Vai trò AI** | Trợ lý gợi ý nội dung đọc |
| **Phong cách** | Gợi ý kèm lý do tại sao nên đọc |
| **Mục đích** | Giúp người đọc khám phá sách sâu hơn |

**Ví dụ câu hỏi:**
- "Gợi ý những điểm quan trọng nhất trong sách"
- "Tôi nên đọc phần nào tiếp theo?"
- "Những chủ đề nào đáng chú ý trong cuốn sách?"

---

### 3.3 Đề xuất thêm chế độ hỏi đáp mới

Dưới đây là các chế độ có thể phát triển thêm để tăng giá trị khai thác sách:

#### 🆚 So sánh (`compare`) — ĐỀ XUẤT

So sánh các quan điểm, luận điểm, hoặc khái niệm trong sách.

**Ví dụ câu hỏi:**
- "So sánh quan điểm chương 2 và chương 5 về vấn đề hội nhập"
- "Điểm giống và khác nhau giữa hai giai đoạn lịch sử trong sách?"

---

#### 📊 Phân tích (`analyze`) — ĐỀ XUẤT

Phân tích sâu một luận điểm, đánh giá lập luận, tìm điểm mạnh/yếu.

**Ví dụ câu hỏi:**
- "Phân tích lập luận của tác giả về chính sách kinh tế"
- "Đánh giá tính thuyết phục của luận điểm chương 4"

---

#### 💡 Trích dẫn (`quote`) — ĐỀ XUẤT

Tìm và trích dẫn nguyên văn các câu nói, đoạn văn quan trọng.

**Ví dụ câu hỏi:**
- "Trích dẫn những câu nói hay nhất trong sách"
- "Tìm đoạn tác giả nói về đổi mới sáng tạo"

---

#### 🎓 Câu hỏi ôn tập (`quiz`) — ĐỀ XUẤT

Tạo câu hỏi trắc nghiệm hoặc tự luận để kiểm tra kiến thức sau khi đọc.

**Ví dụ câu hỏi:**
- "Tạo 5 câu hỏi ôn tập cho chương 2"
- "Đặt câu hỏi kiểm tra kiến thức về nội dung sách"

---

#### 🔗 Liên hệ thực tế (`relate`) — ĐỀ XUẤT

Liên hệ nội dung sách với thực tế, sự kiện hiện tại, hoặc ứng dụng thực tiễn.

**Ví dụ câu hỏi:**
- "Nội dung chương 3 liên hệ thế nào với tình hình Việt Nam hiện nay?"
- "Có thể áp dụng bài học nào từ sách vào thực tế?"

---

### 3.4 Trải nghiệm chat

| Tính năng | Mô tả |
|-----------|-------|
| **Streaming (SSE)** | Câu trả lời hiện ra dần từng chữ, giống ChatGPT |
| **Nguồn trích dẫn** | Mỗi câu trả lời có danh sách nguồn (đoạn sách gốc + số trang) |
| **Mở/đóng panel** | Nút "Hỏi AI" trên navbar để ẩn/hiện panel chat |
| **Hỏi tiếp liên tục** | Giao diện chat cho phép hỏi nhiều câu trong cùng phiên |

**Trang**: `/reader/[id]` → `web/src/app/reader/[id]/page.tsx`

---

## 4. Xác thực người dùng

| Tính năng | Mô tả |
|-----------|-------|
| **Đăng ký** | Tạo tài khoản (username, email, password) |
| **Đăng nhập** | Xác thực qua JWT token lưu trong httpOnly cookie |
| **Đăng xuất** | Xóa cookie phiên |
| **Đổi mật khẩu** | Yêu cầu mật khẩu hiện tại + mật khẩu mới (≥ 8 ký tự) |
| **Xem thông tin tài khoản** | Hiển thị username, email, role |

**Trang**: `/login`, `/register`

---

## 5. Quản trị (Admin Only)

Các tính năng chỉ dành cho tài khoản có role `admin`:

| Tính năng | Mô tả |
|-----------|-------|
| **Upload sách PDF** | Upload file PDF (≤ 200MB), tự động trích xuất metadata bằng AI |
| **Tự động trích xuất** | AI tự nhận diện tiêu đề, tác giả, NXB, năm xuất bản từ PDF |
| **Chỉnh sửa metadata** | Sửa tiêu đề, tác giả, NXB, năm, danh mục, mô tả |
| **Xóa sách** | Xóa hoàn toàn sách và dữ liệu vector |
| **Re-ingest** | Xóa chunks cũ và trích xuất lại từ PDF (khi cần cập nhật) |
| **Xem log truy vấn** | 100 dòng log gần nhất (query, token, chi phí) |
| **Cấu hình AI** | Đổi provider/model cho Chat và Embedding |
| **Quản lý danh mục** | Tạo/xóa danh mục sách |

**Trang**: `/admin`, `/admin/upload`

---

## 6. Quy trình xử lý sách (tự động, chạy nền)

Khi admin upload PDF, hệ thống tự động thực hiện:

```
Upload PDF → Trích xuất metadata (AI)
           → Tạo ảnh bìa
           → Cắt nhỏ nội dung (chunking)
           → Tạo embedding vector cho từng chunk
           → Lưu vào Supabase
           → Tạo tóm tắt AI (ai_summary)
           → Trích xuất mục lục (TOC)
           → Đánh dấu status = "ready"
```

---

## 7. Tổng kết tính năng theo vai trò

| Vai trò | Tính năng chính |
|---------|----------------|
| **Khách (chưa đăng nhập)** | Duyệt sách, xem chi tiết, đọc PDF, chat AI |
| **Người dùng (đã đăng nhập)** | Tất cả của khách + đổi mật khẩu, xem tài khoản |
| **Admin** | Tất cả + upload, xóa, sửa metadata, re-ingest, xem log, cấu hình AI |
