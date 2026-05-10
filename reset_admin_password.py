import os
import bcrypt
import psycopg2
from dotenv import load_dotenv

def reset_password():
    print("=== CÔNG CỤ KHÔI PHỤC MẬT KHẨU ADMIN ===")
    new_pass = input("Nhập mật khẩu mới cho tài khoản Admin: ")
    if len(new_pass) < 6:
        print("Lỗi: Mật khẩu phải có ít nhất 6 ký tự.")
        return

    # Mã hóa mật khẩu
    hashed = bcrypt.hashpw(new_pass.encode(), bcrypt.gensalt()).decode()

    try:
        # Kết nối CSDL
        conn = psycopg2.connect(
            dbname="postgres",
            user="postgres.your-tenant-id",
            password="your-super-secret-and-long-postgres-password",
            host="127.0.0.1",
            port=5432
        )
        cursor = conn.cursor()
        
        # Cập nhật mật khẩu cho user có role = admin
        cursor.execute("UPDATE app_users SET password_hash = %s WHERE role = %s", (hashed, "admin"))
        conn.commit()
        
        print("\n✅ Thành công! Mật khẩu Admin đã được đổi thành công.")
        print(f"Bạn có thể đăng nhập lại bằng mật khẩu mới: {new_pass}")
        
    except Exception as e:
        print(f"\n❌ Lỗi kết nối CSDL: {e}")

if __name__ == "__main__":
    reset_password()
