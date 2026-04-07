import asyncio
from core.supabase_client import get_supabase
from services.metadata_extractor import extract_toc
from services.pdf_processor import _count_tokens
from services.embedding import embed_batch

async def main():
    sb = get_supabase()
    res = sb.table("books").select("id, file_path").execute()
    for book in res.data:
        book_id = book["id"]
        
        # Kiểm tra xem đã có TOC chưa
        check = sb.table("book_chunks").select("id").eq("book_id", book_id).eq("chunk_index", -1).execute()
        if check.data:
            print(f"Sách {book_id} đã có TOC chunk.")
            continue
            
        print(f"Xử lý TOC cho {book_id}...")
        try:
            pdf_res = sb.storage.from_("books").download(book["file_path"])
        except Exception as e:
            print(f" Lỗi tải PDF: {e}")
            continue
            
        toc_text = extract_toc(pdf_res)
        if toc_text:
            token_count = _count_tokens(toc_text)
            embeddings = await embed_batch([toc_text])
            sb.table("book_chunks").insert({
                "book_id": book_id,
                "chunk_index": -1,
                "page_number": -1,
                "content": toc_text,
                "embedding": embeddings[0],
                "token_count": token_count
            }).execute()
            print(f" => Thêm TOC thành công ({token_count} tokens)")
        else:
            print(" => Không tìm thấy TOC tự nhiên trong PDF.")

if __name__ == "__main__":
    asyncio.run(main())
