import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'EbookAI — Nền tảng đọc sách thông minh',
  description: 'Đọc sách điện tử, hỏi đáp, tóm tắt và giải thích nội dung bằng AI',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi">
      <body className="min-h-screen bg-[#0f1117]">{children}</body>
    </html>
  );
}
