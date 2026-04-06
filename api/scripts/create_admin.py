"""
Script tạo tài khoản Admin đầu tiên.
Chạy 1 lần: python scripts/create_admin.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.supabase_client import get_supabase
from core.auth import hash_password


def main():
    print("=== Tạo tài khoản Admin ===")
    username = input("Username: ").strip()
    if not username:
        print("Username không được để trống!")
        return

    import getpass
    password = getpass.getpass("Password (ít nhất 8 ký tự): ")
    if len(password) < 8:
        print("Mật khẩu phải có ít nhất 8 ký tự!")
        return

    email = input("Email (tùy chọn, Enter để bỏ qua): ").strip() or None

    supabase = get_supabase()

    # Kiểm tra trùng
    existing = supabase.table("app_users").select("id").eq("username", username).execute()
    if existing.data:
        print(f"Username '{username}' đã tồn tại!")
        return

    result = supabase.table("app_users").insert({
        "username": username,
        "email": email,
        "password_hash": hash_password(password),
        "role": "admin",
    }).execute()

    admin = result.data[0]
    print(f"\n✅ Tạo Admin thành công!")
    print(f"   ID      : {admin['id']}")
    print(f"   Username: {admin['username']}")
    print(f"   Role    : {admin['role']}")
    print(f"\nBây giờ bạn có thể đăng nhập tại /login")


if __name__ == "__main__":
    main()
