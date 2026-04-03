'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { BookOpen, Upload, Zap, Search, ChevronRight, Loader2 } from 'lucide-react';
import { booksAPI, Book } from '@/lib/api';

export default function HomePage() {
  const [books, setBooks] = useState<Book[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  useEffect(() => {
    booksAPI.list()
      .then(data => setBooks(data.books))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const readyBooks = books.filter(b => b.status === 'ready');
  const filteredBooks = search.trim()
    ? readyBooks.filter(b =>
        b.title.toLowerCase().includes(search.toLowerCase()) ||
        b.author?.toLowerCase().includes(search.toLowerCase())
      )
    : readyBooks;

  return (
    <div className="min-h-screen">
      {/* Navbar */}
      <nav className="border-b border-[#2d3148] bg-[#0f1117]/80 backdrop-blur sticky top-0 z-50">
        <div className="mx-auto max-w-6xl px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-[#6c63ff] flex items-center justify-center">
              <BookOpen className="w-4 h-4 text-white" />
            </div>
            <span className="font-semibold text-white">EbookAI</span>
            <span className="text-[10px] bg-[#6c63ff]/20 text-[#8b85ff] px-2 py-0.5 rounded-full font-mono">POC</span>
          </div>
          <Link href="/admin/upload" className="btn-primary">
            <Upload className="w-4 h-4" />
            Upload sách
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="mx-auto max-w-6xl px-6 py-20 text-center">
        <div className="inline-flex items-center gap-2 rounded-full border border-[#6c63ff]/30 bg-[#6c63ff]/10 px-4 py-1.5 text-sm text-[#8b85ff] mb-6">
          <Zap className="w-3.5 h-3.5" /> Private RAG — Nội dung không rời khỏi server
        </div>
        <h1 className="text-5xl font-bold text-white mb-4 leading-tight">
          Đọc sách thông minh<br />
          <span className="text-[#6c63ff]">cùng AI</span>
        </h1>
        <p className="text-[#8890a4] text-lg max-w-xl mx-auto mb-10">
          Hỏi đáp, giải thích, tóm tắt nội dung sách điện tử. Tất cả được xử lý riêng tư — AI chỉ nhận đoạn trích liên quan.
        </p>

        {/* Features */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-3xl mx-auto mb-16">
          {[
            { icon: '💬', label: 'Hỏi đáp nội dung' },
            { icon: '🔍', label: 'Giải thích đoạn khó' },
            { icon: '📝', label: 'Tóm tắt chương' },
            { icon: '✨', label: 'Gợi ý liên quan' },
          ].map(f => (
            <div key={f.label} className="card flex flex-col items-center gap-2 py-5">
              <span className="text-2xl">{f.icon}</span>
              <span className="text-sm text-[#8890a4] text-center">{f.label}</span>
            </div>
          ))}
        </div>
      </section>

      {/* Book Library */}
      <section className="mx-auto max-w-6xl px-6 pb-20">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-white">
            Thư viện sách
            {!loading && <span className="ml-2 text-sm text-[#8890a4] font-normal">({readyBooks.length} cuốn)</span>}
          </h2>
          <Link href="/admin" className="btn-ghost text-xs">
            Quản lý <ChevronRight className="w-3 h-3" />
          </Link>
        </div>

        {/* Search bar */}
        {!loading && readyBooks.length > 0 && (
          <div className="relative mb-6">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[#8890a4]" />
            <input
              className="input pl-11 w-full"
              placeholder="Tìm kiếm theo tên sách, tác giả..."
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-6 h-6 animate-spin text-[#6c63ff]" />
          </div>
        ) : filteredBooks.length === 0 && search ? (
          <div className="card flex flex-col items-center py-12 text-center">
            <Search className="w-10 h-10 text-[#2d3148] mb-3" />
            <p className="text-[#8890a4]">Không tìm thấy sách nào với từ khóa “{search}”</p>
            <button onClick={() => setSearch('')} className="btn-ghost mt-3 text-sm">Xóa bộ lọc</button>
          </div>
        ) : readyBooks.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {filteredBooks.map(book => (
              <BookCard key={book.id} book={book} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function BookCard({ book }: { book: Book }) {
  return (
    <Link href={`/reader/${book.id}`} className="card group cursor-pointer block">
      <div className="h-40 rounded-xl bg-gradient-to-br from-[#6c63ff]/20 to-[#2d3148] flex items-center justify-center mb-4">
        <BookOpen className="w-12 h-12 text-[#6c63ff]/60 group-hover:text-[#6c63ff] transition-colors" />
      </div>
      <h3 className="font-semibold text-white truncate mb-1">{book.title}</h3>
      {book.author && <p className="text-sm text-[#8890a4] truncate mb-3">by {book.author}</p>}
      <div className="flex items-center justify-between">
        <span className="text-xs text-[#8890a4]">
          {book.total_pages ? `${book.total_pages} trang` : 'PDF'}
        </span>
        <span className="flex items-center gap-1 text-xs text-[#6c63ff] font-medium">
          Đọc ngay <ChevronRight className="w-3 h-3" />
        </span>
      </div>
    </Link>
  );
}

function EmptyState() {
  return (
    <div className="card flex flex-col items-center py-16 text-center">
      <BookOpen className="w-12 h-12 text-[#2d3148] mb-4" />
      <p className="text-[#8890a4] mb-4">Chưa có sách nào. Hãy upload sách đầu tiên!</p>
      <Link href="/admin/upload" className="btn-primary">
        <Upload className="w-4 h-4" /> Upload sách PDF
      </Link>
    </div>
  );
}
