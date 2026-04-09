'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { BookOpen, Search, ChevronRight, LogIn, LogOut, User, Upload } from 'lucide-react';
import { booksAPI, Book, categoriesAPI } from '@/lib/api';
import { getUser, isAdmin, authAPI } from '@/lib/auth';
import { useRouter } from 'next/navigation';

export default function HomePage() {
  const router = useRouter();
  const [books, setBooks] = useState<Book[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [activeCategory, setActiveCategory] = useState('');
  const [dbCategories, setDbCategories] = useState<{ id: string; name: string; sort_order: number }[]>([]);
  const [user, setUser] = useState<ReturnType<typeof getUser>>(null);

  // Đọc user từ localStorage chỉ ở client (tránh hydration mismatch)
  useEffect(() => { setUser(getUser()); }, []);

  useEffect(() => {
    Promise.all([booksAPI.list(), categoriesAPI.list()])
      .then(([bData, cData]) => {
        setBooks(bData.books.filter(b => b.status === 'ready'));
        setDbCategories(cData);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handleLogout = async () => { await authAPI.logout(); router.refresh(); };

  // Lấy danh sách danh mục để làm Tabs (Chỉ lấy Name)
  const categoryNames = dbCategories.map(c => c.name);

  // Lọc sách
  const filtered = books.filter(b => {
    const matchSearch = !search.trim() ||
      b.title.toLowerCase().includes(search.toLowerCase()) ||
      b.author?.toLowerCase().includes(search.toLowerCase()) ||
      b.publisher?.toLowerCase().includes(search.toLowerCase()) ||
      b.category?.toLowerCase().includes(search.toLowerCase());
    const matchCat = !activeCategory || (b.category || '').trim().toLowerCase() === activeCategory.trim().toLowerCase();
    return matchSearch && matchCat;
  });

  // Nhóm theo DB Categories — so khớp mềm dẻo (trim + lowercase)
  const grouped: Record<string, Book[]> = {};
  if (!search.trim() && !activeCategory) {
    const unclassified: Book[] = [];
    // Khởi tạo các nhóm rỗng để danh mục không có sách vẫn hiện
    for (const cat of dbCategories) {
      grouped[cat.name] = [];
    }

    // Tạo map nhanh: tên danh mục (lowercase, trim) → tên gốc trong DB
    const catLookup: Record<string, string> = {};
    for (const cat of dbCategories) {
      catLookup[cat.name.trim().toLowerCase()] = cat.name;
    }

    for (const b of books) {
      const bookCatKey = (b.category || '').trim().toLowerCase();
      const matchedCatName = catLookup[bookCatKey];
      if (bookCatKey && matchedCatName) {
        grouped[matchedCatName].push(b);
      } else {
        unclassified.push(b);
      }
    }
    if (unclassified.length > 0) {
      grouped['Chưa phân loại'] = unclassified;
    }
  }

  return (
    <div className="min-h-screen bg-[#f5f6fa] text-[#1a1a2e]">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-[#1a237e] text-white shadow-[0_2px_8px_rgba(0,0,0,0.2)]">
        <div className="max-w-[1200px] mx-auto px-6">
          {/* Top bar */}
          <div className="flex items-center justify-between py-3 border-b border-white/10">
            <Link href="/" className="flex items-center gap-3 no-underline text-white">
              <div className="w-10 h-10 rounded-lg bg-[#ff6b35] flex items-center justify-center">
                <BookOpen className="w-5 h-5" />
              </div>
              <div>
                <div className="font-bold text-[1.1rem] leading-[1.2]">EbookAI</div>
                <div className="text-[0.65rem] opacity-70 tracking-wider">THƯ VIỆN SÁCH ĐIỆN TỬ</div>
              </div>
            </Link>

            {/* Search */}
            <div className="flex-1 max-w-[480px] mx-8 relative">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[#999]" />
              <input
                value={search}
                onChange={e => { setSearch(e.target.value); setActiveCategory(''); }}
                placeholder="Tìm kiếm theo tên sách, tác giả, NXB..."
                className="w-full py-2.5 px-4 pl-10 rounded-full border-none bg-white text-[#1a1a2e] text-sm outline-none"
              />
            </div>

            {/* Auth */}
            <div className="flex items-center gap-3">
              {user ? (
                <>
                  {isAdmin() && (
                    <Link href="/admin" className="flex items-center gap-1.5 text-[#ffcc02] no-underline text-sm font-medium">
                      <Upload className="w-3.5 h-3.5" /> Quản trị
                    </Link>
                  )}
                  <span className="flex items-center gap-1.5 text-sm opacity-90">
                    <User className="w-3.5 h-3.5" /> {user.username}
                  </span>
                  <button onClick={handleLogout} className="flex items-center gap-1.5 bg-white/15 border-none rounded-lg py-1.5 px-3 text-white cursor-pointer text-[0.8rem]">
                    <LogOut className="w-3.5 h-3.5" /> Đăng xuất
                  </button>
                </>
              ) : (
                <Link href="/login" className="flex items-center gap-1.5 bg-[#ff6b35] rounded-lg py-2 px-4 text-white no-underline text-sm font-medium">
                  <LogIn className="w-3.5 h-3.5" /> Đăng nhập
                </Link>
              )}
            </div>
          </div>

          {/* Category nav */}
          {categoryNames.length > 0 && (
            <div className="flex gap-1 py-2 overflow-x-auto">
              <button
                onClick={() => setActiveCategory('')}
                className={`whitespace-nowrap py-1.5 px-3.5 rounded-full border-none cursor-pointer text-[0.8rem] font-medium text-white ${activeCategory === '' ? 'bg-[#ff6b35]' : 'bg-white/10'}`}
              >
                Tất cả
              </button>
              {categoryNames.map(cat => (
                <button key={cat}
                  onClick={() => { setActiveCategory(cat); setSearch(''); }}
                  className={`whitespace-nowrap py-1.5 px-3.5 rounded-full border-none cursor-pointer text-[0.8rem] font-medium text-white ${activeCategory === cat ? 'bg-[#ff6b35]' : 'bg-white/10'}`}
                >
                  {cat}
                </button>
              ))}
            </div>
          )}
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-[1200px] mx-auto py-8 px-6">
        {loading ? (
          <div className="text-center py-20 text-[#999]">Đang tải...</div>
        ) : books.length === 0 ? (
          <EmptyState />
        ) : search || activeCategory ? (
          /* Search/filter result */
          <section>
            <h2 className="text-lg font-semibold text-[#1a1a2e] mb-5">
              {filtered.length > 0 ? `Kết quả tìm kiếm (${filtered.length} cuốn)` : 'Không tìm thấy kết quả'}
            </h2>
            <BookGrid books={filtered} />
          </section>
        ) : (
          /* Grouped by category */
          <div className="flex flex-col gap-10">
            {Object.entries(grouped).map(([cat, catBooks]) => (
              <section key={cat}>
                <div className="flex items-center justify-between mb-5">
                  <div className="flex items-center gap-3">
                    <div className="w-1 h-6 rounded-[2px] bg-[#1a237e]" />
                    <h2 className="text-lg font-bold text-[#1a1a2e] m-0">{cat}</h2>
                    <span className="text-sm text-[#999]">({catBooks.length} cuốn)</span>
                  </div>
                  <button
                    onClick={() => setActiveCategory(cat === 'Chưa phân loại' ? '' : cat)}
                    className="flex items-center gap-1 text-[0.8rem] text-[#1a237e] bg-none border-none cursor-pointer font-medium"
                  >
                    Xem tất cả <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                </div>
                {catBooks.length > 0 ? (
                  <div className="flex gap-4 overflow-x-auto pb-2">
                    {catBooks.slice(0, 6).map(book => <BookCard key={book.id} book={book} horizontal />)}
                  </div>
                ) : (
                  <div className="p-8 text-center bg-white rounded-xl text-[#999] text-sm">
                    Chưa có sách nào trong danh mục này
                  </div>
                )}
              </section>
            ))}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="bg-[#1a237e] text-white/70 text-center p-6 text-sm mt-12">
        © 2026 EbookAI — Nền tảng sách điện tử thông minh
      </footer>
    </div>
  );
}

function BookGrid({ books }: { books: Book[] }) {
  if (books.length === 0) return <p className="text-[#999]">Không có sách nào.</p>;
  return (
    <div className="grid grid-cols-[repeat(auto-fill,minmax(160px,1fr))] gap-5">
      {books.map(book => <BookCard key={book.id} book={book} />)}
    </div>
  );
}

function BookCard({ book, horizontal }: { book: Book; horizontal?: boolean }) {
  const coverBg = `hsl(${Math.abs(book.id.charCodeAt(0) * 37) % 360}, 55%, 35%)`;
  
  return (
    <Link href={`/books/${book.id}`} className={`no-underline text-inherit ${horizontal ? 'shrink-0 w-[150px]' : ''}`}>
      <div 
        className="bg-white rounded-xl overflow-hidden shadow-[0_2px_8px_rgba(0,0,0,0.08)] transition-all duration-200 cursor-pointer hover:-translate-y-[3px] hover:shadow-[0_8px_24px_rgba(0,0,0,0.12)]"
      >
        {/* Cover */}
        <div 
          className="h-[200px] flex items-center justify-center relative"
          style={{ background: book.cover_url ? undefined : coverBg }}
        >
          {book.cover_url
            ? <img src={book.cover_url} alt={book.title} className="w-full h-full object-cover" />
            : <BookOpen className="w-12 h-12 text-white/50" />
          }
          {book.category && (
            <span className="absolute top-2 left-2 bg-black/60 text-white text-[0.65rem] py-0.5 px-2 rounded-full">
              {book.category}
            </span>
          )}
        </div>
        {/* Info */}
        <div className="p-3">
          <p className="font-semibold text-sm text-[#1a1a2e] mb-1 line-clamp-2 leading-relaxed" title={book.title}>
            {book.title}
          </p>
          {book.author && <p className="text-xs text-[#666] mb-1 truncate">{book.author}</p>}
          {book.publisher && <p className="text-[0.7rem] text-[#1a237e] m-0 truncate">{book.publisher}{book.published_year ? ` · ${book.published_year}` : ''}</p>}
        </div>
      </div>
    </Link>
  );
}

function EmptyState() {
  return (
    <div className="text-center py-20 px-8 text-[#999]">
      <BookOpen className="w-16 h-16 mx-auto mb-4 opacity-30" />
      <p className="text-lg mb-2">Chưa có sách nào trong thư viện</p>
    </div>
  );
}
