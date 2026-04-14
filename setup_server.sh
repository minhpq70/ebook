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

echo -e "${CYAN}==========================================${NC}"
echo -e "${GREEN}1. Cập nhật hệ điều hành Ubuntu...${NC}"
echo -e "${CYAN}==========================================${NC}"
sudo apt-get update && sudo apt-get upgrade -y

echo -e "${CYAN}==========================================${NC}"
echo -e "${GREEN}2. Cài đặt Tiện ích Hệ Thống mềm & Tesseract OCR (Nhận diện tiếng Việt)${NC}"
echo -e "${CYAN}==========================================${NC}"
sudo apt-get install -y curl git wget unzip software-properties-common build-essential
sudo apt-get install -y tesseract-ocr tesseract-ocr-vie libgl1 

echo -e "${CYAN}==========================================${NC}"
echo -e "${GREEN}3. Cài đặt Docker & Docker Compose (Để dùng cho Bản Mod Supabase)${NC}"
echo -e "${CYAN}==========================================${NC}"
# Cài bản docker engine trực tiếp từ ubuntu universe repo
sudo apt-get install -y docker.io docker-compose-v2
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER

echo -e "${CYAN}==========================================${NC}"
echo -e "${GREEN}4. Cài đặt Node.js 20 & trình quản lý quy trình PM2${NC}"
echo -e "${CYAN}==========================================${NC}"
# Down repo Node 20
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
# Cài đặt PM2 global
sudo npm install -g pm2

echo -e "${CYAN}==========================================${NC}"
echo -e "${GREEN}5. Cài đặt Python 3.12 và công cụ Virtual Environment${NC}"
echo -e "${CYAN}==========================================${NC}"
# (Tùy phiên bản Ubuntu, Ubuntu 24.04 đã có sẵn python 3.12, 22.04 thì add deadsnakes PPA)
if ! command -v python3.12 &> /dev/null; then
    sudo add-apt-repository ppa:deadsnakes/ppa -y
    sudo apt-get update
fi
sudo apt-get install -y python3.12 python3.12-venv python3.12-dev

echo -e "${CYAN}==========================================${NC}"
echo -e "${GREEN}6. Cài đặt Cổng Proxy Nginx${NC}"
echo -e "${CYAN}==========================================${NC}"
sudo apt-get install -y nginx
sudo systemctl enable nginx
sudo systemctl start nginx

echo -e "\n${CYAN}=======================================================${NC}"
echo -e "${GREEN}✓ HOÀN TẤT XÂY DỰNG MÔI TRƯỜNG VẬT LÝ MACHINE!${NC}"
echo -e "${CYAN}=======================================================${NC}"
echo -e "Server này hiện tại đã trang bị tận răng: Docker, Node20, PM2, Python3.12, Nginx, Tesseract-OCR(Vie)."
echo -e "\nBạn vui lòng mở file server_migration_guide.md và thực hiện tiếp BƯỚC 2 (Tạo Local Supabase bằng Docker). Chúc may mắn!"
