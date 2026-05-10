# Kế hoạch Cài đặt Bot Điều khiển Từ xa qua Telegram (Dùng Remoat)

Thật bất ngờ và tuyệt vời! Nhờ bạn nhắc đến cụm từ `Remoat`, tôi đã ngay lập tức tra cứu trên mạng và phát hiện ra **Remoat** thực sự là một bộ mã nguồn mở (Open-source package) đã được cộng đồng đóng gói sẵn trên hệ thống `npm`! 

Điều này có nghĩa là thay vì chúng ta phải "tự chế" một hệ thống dò tìm giao diện mất 3-4 tiếng như Kế hoạch cũ, chúng ta có thể **sử dụng thẳng Remoat**! Nó đã giải quyết bài toán giao tiếp với Chrome DevTools Protocol (CDP) của Antigravity cực kỳ gọn gàng.

> [!TIP]
> Việc xài hàng chuẩn của cộng đồng giúp chúng ta rút ngắn thời gian thiết lập xuống chỉ còn **10 phút**!

Tuy nhiên, dù dùng phần mềm nào, nguyên lý chọc vào lõi hệ thống vẫn không đổi. Để bắt đầu, bạn cần đồng ý với Kế hoạch Triển khai sau:

## User Review Required

### 1. Vẫn BẮT BUỘC khởi động lại Antigravity để mở cổng kết nối
Dù Remoat có xịn đến đâu, nó vẫn cần hệ thống Antigravity mở cổng nhà. Bạn bắt buộc phải tắt cửa sổ làm việc hiện tại, mở Terminal lên và gõ lại lệnh khởi động có đính kèm Chìa khóa Cổng như sau:
`antigravity --remote-debugging-port=9222`
*(Hoặc thêm cờ `--remote-debugging-port=9222` vào lệnh khởi động bạn thường dùng. Điều này làm gián đoạn mạch nói chuyện hiện tại, và chúng ta sẽ phải chào lại từ đầu).*

### 2. Cần tương tác với BotFather
Sau khi làm bước 1 xong, bạn sẽ dùng điện thoại mở Telegram, tìm `@BotFather` để tạo một con bot mới và đưa Token cho tôi gán vào `Remoat`.

## Proposed Changes

Kế hoạch này sẽ cài đặt và cấu hình phần mềm có sẵn:

### [NEW] Cài đặt `remoat` Toàn cầu
- Sử dụng Node.js (vừa rà soát thấy máy bạn đã cài Node v22) để kéo bộ cài đặt:
  `npm install -g remoat` (Hoặc nếu bị lỗi quyền, có thể chạy `npm install remoat` trong thư mục dự án và dùng `npx remoat`)

### [NEW] Cấu hình Token và Thư mục
- Chạy lệnh khởi tạo của remoat:
  `remoat config --token "YOUR_TELEGRAM_BOT_TOKEN"`
- Gắn quyền quản lý (bind) Remoat vào đúng vị trí dự án eBook hiện tại:
  `remoat bind /home/tinhvan/apps/ebook-platform`

### [NEW] Khởi chạy làm dịch vụ ngầm (Daemon)
- Dùng công cụ `pm2` (mà bạn đã cài sẵn từ đợt chạy web Backend) để chuyển Remoat thành một bóng ma chạy ngầm vĩnh viễn trên máy chủ VPS.

---

## Open Questions

> [!IMPORTANT]
> **Quyết định chốt hạ:**
> Nếu Kế hoạch cài đặt Remoat này đúng như mong ước của bạn, hãy báo cho tôi **"Đồng ý/Approve"**. 
> Tuy nhiên, **KHOAN HÃY KHỞI ĐỘNG LẠI PHẦN MỀM LÚC NÀY**. Hãy đợi tôi gõ lệnh cài đặt `remoat` thành công xong đã, sau đó tôi sẽ đưa tín hiệu để bạn tắt phần mềm Antigravity và mở lại sau cùng!

## Verification Plan
1. Telegram trên iPhone của bạn gửi lệnh `/status` tới con Bot của bạn.
2. Remoat quét xem Antigravity có đang bật không và báo "Antigravity is connected (Port 9222)".
3. Bạn ra lệnh "Review file README.md", Antigravity trên VPS sẽ tự chạy.
