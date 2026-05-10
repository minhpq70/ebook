"""
Đồng bộ external_id từ file CSV cho sách.
Ghi vào bảng book_external_ids (mapping table).

Usage:
    venv/bin/python sync_external_ids.py data/books.csv --source Libol
"""
import sys
import csv
import os
import argparse
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("Error: SUPABASE_URL or SUPABASE_SERVICE_KEY not set in .env")
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def sync_books(csv_file_path: str, source_system: str):
    try:
        with open(csv_file_path, mode='r', encoding='utf-8-sig') as file:
            # Auto-detect delimiter (dấu phẩy hoặc dấu chấm phẩy)
            sample = file.read(2048)
            file.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=',;\t')
            except csv.Error:
                dialect = csv.excel
            reader = csv.DictReader(file, dialect=dialect)
            
            success_count = 0
            skipped_count = 0
            not_found_count = 0
            
            for row in reader:
                title = row.get("title")
                book_id = row.get("book_id")
                
                if not title or not book_id:
                    print(f"Bỏ qua dòng thiếu thông tin: {row}")
                    continue
                
                # Tìm sách theo tiêu đề (title)
                res = supabase.table("books").select("id, title").eq("title", title).execute()
                books = res.data
                
                if not books:
                    print(f"[-] Không tìm thấy sách với tiêu đề: '{title}'")
                    not_found_count += 1
                    continue
                
                book = books[0]  # Lấy cuốn đầu tiên khớp
                
                # Kiểm tra đã tồn tại trong bảng mapping chưa
                existing = supabase.table("book_external_ids").select("id") \
                    .eq("source_system", source_system) \
                    .eq("external_id", str(book_id)).execute()
                
                if existing.data:
                    print(f"[~] Sách '{title}' đã có external_id = {book_id} (source: {source_system}). Bỏ qua.")
                    skipped_count += 1
                    continue
                
                # Thêm vào bảng mapping
                try:
                    supabase.table("book_external_ids").insert({
                        "book_id": book["id"],
                        "source_system": source_system,
                        "external_id": str(book_id),
                    }).execute()
                    print(f"[+] Thêm mapping: '{title}' -> {source_system}:{book_id}")
                    success_count += 1
                except Exception as e:
                    print(f"[!] Lỗi khi thêm mapping: '{title}' — {e}")
                    
            print("\n" + "="*40)
            print("TỔNG KẾT ĐỒNG BỘ")
            print("="*40)
            print(f"Thêm mapping thành công: {success_count}")
            print(f"Bỏ qua (đã tồn tại) : {skipped_count}")
            print(f"Không tìm thấy tên   : {not_found_count}")

    except Exception as e:
        print(f"Lỗi: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Đồng bộ external_id từ file CSV cho sách")
    parser.add_argument("csv_file", help="Đường dẫn đến file CSV (cột: title, book_id)")
    parser.add_argument("--source", default="Libol", help="Tên hệ thống nguồn (Mặc định: Libol, STBOOK...)")
    args = parser.parse_args()
    
    sync_books(args.csv_file, args.source)
