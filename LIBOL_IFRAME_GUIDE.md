# Hướng Dẫn Tích Hợp Iframe AI Ebook Platform Lên Libol (.NET)

Tài liệu này cung cấp hướng dẫn dành cho đội ngũ phát triển .NET của Libol để nhúng khung Chat AI vào trang đọc sách/chi tiết sách một cách bảo mật.

Quy trình nhúng gồm 2 bước: **Tạo Token bảo mật ở Backend (C#)** và **Hiển thị Iframe ở Frontend (Razor/HTML)**.

---

## Bước 1: Tạo Token Bảo mật bằng C# (Backend Libol)

Chúng ta không thể nhúng link Iframe trần trụi (ví dụ: `?book_ref=105`) vì độc giả có thể copy link đó mang ra ngoài xài API chùa.
Libol cần dùng chung một "chìa khóa bí mật" (Shared Secret) đã được thống nhất với AI Ebook Platform để ký ra một mã Token có thời hạn (JWT).

**Code mẫu C# (Sử dụng thư viện `System.IdentityModel.Tokens.Jwt`):**

```csharp
using System;
using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using Microsoft.IdentityModel.Tokens;
using System.Text;

public class AiChatHelper
{
    // Đây là chuỗi bảo mật khớp với biến cấu hình bên phần mềm AI
    private const string SharedSecret = "your-super-secret-jwt-token-with-at-least-32-characters-long"; 

    public static string GenerateEmbedToken(string bookId)
    {
        var securityKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(SharedSecret));
        var credentials = new SigningCredentials(securityKey, SecurityAlgorithms.HmacSha256);

        // Gắn thông tin cuốn sách vào token để AI xác thực chéo
        var claims = new[] {
            new Claim("book_ref", bookId),
            new Claim("source", "Libol")
        };

        var token = new JwtSecurityToken(
            issuer: "LibolSystem",
            audience: "AiEbookPlatform",
            claims: claims,
            expires: DateTime.UtcNow.AddHours(2), // Token này chỉ sống 2 tiếng, sau đó Iframe sẽ bị từ chối
            signingCredentials: credentials);

        return new JwtSecurityTokenHandler().WriteToken(token);
    }
}
```

---

## Bước 2: Chèn Iframe vào giao diện đọc sách của Libol (Frontend)

Trên trang **Chi tiết cuốn sách** hoặc **Trang đọc sách** của Libol (thường là file `.cshtml` hoặc `.aspx`), lập trình viên gọi hàm C# trên để sinh Token, sau đó gắn vào thẻ `<iframe>`.

**Code mẫu trên View (ASP.NET Razor):**

```html
@{
    // Giả sử Model.BookID là ID cuốn sách hiện tại trên Libol (VD: "105")
    string currentBookId = Model.BookID.ToString(); 
    string chatToken = AiChatHelper.GenerateEmbedToken(currentBookId);
    
    // Tên miền gốc của giao diện AI Ebook Platform
    string aiFrontendUrl = "http://localhost:3000"; 
}

<!-- Vùng hiển thị khung Chat AI -->
<div class="libol-ai-assistant">
    <div class="ai-header">
        <h4>💬 Trợ lý AI (Hỏi đáp về cuốn sách này)</h4>
    </div>
    
    <!-- Thẻ Iframe -->
    <iframe 
        src="@aiFrontendUrl/chat/embed?book_ref=@currentBookId&token=@chatToken" 
        width="100%" 
        height="600px" 
        frameborder="0"
        allow="clipboard-write"
        style="border-radius: 8px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
    </iframe>
</div>
```

---

## 💡 Giải thích Luồng Xử lý & Bảo mật
1. Khi độc giả mở sách `ID 105` trên Libol, Libol tự động tạo một đoạn mã `chatToken`.
2. Trình duyệt tải Iframe gọi sang Máy chủ AI kèm theo `token` đó.
3. Máy chủ AI giải mã token:
   - Nếu Token hết hạn (> 2 tiếng) 👉 AI chặn lại, hiển thị "Phiên làm việc đã hết hạn".
   - Nếu `book_ref` trong Token bị chỉnh sửa khác với URL 👉 AI chặn lại (chống giả mạo).
   - Nếu mọi thứ hợp lệ, AI load đúng cuốn sách có `external_id = 105` để cho phép user hỏi đáp.
