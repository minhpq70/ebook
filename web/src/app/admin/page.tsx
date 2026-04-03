'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { BookOpen, Upload, Trash2, Eye, ArrowLeft, Loader2, AlertCircle } from 'lucide-react';
import { booksAPI, Book } from '@/lib/api';

export default function AdminPage() {
  const [books, setBooks] = useState<Book[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState<string | null>(null);

  const fetchBooks = () => {
    setLoading(true);
    booksAPI.list()
      .then(d => setBooks(d.books))
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchBooks(); }, []);

  const handleDelete = async (book: Book) => {
    if (!confirm(`Xóa sách "${book.title}"? Hành động này không thể hoàn tác.`)) return;
    setDeleting(book.id);
    try {
      await booksAPI.delete(book.id);
      setBooks(prev => prev.filter(b => b.id !== book.id));
    } catch (err: any) {
      alert(err.message);
    } finally {
      setDeleting(null);
    }
  };

  const statusLabel: Record<string, string> = {
    ready: 'Sẵn sàng', processing: 'Đang xử lý', error: 'Lỗi'
  };

  const formatSize = (bytes?: number) => {
    if (!bytes) return '—';
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  };

  return (
    <div className="min-h-screen">
      <nav className="border-b border-[#2d3148] bg-[#0f1117]/80 backdrop-blur sticky top-0 z-50">
        <div className="mx-auto max-w-5xl px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/" className="btn-ghost px-3 py-2"><ArrowLeft className="w-4 h-4" /></Link>
            <BookOpen className="w-4 h-4 text-[#6c63ff]" />
            <span className="font-medium">Quản lý sách</span>
            <span className="text-sm text-[#8890a4]">({books.length} cuốn)</span>
          </div>
          <Link href="/admin/upload" className="btn-primary">
            <Upload className="w-4 h-4" /> Upload sách
          </Link>
        </div>
      </nav>

      <div className="mx-auto max-w-5xl px-6 py-8">
        {loading ? (
          <div className="flex justify-center py-20">
            <Loader2 className="w-6 h-6 animate-spin text-[#6c63ff]" />
          </div>
        ) : books.length === 0 ? (
          <div className="card text-center py-16">
            <BookOpen className="w-10 h-10 text-[#2d3148] mx-auto mb-3" />
            <p className="text-[#8890a4] mb-4">Chưa có sách nào</p>
            <Link href="/admin/upload" className="btn-primary">
              <Upload className="w-4 h-4" /> Upload sách đầu tiên
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {books.map(book => (
              <div key={book.id} className="card flex items-center gap-4">
                <div className="w-10 h-10 rounded-lg bg-[#6c63ff]/10 flex items-center justify-center shrink-0">
                  <BookOpen className="w-5 h-5 text-[#6c63ff]" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <p className="font-medium text-white truncate">{book.title}</p>
                    <span className={`badge badge-${book.status}`}>{statusLabel[book.status] || book.status}</span>
                  </div>
                  <p className="text-sm text-[#8890a4] truncate">
                    {book.author ? `${book.author} · ` : ''}{book.total_pages ? `${book.total_pages} trang · ` : ''}{formatSize(book.file_size)}
                  </p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {book.status === 'ready' && (
                    <Link href={`/reader/${book.id}`} className="btn-ghost px-3 py-2">
                      <Eye className="w-4 h-4" />
                    </Link>
                  )}
                  <button
                    onClick={() => handleDelete(book)}
                    disabled={deleting === book.id}
                    className="inline-flex items-center justify-center w-9 h-9 rounded-xl border border-red-500/20
                               text-red-400 hover:bg-red-500/10 transition-all disabled:opacity-50"
                  >
                    {deleting === book.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
