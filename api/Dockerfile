# ── Build Stage ─────────────────────────────────────────────
FROM python:3.12-slim AS base

# Tesseract OCR + Vietnamese language pack (cần cho OCR fallback)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-vie \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements trước để cache layer pip install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Tạo thư mục logs
RUN mkdir -p logs

# Xóa các file nhạy cảm nếu vô tình copy vào
RUN rm -f .env service_account.json

EXPOSE 8001

# Uvicorn production server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2"]
