#!/usr/bin/env python3
"""
Helper script để convert Google Service Account JSON thành environment variable.

Cách sử dụng:
1. Đặt file service_account.json vào cùng thư mục với script này
2. Chạy: python convert_sa_json.py
3. Copy output vào .env file: GOOGLE_SA_JSON="output_string"
"""

import json
import base64
import sys
from pathlib import Path

def main():
    json_file = Path(__file__).parent / "service_account.json"
    
    if not json_file.exists():
        print("❌ Không tìm thấy file service_account.json")
        print("Đặt file service_account.json vào cùng thư mục với script này")
        sys.exit(1)
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Convert to JSON string
        json_str = json.dumps(data, separators=(',', ':'))
        
        # Base64 encode để tránh vấn đề escape characters
        encoded = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')
        
        print("✅ Chuyển đổi thành công!")
        print()
        print("Thêm vào file .env:")
        print(f"GOOGLE_SA_JSON={encoded}")
        print()
        print("Hoặc sử dụng JSON string trực tiếp:")
        print(f"GOOGLE_SA_JSON='{json_str}'")
        print()
        print("⚠️  Xóa file service_account.json sau khi đã copy vào .env")
        
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()