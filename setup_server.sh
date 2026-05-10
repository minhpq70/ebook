#!/bin/bash
# =====================================================================
# TỰ ĐỘNG CÀI ĐẶT MÔI TRƯỜNG MÁY CHỦ CHO EBOOK PLATFORM
# Dành cho: Ubuntu 22.04 LTS / 24.04 LTS
# =====================================================================

# Thoát ngay nếu một dòng lệnh nào fail
set -e

# Báo màu dễ nhìn
NC='\033[0m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'

echo -e "${CYAN}==========================================${NC}"
echo -e "${GREEN}1. Cập nhật hệ điều hành Ubuntu...${NC}"
echo -e "${CYAN}==========================================${NC}"
sudo apt-get update && sudo apt-get upgrade -y

echo -e "${CYAN}==========================================${NC}"
echo -e "${GREEN}2. Cài đặt Tiện ích Hệ Thống & Thư viện đồ họa cho OCR${NC}"
echo -e "${CYAN}==========================================${NC}"
sudo apt-get install -y curl git wget unzip software-properties-common build-essential
# libgl1 + libglib2.0 cần cho PaddleOCR (OpenCV headless)
# Tesseract giữ làm fallback cuối cùng nếu PaddleOCR lỗi
sudo apt-get install -y libgl1 libglib2.0-0 tesseract-ocr tesseract-ocr-vie

echo -e "${CYAN}==========================================${NC}"
echo -e "${GREEN}3. Cài đặt Docker & Docker Compose (Cho Supabase Self-Hosted)${NC}"
echo -e "${CYAN}==========================================${NC}"
sudo apt-get install -y docker.io docker-compose-v2
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER

echo -e "${CYAN}==========================================${NC}"
echo -e "${GREEN}4. Cài đặt Node.js 20 & PM2${NC}"
echo -e "${CYAN}==========================================${NC}"
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
sudo npm install -g pm2

echo -e "${CYAN}==========================================${NC}"
echo -e "${GREEN}5. Cài đặt Python 3.12 và Virtual Environment${NC}"
echo -e "${CYAN}==========================================${NC}"
if ! command -v python3.12 &> /dev/null; then
    sudo add-apt-repository ppa:deadsnakes/ppa -y
    sudo apt-get update
fi
sudo apt-get install -y python3.12 python3.12-venv python3.12-dev

echo -e "${CYAN}==========================================${NC}"
echo -e "${GREEN}6. Cài đặt Nginx Reverse Proxy${NC}"
echo -e "${CYAN}==========================================${NC}"
sudo apt-get install -y nginx
sudo systemctl enable nginx
sudo systemctl start nginx

echo -e "${CYAN}==========================================${NC}"
echo -e "${GREEN}7. Cài đặt Redis Server (cho cache & ingestion queue)${NC}"
echo -e "${CYAN}==========================================${NC}"
sudo apt-get install -y redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server

echo -e "\n${CYAN}=======================================================${NC}"
echo -e "${GREEN}✓ HOÀN TẤT XÂY DỰNG MÔI TRƯỜNG MÁY CHỦ!${NC}"
echo -e "${CYAN}=======================================================${NC}"
echo -e "Server đã trang bị: Docker, Node 20, PM2, Python 3.12, Nginx, Redis."
echo -e "OCR Engine: PaddleOCR + VietOCR (cài qua pip ở bước tiếp), Tesseract fallback."
echo -e ""
echo -e "${YELLOW}➡ Tiếp theo: mở SERVER_MIGRATION_GUIDE.md và thực hiện BƯỚC 2.${NC}"
