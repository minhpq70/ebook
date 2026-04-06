"""
Auth Router
- POST /auth/register       — Đăng ký tài khoản người dùng
- POST /auth/login          — Đăng nhập (admin hoặc user)
- GET  /auth/me             — Thông tin tài khoản hiện tại
- POST /auth/change-password— Đổi mật khẩu (lưu vào Supabase)
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from core.auth import hash_password, verify_password, create_jwt, get_current_user
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

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=201)
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
    return TokenResponse(access_token=token, role=user["role"], username=user["username"])


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    """Đăng nhập. Trả về JWT chứa user_id và role."""
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
    return TokenResponse(access_token=token, role=user["role"], username=user["username"])


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
