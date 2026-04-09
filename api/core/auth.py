"""
Auth Core: JWT + password hashing + FastAPI dependencies

Token được đọc theo thứ tự ưu tiên:
  1. httpOnly cookie "access_token" (an toàn trước XSS)
  2. Bearer header (cho API clients / mobile apps)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from core.config import settings

_bearer = HTTPBearer(auto_error=False)

# ── Cookie Config ─────────────────────────────────────────────────────────────

COOKIE_NAME = "access_token"
COOKIE_MAX_AGE = settings.jwt_expire_hours * 3600  # giây

def get_cookie_settings() -> dict:
    """Trả về kwargs cho response.set_cookie() tuỳ theo môi trường."""
    is_prod = settings.app_env == "production"
    return {
        "key": COOKIE_NAME,
        "httponly": True,           # JS không đọc được → chống XSS
        "secure": is_prod,         # True = chỉ gửi qua HTTPS (production)
        "samesite": "lax",         # chống CSRF cơ bản
        "max_age": COOKIE_MAX_AGE,
        "path": "/",               # cookie áp dụng cho tất cả routes
    }

# ── Password ──────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())

# ── JWT ───────────────────────────────────────────────────────────────────────

ALGORITHM = "HS256"


def create_jwt(user_id: str, role: str, expires_hours: int | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        hours=expires_hours or settings.jwt_expire_hours
    )
    payload = {"sub": user_id, "role": role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_jwt(token: str) -> dict:
    """Giải mã JWT. Raise HTTPException nếu không hợp lệ."""
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ hoặc đã hết hạn",
        )

# ── Token Extraction ─────────────────────────────────────────────────────────

def _extract_token(request: Request, creds: Optional[HTTPAuthorizationCredentials]) -> str | None:
    """
    Lấy JWT token theo thứ tự ưu tiên:
      1. httpOnly cookie (browser — an toàn trước XSS)
      2. Bearer header (API clients, mobile apps)
    """
    # 1. Cookie
    cookie_token = request.cookies.get(COOKIE_NAME)
    if cookie_token:
        return cookie_token
    # 2. Header
    if creds:
        return creds.credentials
    return None

# ── Dependencies ──────────────────────────────────────────────────────────────

def get_current_user(
    request: Request,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict:
    """Trả về payload JWT. Dùng cho các route yêu cầu đăng nhập."""
    token = _extract_token(request, creds)
    if not token:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    return decode_jwt(token)


def get_optional_user(
    request: Request,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict | None:
    """Trả về payload JWT hoặc None nếu chưa đăng nhập (public route)."""
    token = _extract_token(request, creds)
    if not token:
        return None
    try:
        return decode_jwt(token)
    except HTTPException:
        return None


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Chỉ cho phép role=admin."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Chỉ Admin được phép thực hiện thao tác này")
    return user
