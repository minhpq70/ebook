import asyncio
from core.supabase_client import get_supabase
from services.metadata_extractor import get_cover_image_bytes, generate_ai_summary

async def main():
    sb = get_supabase()
    res = sb.table("books").select("id, file_path, cover_url, ai_summary").execute()
    for book in res.data:
        book_id = book["id"]
        print(f"Processing {book_id}...")
        
        # Download PDF bytes
        try:
            pdf_res = sb.storage.from_("books").download(book["file_path"])
        except Exception as e:
            print(f"Lỗi tải PDF cho sách {book_id}: {e}")
            continue
            
        update_data = {}
        # Luôn ghi đè cover_url lại sang bucket covers
        cover_bytes = get_cover_image_bytes(pdf_res)
        if cover_bytes:
            cover_path = f"{book_id}.jpeg"
            sb.storage.from_("covers").upload(
                path=cover_path,
                file=cover_bytes,
                file_options={"content-type": "image/jpeg", "upsert": "true"}
            )
            cover_url = sb.storage.from_("covers").get_public_url(cover_path)
            if isinstance(cover_url, dict):
                cover_url = cover_url.get('publicURL', cover_url.get('publicUrl'))
            if not cover_url:
                cover_url = f"{sb.supabase_url}/storage/v1/object/public/covers/{cover_path}"
            update_data["cover_url"] = cover_url
            print(f" - Tạo ảnh bìa thành công Bucket COVERS")

        if not book.get("ai_summary"):
            summary = await generate_ai_summary(pdf_res)
            if summary:
                update_data["ai_summary"] = summary
                print(f" - Tạo AI summary thành công")

        if update_data:
            sb.table("books").update(update_data).eq("id", book_id).execute()
            print(f" - Đã update DB url: {update_data.get('cover_url')}")

if __name__ == "__main__":
    asyncio.run(main())
