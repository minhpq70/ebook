"""
Auth Router
- POST /auth/register       — Đăng ký tài khoản người dùng
- POST /auth/login          — Đăng nhập → set httpOnly cookie
- POST /auth/logout         — Đăng xuất → xóa cookie
- GET  /auth/me             — Thông tin tài khoản hiện tại
- POST /auth/change-password— Đổi mật khẩu (lưu vào Supabase)
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from core.auth import (
    hash_password, verify_password, create_jwt,
    get_current_user, get_cookie_settings, COOKIE_NAME,
)
from core.supabase_client import get_supabase

router = APIRouter(prefix="/auth", tags=["Auth"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str
    email: str | None = None
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


# ── Helper ────────────────────────────────────────────────────────────────────

def _make_auth_response(user: dict, token: str) -> JSONResponse:
    """Tạo response với httpOnly cookie chứa JWT token."""
    response = JSONResponse(
        content={
            "role": user["role"],
            "username": user["username"],
            "message": "Đăng nhập thành công",
        }
    )
    response.set_cookie(value=token, **get_cookie_settings())
    return response


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/register", status_code=201)
async def register(req: RegisterRequest):
    """Đăng ký tài khoản người dùng (role=user)."""
    supabase = get_supabase()

    # Kiểm tra trùng
    existing = supabase.table("app_users").select("id").eq("username", req.username).execute()
    if existing.data:
        raise HTTPException(status_code=409, detail="Username đã tồn tại")

    result = supabase.table("app_users").insert({
        "username": req.username,
        "email": req.email,
        "password_hash": hash_password(req.password),
        "role": "user",
    }).execute()

    user = result.data[0]
    token = create_jwt(user["id"], user["role"])
    return _make_auth_response(user, token)


@router.post("/login")
async def login(req: LoginRequest):
    """Đăng nhập. Set httpOnly cookie chứa JWT."""
    supabase = get_supabase()

    result = supabase.table("app_users").select("*").eq("username", req.username).execute()
    if not result.data:
        raise HTTPException(status_code=401, detail="Sai tên đăng nhập hoặc mật khẩu")

    user = result.data[0]
    if not user.get("is_active"):
        raise HTTPException(status_code=403, detail="Tài khoản đã bị vô hiệu hóa")
    if not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Sai tên đăng nhập hoặc mật khẩu")

    token = create_jwt(user["id"], user["role"])
    return _make_auth_response(user, token)


@router.post("/logout")
async def logout():
    """Đăng xuất — xóa httpOnly cookie."""
    response = JSONResponse(content={"message": "Đã đăng xuất"})
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return response


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    """Thông tin tài khoản đang đăng nhập."""
    supabase = get_supabase()
    result = supabase.table("app_users").select("id,username,email,role,created_at").eq("id", user["sub"]).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản")
    return result.data[0]


@router.post("/change-password")
async def change_password(req: ChangePasswordRequest, user: dict = Depends(get_current_user)):
    """Đổi mật khẩu. Hash mới được lưu vào Supabase."""
    supabase = get_supabase()

    result = supabase.table("app_users").select("password_hash").eq("id", user["sub"]).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản")

    if not verify_password(req.current_password, result.data[0]["password_hash"]):
        raise HTTPException(status_code=401, detail="Mật khẩu hiện tại không đúng")

    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="Mật khẩu mới phải có ít nhất 8 ký tự")

    supabase.table("app_users").update({
        "password_hash": hash_password(req.new_password),
        "updated_at": "now()",
    }).eq("id", user["sub"]).execute()

    return {"message": "Đổi mật khẩu thành công"}

