"""
Categories Router
- GET /api/v1/categories - Lấy danh sách danh mục
- POST /api/v1/categories - Tạo danh mục mới
- DELETE /api/v1/categories/{id} - Xóa danh mục
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List

from core.auth import require_admin
from core.supabase_client import get_supabase

router = APIRouter(prefix="/categories", tags=["Categories"])

class Category(BaseModel):
    id: str
    name: str
    sort_order: int
    created_at: str

class CategoryCreate(BaseModel):
    name: str
    sort_order: int = 0

@router.get("", response_model=List[Category])
def get_categories():
    """Lấy danh sách categories, sắp xếp theo sort_order và tên."""
    supabase = get_supabase()
    res = supabase.table("categories").select("*").order("sort_order", desc=False).order("name", desc=False).execute()
    return res.data

@router.post("", response_model=Category)
def create_category(req: CategoryCreate, _: dict = Depends(require_admin)):
    """Tạo mới danh mục (Yêu cầu Admin)."""
    supabase = get_supabase()
    # Kiểm tra trùng lập
    existing = supabase.table("categories").select("*").eq("name", req.name.strip()).execute()
    if existing.data:
        raise HTTPException(status_code=400, detail="Danh mục đã tồn tại")
        
    data = {"name": req.name.strip(), "sort_order": req.sort_order}
    res = supabase.table("categories").insert(data).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Chưa thể tạo danh mục")
    return res.data[0]

@router.delete("/{category_id}")
def delete_category(category_id: str, _: dict = Depends(require_admin)):
    """Xóa danh mục (Yêu cầu Admin). Sách đã gán danh mục này vẫn giữ nguyên text list."""
    supabase = get_supabase()
    res = supabase.table("categories").delete().eq("id", category_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Không tìm thấy danh mục")
    return {"message": "Xóa thành công", "deleted": res.data[0]}
