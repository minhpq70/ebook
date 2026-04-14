# Hướng Dẫn Điều Khiển Antigravity Bằng Điện Thoại (Qua SSH & Tmux)

Tài liệu này hướng dẫn cách thiết lập một phiên làm việc thông minh 24/7. Bạn có thể sử dụng điện thoại để ra lệnh cho AI Agent (Antigravity) chạy ngầm trên Máy Chủ (VPS) hoặc ngay trên chiếc máy tính (Macbook) đang cấu hình này.

Khái niệm cốt lõi: Sử dụng `tmux` (Terminal Multiplexer) - đây là một công cụ giúp mở và giữ các cửa sổ Terminal luôn chạy ngầm, kể cả khi bạn đột ngột mất kết nối mạng hay tắt ứng dụng SSH trên điện thoại.

---

## 🚀 Bước 1: Chuẩn bị App trên Điện Thoại
Bạn cần cài đặt một ứng dụng SSH (Secure Shell) lên điện thoại để truy cập từ xa vào thiết bị đang chạy Antigravity.

- **Dành cho iOS (iPhone/iPad):**
  - Khuyên dùng: **Termius** hoặc **Shelly**.
- **Dành cho Android:**
  - Khuyên dùng: **Termius** hoặc **JuiceSSH**.

*Quy trình kết nối trên điện thoại:* Mở App > Tạo kết nối mới (New Host) > Nhập IP của Máy chủ (hoặc IP Local của Macbook) > Nhập thông tin User & Password hoặc key SSH.

---

## 🛠 Bước 2: Cài Đặt và Hiểu Về `tmux` trên Thiết Bị Chạy AI
Công cụ `tmux` cho phép tạo "phòng họp ẩn" để Antigravity làm việc.

### Môi trường Ubuntu ( Máy chủ VPS):
```bash
sudo apt-get update
sudo apt-get install tmux -y
```

### Môi trường MacOS (như máy bạn đang dùng hiện tại):
```bash
# Cài đặt qua Homebrew
brew install tmux
```

---

## 🕹 Bước 3: Quy Trình Thao Tác (Workflow Thực Tế)

Hãy tưởng tượng bạn đang đi công tác, rút điện thoại ra và muốn yêu cầu Antigravity triển khai phiên bản mới của dự án.

**1. Tạo phòng làm việc ảo:**
Mở Termius trên điện thoại, đăng nhập vào máy chủ. Khởi tạo một phiên chạy (session) mới tên là `agent_room`:
```bash
tmux new -s agent_room
```

**2. Gọi AI ra làm việc:**
Sau khi gõ lệnh trên, bạn đã nằm bên trong phòng ảo. Hãy kích hoạt Antigravity:
```bash
antigravity
```
Cửa sổ chat sẽ hiện ra trên màn hình điện thoại. Gõ yêu cầu của bạn: *"Cập nhật giao diện mới nhất từ nhánh git rồi khởi động lại PM2 giúp tôi nhé."*

**3. "Tàng hình" để AI tự xử lý (Detach):**
Điểm ăn tiền nhất của `tmux`: Giữa chừng bạn bận hoặc điện thoại sắp hết pin, bạn nhấn phím để thoát (ẩn) phiên làm việc xuống dưới ngầm. Antigravity bên trong vẫn đang tự động fix bug hoặc config server mà không hề bị sập!
- **Tổ hợp phím tắt trên bàn phím mặc định:** Nhấn `Ctrl + b` sau đó buông ra và nhấn chữ `d` (viết tắt của detach).
- (Hoặc tắt phụt ứng dụng Termius một cách đột ngột, hệ thống cũng coi như là lệnh Detach).

**4. Quay trở lại phòng làm việc để kiểm tra kết quả (Attach):**
Chiều về, bạn có thể lấy iPad hoặc mở máy tính bàn, kết nối SSH vào lại con VPS đó và gọi lệnh để quay lại căn phòng lúc sáng:
```bash
tmux attach -t agent_room
```
Toàn bộ lịch sử tin nhắn, kết quả deploy sẽ lại hiện ra đầy đủ trên màn hình y như lúc bạn rời đi. Rất thú vị và liền mạch!

---

## 💡 Tổng Hợp Lệnh `tmux` Quan Trọng Nhất (Lưu ý)
- `tmux ls` : Xem danh sách các "phòng ảo" đang mở.
- `tmux attach -t <tên_phòng>` : Quay lại phòng đang để ẩn.
- `tmux kill-session -t <tên_phòng>` : Đóng hẳn phòng (Ví dụ bạn xong việc không cần AI chạy ngầm nữa).
- Bấm tổ hợp `Ctrl + b` rồi phím `[` : Để cuộn xem lịch sử chat của Terminal (Bấm phím mũi tên lên/xuống). Để thoát chế độ cuộn thì nhấn `q`.

> **Mẹo nâng cao:** Thao tác bàn phím ảo trên điện thoại để bấm `Ctrl+B -> D` hơi cực. Nhiều phần mềm như Termius có sẵn thanh công cụ phía trên bàn phím có sẵn lệnh tắt (Macro) để bắn phím `Ctrl`, bạn nên ghim nút `Ctrl + B` để thao tác chớp nhoáng.
