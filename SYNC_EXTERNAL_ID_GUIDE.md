# Hướng dẫn đồng bộ External ID từ CSV

## Mục đích

Gán `external_id` (mã sách từ Libol/XBĐT) cho các cuốn sách đã có trong hệ thống Ebook AI.  
Sau khi gán, iframe chat có thể nhúng bằng `external_id` thay vì UUID nội bộ.

## Chuẩn bị file CSV

Tạo file CSV với **2 cột bắt buộc**:

| Cột | Mô tả | Ví dụ |
|-----|--------|-------|
| `title` | Tên sách (phải khớp chính xác với title trong DB) | Hạt giống tâm hồn |
| `book_id` | Mã sách từ hệ thống nguồn (Libol, STBOOK...) | CP111BK12021051414403174112204-5 |

**Ví dụ file `books.csv`:**

```csv
title,book_id
Hạt giống tâm hồn,12345
Xây dựng Đảng về đạo đức - Một số vấn đề lý luận và thực tiễn,67890
Những điểm mới về an ninh quốc gia trong Văn kiện Đại hội XIII của Đảng,11223
```

> **Lưu ý:** Cột `title` phải khớp **chính xác** với tên sách trong CSDL. Nếu tên không khớp, script sẽ báo "Không tìm thấy".

## Chạy script

```bash
cd /home/tinhvan/apps/ebook-platform/api
venv/bin/python sync_external_ids.py <đường_dẫn_csv> --source <tên_hệ_thống>
```

**Ví dụ:**

```bash
# Đồng bộ từ Libol (mặc định)
venv/bin/python sync_external_ids.py data/books.csv

# Đồng bộ từ STBOOK
venv/bin/python sync_external_ids.py data/stbook_ids.csv --source STBOOK
```

## Kết quả

Script sẽ in báo cáo:

```
========================================
TỔNG KẾT ĐỒNG BỘ
========================================
Cập nhật thành công : 5
Bỏ qua (đã trùng khớp): 2
Không tìm thấy tên  : 1
```

## Các trường trong CSDL liên quan

| Trường | Mô tả |
|--------|--------|
| `id` | UUID nội bộ (tự sinh khi upload) |
| `external_id` | Mã sách từ hệ thống bên ngoài (Libol/STBOOK) |
| `source_system` | Tên hệ thống nguồn: `Libol`, `STBOOK`... |

## Nhúng iframe bằng External ID

Sau khi gán `external_id`, có thể nhúng chat iframe bằng mã sách thay vì UUID:

```html
<iframe src="https://bookai.tinhvan.com/test_chat.html?book_id=<external_id>"></iframe>
```

Hệ thống sẽ tự tra `external_id` → tìm sách tương ứng trong DB.

## File liên quan

- Script: `api/sync_external_ids.py`
- Bảng DB: `books` (cột `external_id`, `source_system`)
- Hàm lookup: `api/services/ingestion.py` → `get_book()` (hỗ trợ cả UUID và external_id)
