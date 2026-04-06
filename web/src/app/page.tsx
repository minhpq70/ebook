'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { BookOpen, Search, ChevronRight, LogIn, LogOut, User, Upload } from 'lucide-react';
import { booksAPI, Book } from '@/lib/api';
import { getUser, clearAuth, isAdmin } from '@/lib/auth';
import { useRouter } from 'next/navigation';

export default function HomePage() {
  const router = useRouter();
  const [books, setBooks] = useState<Book[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [activeCategory, setActiveCategory] = useState('');
  const [user, setUser] = useState<ReturnType<typeof getUser>>(null);

  // Đọc user từ localStorage chỉ ở client (tránh hydration mismatch)
  useEffect(() => { setUser(getUser()); }, []);

  useEffect(() => {
    booksAPI.list()
      .then(d => setBooks(d.books.filter(b => b.status === 'ready')))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handleLogout = () => { clearAuth(); router.refresh(); };

  // Lấy danh sách danh mục
  const categories = Array.from(new Set(books.map(b => b.category).filter(Boolean))) as string[];

  // Lọc sách
  const filtered = books.filter(b => {
    const matchSearch = !search.trim() ||
      b.title.toLowerCase().includes(search.toLowerCase()) ||
      b.author?.toLowerCase().includes(search.toLowerCase()) ||
      b.publisher?.toLowerCase().includes(search.toLowerCase()) ||
      b.category?.toLowerCase().includes(search.toLowerCase());
    const matchCat = !activeCategory || b.category === activeCategory;
    return matchSearch && matchCat;
  });

  // Nhóm theo danh mục (chỉ khi không search)
  const grouped: Record<string, Book[]> = {};
  if (!search.trim() && !activeCategory) {
    const withCat = books.filter(b => b.category);
    const withoutCat = books.filter(b => !b.category);
    for (const b of withCat) {
      if (!grouped[b.category!]) grouped[b.category!] = [];
      grouped[b.category!].push(b);
    }
    if (withoutCat.length) grouped['Chưa phân loại'] = withoutCat;
  }

  return (
    <div className="min-h-screen" style={{ background: '#f5f6fa', color: '#1a1a2e' }}>
      {/* Header */}
      <header style={{ background: '#1a237e', color: 'white', position: 'sticky', top: 0, zIndex: 50, boxShadow: '0 2px 8px rgba(0,0,0,0.2)' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto', padding: '0 1.5rem' }}>
          {/* Top bar */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.75rem 0', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
            <Link href="/" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', textDecoration: 'none', color: 'white' }}>
              <div style={{ width: 40, height: 40, borderRadius: '0.5rem', background: '#ff6b35', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <BookOpen style={{ width: 22, height: 22 }} />
              </div>
              <div>
                <div style={{ fontWeight: 700, fontSize: '1.1rem', lineHeight: 1.2 }}>EbookAI</div>
                <div style={{ fontSize: '0.65rem', opacity: 0.7, letterSpacing: '0.05em' }}>THƯ VIỆN SÁCH ĐIỆN TỬ</div>
              </div>
            </Link>

            {/* Search */}
            <div style={{ flex: 1, maxWidth: 480, margin: '0 2rem', position: 'relative' }}>
              <Search style={{ position: 'absolute', left: '0.875rem', top: '50%', transform: 'translateY(-50%)', width: 16, height: 16, color: '#999' }} />
              <input
                value={search}
                onChange={e => { setSearch(e.target.value); setActiveCategory(''); }}
                placeholder="Tìm kiếm theo tên sách, tác giả, NXB..."
                style={{ width: '100%', padding: '0.625rem 1rem 0.625rem 2.5rem', borderRadius: '2rem', border: 'none', background: 'white', color: '#1a1a2e', fontSize: '0.875rem', outline: 'none', boxSizing: 'border-box' }}
              />
            </div>

            {/* Auth */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              {user ? (
                <>
                  {isAdmin() && (
                    <Link href="/admin" style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', color: '#ffcc02', textDecoration: 'none', fontSize: '0.875rem', fontWeight: 500 }}>
                      <Upload style={{ width: 14, height: 14 }} /> Quản trị
                    </Link>
                  )}
                  <span style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', fontSize: '0.875rem', opacity: 0.9 }}>
                    <User style={{ width: 14, height: 14 }} /> {user.username}
                  </span>
                  <button onClick={handleLogout} style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', background: 'rgba(255,255,255,0.15)', border: 'none', borderRadius: '0.5rem', padding: '0.375rem 0.75rem', color: 'white', cursor: 'pointer', fontSize: '0.8rem' }}>
                    <LogOut style={{ width: 13, height: 13 }} /> Đăng xuất
                  </button>
                </>
              ) : (
                <Link href="/login" style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', background: '#ff6b35', borderRadius: '0.5rem', padding: '0.5rem 1rem', color: 'white', textDecoration: 'none', fontSize: '0.875rem', fontWeight: 500 }}>
                  <LogIn style={{ width: 14, height: 14 }} /> Đăng nhập
                </Link>
              )}
            </div>
          </div>

          {/* Category nav */}
          {categories.length > 0 && (
            <div style={{ display: 'flex', gap: '0.25rem', padding: '0.5rem 0', overflowX: 'auto' }}>
              <button
                onClick={() => setActiveCategory('')}
                style={{ whiteSpace: 'nowrap', padding: '0.375rem 0.875rem', borderRadius: '2rem', border: 'none', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 500,
                  background: activeCategory === '' ? '#ff6b35' : 'rgba(255,255,255,0.12)',
                  color: 'white' }}
              >
                Tất cả
              </button>
              {categories.map(cat => (
                <button key={cat}
                  onClick={() => { setActiveCategory(cat); setSearch(''); }}
                  style={{ whiteSpace: 'nowrap', padding: '0.375rem 0.875rem', borderRadius: '2rem', border: 'none', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 500,
                    background: activeCategory === cat ? '#ff6b35' : 'rgba(255,255,255,0.12)',
                    color: 'white' }}
                >
                  {cat}
                </button>
              ))}
            </div>
          )}
        </div>
      </header>

      {/* Main content */}
      <main style={{ maxWidth: 1200, margin: '0 auto', padding: '2rem 1.5rem' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: '5rem', color: '#999' }}>Đang tải...</div>
        ) : books.length === 0 ? (
          <EmptyState />
        ) : search || activeCategory ? (
          /* Search/filter result */
          <section>
            <h2 style={{ fontSize: '1.125rem', fontWeight: 600, color: '#1a1a2e', marginBottom: '1.25rem' }}>
              {filtered.length > 0 ? `Kết quả tìm kiếm (${filtered.length} cuốn)` : 'Không tìm thấy kết quả'}
            </h2>
            <BookGrid books={filtered} />
          </section>
        ) : (
          /* Grouped by category */
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2.5rem' }}>
            {Object.entries(grouped).map(([cat, catBooks]) => (
              <section key={cat}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <div style={{ width: 4, height: 24, borderRadius: 2, background: '#1a237e' }} />
                    <h2 style={{ fontSize: '1.125rem', fontWeight: 700, color: '#1a1a2e', margin: 0 }}>{cat}</h2>
                    <span style={{ fontSize: '0.8rem', color: '#999' }}>({catBooks.length} cuốn)</span>
                  </div>
                  <button
                    onClick={() => setActiveCategory(cat === 'Chưa phân loại' ? '' : cat)}
                    style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.8rem', color: '#1a237e', background: 'none', border: 'none', cursor: 'pointer', fontWeight: 500 }}
                  >
                    Xem tất cả <ChevronRight style={{ width: 14, height: 14 }} />
                  </button>
                </div>
                <div style={{ display: 'flex', gap: '1rem', overflowX: 'auto', paddingBottom: '0.5rem' }}>
                  {catBooks.slice(0, 6).map(book => <BookCard key={book.id} book={book} horizontal />)}
                </div>
              </section>
            ))}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer style={{ background: '#1a237e', color: 'rgba(255,255,255,0.7)', textAlign: 'center', padding: '1.5rem', fontSize: '0.8rem', marginTop: '3rem' }}>
        © 2026 EbookAI — Nền tảng sách điện tử thông minh
      </footer>
    </div>
  );
}

function BookGrid({ books }: { books: Book[] }) {
  if (books.length === 0) return <p style={{ color: '#999' }}>Không có sách nào.</p>;
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: '1.25rem' }}>
      {books.map(book => <BookCard key={book.id} book={book} />)}
    </div>
  );
}

function BookCard({ book, horizontal }: { book: Book; horizontal?: boolean }) {
  const coverBg = `hsl(${Math.abs(book.id.charCodeAt(0) * 37) % 360}, 55%, 35%)`;
  const style = horizontal ? {
    flexShrink: 0, width: 150, textDecoration: 'none', color: 'inherit',
  } : { textDecoration: 'none', color: 'inherit' };

  return (
    <Link href={`/books/${book.id}`} style={style}>
      <div style={{ background: 'white', borderRadius: '0.75rem', overflow: 'hidden', boxShadow: '0 2px 8px rgba(0,0,0,0.08)', transition: 'transform 0.2s, box-shadow 0.2s', cursor: 'pointer' }}
        onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.transform = 'translateY(-3px)'; (e.currentTarget as HTMLDivElement).style.boxShadow = '0 8px 24px rgba(0,0,0,0.12)'; }}
        onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.transform = ''; (e.currentTarget as HTMLDivElement).style.boxShadow = '0 2px 8px rgba(0,0,0,0.08)'; }}
      >
        {/* Cover */}
        <div style={{ height: 200, background: book.cover_url ? undefined : coverBg, display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative' }}>
          {book.cover_url
            ? <img src={book.cover_url} alt={book.title} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
            : <BookOpen style={{ width: 48, height: 48, color: 'rgba(255,255,255,0.5)' }} />
          }
          {book.category && (
            <span style={{ position: 'absolute', top: '0.5rem', left: '0.5rem', background: 'rgba(0,0,0,0.6)', color: 'white', fontSize: '0.65rem', padding: '0.2rem 0.5rem', borderRadius: '2rem' }}>
              {book.category}
            </span>
          )}
        </div>
        {/* Info */}
        <div style={{ padding: '0.75rem' }}>
          <p style={{ fontWeight: 600, fontSize: '0.875rem', color: '#1a1a2e', margin: '0 0 0.25rem', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden', lineHeight: 1.4 }} title={book.title}>
            {book.title}
          </p>
          {book.author && <p style={{ fontSize: '0.75rem', color: '#666', margin: '0 0 0.25rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{book.author}</p>}
          {book.publisher && <p style={{ fontSize: '0.7rem', color: '#1a237e', margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{book.publisher}{book.published_year ? ` · ${book.published_year}` : ''}</p>}
        </div>
      </div>
    </Link>
  );
}

function EmptyState() {
  return (
    <div style={{ textAlign: 'center', padding: '5rem 2rem', color: '#999' }}>
      <BookOpen style={{ width: 64, height: 64, margin: '0 auto 1rem', opacity: 0.3 }} />
      <p style={{ fontSize: '1.125rem', marginBottom: '0.5rem' }}>Chưa có sách nào trong thư viện</p>
    </div>
  );
}
