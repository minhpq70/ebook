# Kế Hoạch Nâng Cấp OCR: PaddleOCR + VietOCR

> Thay thế Tesseract bằng pipeline OCR 2 tầng chuyên biệt cho tiếng Việt.

## Hiện Trạng (Tesseract)

- Model: `tesseract` + language pack `vie`
- Chất lượng tiếng Việt: **70-85%** (hay nhầm dấu: ả↔ã, ố↔ổ, ừ↔ự)
- Tốc độ: ~3-5s/trang
- File: `services/pdf_processor.py` → `iter_pdf_page_batches()`, `extract_pages_from_pdf()`

## Pipeline Mới: 2 Tầng

```
Trang PDF
   │
   ▼
PyMuPDF get_text()
   │
   ├─ Text hợp lệ (>50 ký tự, tiếng Việt) → ✅ Bỏ qua OCR
   │
   └─ Scan/ảnh (rỗng hoặc <50 ký tự) → OCR Pipeline:
       │
       ▼
   Tầng 1: PaddleOCR
       ├─ Detection: tìm bounding boxes vùng chữ
       ├─ Recognition: nhận dạng text từng vùng
       └─ Trả về: [(bbox, text, confidence), ...]
       │
       ├─ confidence >= 0.85 → ✅ Dùng kết quả PaddleOCR
       │
       └─ confidence < 0.85 → Tầng 2: VietOCR
           ├─ Crop ảnh theo bbox từ PaddleOCR
           ├─ Recognition lại bằng VietOCR (vgg_transformer)
           └─ ✅ Dùng kết quả VietOCR (chính xác hơn cho dấu Việt)
```

## So Sánh Chất Lượng

| Hệ thống | Tốc độ/trang | Chính xác (tiếng Việt) | Dấu thanh |
|----------|-------------|----------------------|-----------|
| Tesseract (hiện tại) | ~3-5s | 70-85% | Hay nhầm |
| PaddleOCR only | ~1-2s | 85-90% | Khá |
| **PaddleOCR + VietOCR** | ~2-4s | **92-97%** | **Rất tốt** |

## Dependencies Cần Thêm

```txt
# requirements.txt
paddlepaddle==3.0.0    # PaddlePaddle framework (~200MB)
paddleocr==2.9.1       # PaddleOCR wrapper (~100MB)
vietocr==0.3.5         # VietOCR recognition (~50MB + pretrained weights)
```

## Files Cần Sửa

| File | Thay đổi |
|------|---------|
| `services/pdf_processor.py` | Thay Tesseract bằng PaddleOCR + VietOCR trong `iter_pdf_page_batches()` |
| `services/metadata_extractor.py` | Cập nhật `extract_early_text()` và `extract_toc()` dùng OCR mới |
| `requirements.txt` | Thêm paddlepaddle, paddleocr, vietocr |
| `Dockerfile` | Bỏ Tesseract packages, thêm PaddlePaddle deps |

## Lưu Ý Triển Khai

- **RAM**: PaddleOCR + VietOCR cần **≥1GB RAM** → Render free tier (512MB) không đủ
- **CPU-only**: Cả hai đều chạy được trên CPU, không bắt buộc GPU
- **Confidence threshold 0.85**: Có thể điều chỉnh tùy chất lượng scan thực tế
- **PDF text-based**: Hoàn toàn bỏ qua OCR → không tốn resource

## Trạng Thái

- [x] Code đã triển khai: `services/ocr_engine.py`, cập nhật `pdf_processor.py` và `metadata_extractor.py`
- [x] Dependencies: `paddlepaddle`, `paddleocr`, `torch`, `vietocr` trong `requirements.txt`
- [x] Graceful fallback: PaddleOCR → VietOCR → Tesseract (hệ thống không crash nếu thiếu package)
