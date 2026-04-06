"""
Auth Core: JWT + password hashing + FastAPI dependencies
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from core.config import settings

_bearer = HTTPBearer(auto_error=False)

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

# ── Dependencies ──────────────────────────────────────────────────────────────

def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict:
    """Trả về payload JWT. Dùng cho các route yêu cầu đăng nhập."""
    if not creds:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    return decode_jwt(creds.credentials)


def get_optional_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict | None:
    """Trả về payload JWT hoặc None nếu chưa đăng nhập (public route)."""
    if not creds:
        return None
    try:
        return decode_jwt(creds.credentials)
    except HTTPException:
        return None


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Chỉ cho phép role=admin."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Chỉ Admin được phép thực hiện thao tác này")
    return user
