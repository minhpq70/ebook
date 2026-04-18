'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { BookOpen, Upload, Trash2, Eye, ArrowLeft, Loader2, Settings, FileText, Edit2, Check, X, LogOut } from 'lucide-react';
import { booksAPI, Book, categoriesAPI } from '@/lib/api';
import { adminAPI, authAPI, getUser } from '@/lib/auth';
import { useRouter } from 'next/navigation';

type Tab = 'books' | 'logs' | 'config';

interface LogEntry { timestamp: string; mode?: string; book?: string; type?: string; tokens?: string; cost?: string; q?: string; }
interface AIConfig { current: { provider: string; chat_model: string; embedding_provider: string; embedding_model: string }; providers: Record<string, any>; embedding_providers: Record<string, any>; available: Record<string, boolean>; }

export default function AdminPage() {
  const router = useRouter();
  const [user, setUser] = useState<ReturnType<typeof getUser>>(null);
  const [tab, setTab] = useState<Tab>('books');

  useEffect(() => { setUser(getUser()); }, []);

  // Books
  const [books, setBooks] = useState<Book[]>([]);
  const [booksLoading, setBooksLoading] = useState(true);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [editBook, setEditBook] = useState<string | null>(null);
  const [editData, setEditData] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [categories, setCategories] = useState<{ id: string; name: string }[]>([]);

  // Logs
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);

  // Config
  const [config, setConfig] = useState<AIConfig | null>(null);
  const [configLoading, setConfigLoading] = useState(false);
  const [editConfig, setEditConfig] = useState(false);
  const [newProvider, setNewProvider] = useState('');
  const [newChatModel, setNewChatModel] = useState('');
  const [newEmbedProvider, setNewEmbedProvider] = useState('');
  const [newEmbedModel, setNewEmbedModel] = useState('');
  const [configSaving, setConfigSaving] = useState(false);
  const [configMsg, setConfigMsg] = useState('');

  const fetchBooks = () => {
    setBooksLoading(true);
    booksAPI.list().then(d => setBooks(d.books)).catch(console.error).finally(() => setBooksLoading(false));
  };

  const fetchLogs = () => {
    setLogsLoading(true);
    adminAPI.getLogs(100).then(d => setLogs(d.logs || [])).catch(console.error).finally(() => setLogsLoading(false));
  };

  const fetchConfig = () => {
    setConfigLoading(true);
    adminAPI.getConfig().then(d => { setConfig(d); setNewProvider(d.current.provider); setNewChatModel(d.current.chat_model); setNewEmbedProvider(d.current.embedding_provider || 'openai'); setNewEmbedModel(d.current.embedding_model); }).catch(console.error).finally(() => setConfigLoading(false));
  };

  useEffect(() => { fetchBooks(); categoriesAPI.list().then(setCategories).catch(console.error); }, []);
  useEffect(() => { if (tab === 'logs') fetchLogs(); if (tab === 'config') fetchConfig(); }, [tab]);

  const handleDelete = async (book: Book) => {
    if (!confirm(`Xóa sách "${book.title}"?`)) return;
    setDeleting(book.id);
    try { await booksAPI.delete(book.id); setBooks(p => p.filter(b => b.id !== book.id)); } catch (e: any) { alert(e.message); } finally { setDeleting(null); }
  };

  const startEdit = (book: Book) => {
    setEditBook(book.id);
    setEditData({ title: book.title || '', author: book.author || '', publisher: book.publisher || '', published_year: book.published_year || '', category: book.category || '', page_size: book.page_size || '', description: book.description || '' });
  };

  const saveEdit = async (bookId: string) => {
    setSaving(true);
    try {
      if (editData.category) {
        const catName = editData.category.trim();
        const exists = categories.find(c => c.name.toLowerCase() === catName.toLowerCase());
        if (!exists) {
          try {
            await categoriesAPI.create({ name: catName, sort_order: categories.length + 1 });
            setCategories(p => [...p, { id: 'new', name: catName }]);
          } catch (e) {
            console.warn('Cannot auto-create category', e);
          }
        }
      }

      await adminAPI.updateBook(bookId, editData);
      setBooks(p => p.map(b => b.id === bookId ? { ...b, ...editData } : b));
      setEditBook(null);
    } catch (e: any) { alert(e.message); } finally { setSaving(false); }
  };

  const saveConfig = async () => {
    setConfigSaving(true); setConfigMsg('');
    try {
      await adminAPI.updateConfig({ provider: newProvider, chat_model: newChatModel, embedding_provider: newEmbedProvider, embedding_model: newEmbedModel });
      setConfigMsg('✅ Cập nhật thành công!'); setEditConfig(false); fetchConfig();
    } catch (e: any) { setConfigMsg('❌ ' + e.message); } finally { setConfigSaving(false); }
  };

  const statusLabel: Record<string, string> = { ready: 'Sẵn sàng', processing: 'Đang xử lý', error: 'Lỗi' };
  const formatSize = (b?: number) => !b ? '—' : b < 1024 * 1024 ? `${(b / 1024).toFixed(0)} KB` : `${(b / 1024 / 1024).toFixed(1)} MB`;

  const tabs: { key: Tab; label: string; icon: any }[] = [
    { key: 'books', label: 'Quản lý sách', icon: BookOpen },
    { key: 'logs', label: 'Log câu hỏi', icon: FileText },
    { key: 'config', label: 'Cấu hình AI', icon: Settings },
  ];

  return (
    <div className="min-h-screen">
      <nav className="border-b border-[#2d3148] bg-[#0f1117]/80 backdrop-blur sticky top-0 z-50">
        <div className="mx-auto max-w-6xl px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/" className="btn-ghost px-3 py-2"><ArrowLeft className="w-4 h-4" /></Link>
            <BookOpen className="w-4 h-4 text-[#6c63ff]" />
            <span className="font-medium">Admin Dashboard</span>
            <span className="text-sm text-[#8890a4]">— {user?.username}</span>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/admin/categories" className="btn-ghost px-3 py-2 text-sm">🗂 Quản lý Danh mục</Link>
            <Link href="/admin/upload" className="btn-primary"><Upload className="w-4 h-4" /> Upload sách</Link>
            <button onClick={async () => { await authAPI.logout(); router.replace('/login'); }} className="btn-ghost px-3 py-2" title="Đăng xuất">
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
        {/* Tabs */}
        <div className="mx-auto max-w-6xl px-6 flex gap-1 pb-0">
          {tabs.map(t => (
            <button key={t.key} onClick={() => setTab(t.key)}
              className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${tab === t.key ? 'border-[#6c63ff] text-[#6c63ff]' : 'border-transparent text-[#8890a4] hover:text-white'}`}
            >
              <t.icon className="w-3.5 h-3.5" /> {t.label}
            </button>
          ))}
        </div>
      </nav>

      <div className="mx-auto max-w-6xl px-6 py-8">

        {/* ── TAB: BOOKS ── */}
        {tab === 'books' && (
          booksLoading ? <div className="flex justify-center py-20"><Loader2 className="w-6 h-6 animate-spin text-[#6c63ff]" /></div>
            : books.length === 0 ? (
              <div className="card text-center py-16">
                <BookOpen className="w-10 h-10 text-[#2d3148] mx-auto mb-3" />
                <p className="text-[#8890a4] mb-4">Chưa có sách nào</p>
                <Link href="/admin/upload" className="btn-primary"><Upload className="w-4 h-4" /> Upload sách đầu tiên</Link>
              </div>
            ) : (
              <div className="space-y-3">
                {books.map(book => (
                  <div key={book.id} className="card">
                    {editBook === book.id ? (
                      /* Edit mode */
                      <div className="space-y-3">
                        <div className="grid grid-cols-2 gap-3">
                          {[
                            { f: 'title', label: 'Tiêu đề' },
                            { f: 'author', label: 'Tác giả' },
                            { f: 'publisher', label: 'Nhà xuất bản' },
                            { f: 'published_year', label: 'Năm xuất bản' },
                            { f: 'category', label: 'Danh mục' },
                            { f: 'page_size', label: 'Khổ cỡ' }
                          ].map(({ f, label }) => (
                            <div key={f}>
                              <label className="text-xs text-[#8890a4] mb-1 block">{label}</label>
                              <input
                                className="input"
                                list={f === 'category' ? 'admin-category-list' : undefined}
                                value={editData[f] || ''}
                                onChange={e => setEditData(p => ({ ...p, [f]: e.target.value }))}
                              />
                            </div>
                          ))}
                        </div>
                        <datalist id="admin-category-list">
                          {categories.map(c => <option key={c.name} value={c.name} />)}
                        </datalist>
                        <div>
                          <label className="text-xs text-[#8890a4] mb-1 block">Mô tả</label>
                          <textarea className="input resize-none" rows={2} value={editData.description || ''} onChange={e => setEditData(p => ({ ...p, description: e.target.value }))} />
                        </div>
                        <div className="flex gap-2 justify-end">
                          <button onClick={() => setEditBook(null)} className="btn-ghost px-3 py-1.5 text-sm"><X className="w-4 h-4" /> Hủy</button>
                          <button onClick={() => saveEdit(book.id)} disabled={saving} className="btn-primary py-1.5 text-sm">
                            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Check className="w-4 h-4" /> Lưu</>}
                          </button>
                        </div>
                      </div>
                    ) : (
                      /* View mode */
                      <div className="flex items-center gap-4">
                        <div className="w-10 h-10 rounded-lg bg-[#6c63ff]/10 flex items-center justify-center shrink-0">
                          {book.cover_url
                            ? <img src={book.cover_url} alt="" className="w-10 h-10 object-cover rounded-lg" />
                            : <BookOpen className="w-5 h-5 text-[#6c63ff]" />
                          }
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                            <p className="font-medium text-white truncate">{book.title}</p>
                            <span className={`badge badge-${book.status}`}>{statusLabel[book.status] || book.status}</span>
                            {book.category && <span className="text-xs text-[#6c63ff] bg-[#6c63ff]/10 px-2 py-0.5 rounded-full">{book.category}</span>}
                          </div>
                          <p className="text-sm text-[#8890a4] truncate">
                            {book.author ? `${book.author} · ` : ''}{book.publisher ? `${book.publisher} · ` : ''}{book.total_pages ? `${book.total_pages} trang · ` : ''}{formatSize(book.file_size)}
                          </p>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          <button onClick={() => startEdit(book)} className="btn-ghost px-3 py-2" title="Sửa metadata">
                            <Edit2 className="w-4 h-4" />
                          </button>
                          {book.status === 'ready' && (
                            <Link href={`/books/${book.id}`} className="btn-ghost px-3 py-2" title="Xem trang sách">
                              <Eye className="w-4 h-4" />
                            </Link>
                          )}
                          <button onClick={() => handleDelete(book)} disabled={deleting === book.id}
                            className="inline-flex items-center justify-center w-9 h-9 rounded-xl border border-red-500/20 text-red-400 hover:bg-red-500/10 transition-all disabled:opacity-50">
                            {deleting === book.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )
        )}

        {/* ── TAB: LOGS ── */}
        {tab === 'logs' && (
          logsLoading ? <div className="flex justify-center py-20"><Loader2 className="w-6 h-6 animate-spin text-[#6c63ff]" /></div>
            : logs.length === 0 ? (
              <div className="card text-center py-16 text-[#8890a4]">Chưa có log nào. Hãy thử đặt câu hỏi về một cuốn sách.</div>
            ) : (
              <div className="card overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[#2d3148] text-[#8890a4] text-xs">
                      <th className="text-left py-3 px-4 font-medium">Thời gian</th>
                      <th className="text-left py-3 px-4 font-medium">Loại</th>
                      <th className="text-left py-3 px-4 font-medium">Book</th>
                      <th className="text-left py-3 px-4 font-medium">Tokens</th>
                      <th className="text-left py-3 px-4 font-medium">Chi phí</th>
                      <th className="text-left py-3 px-4 font-medium">Câu hỏi</th>
                    </tr>
                  </thead>
                  <tbody>
                    {logs.map((log, i) => (
                      <tr key={i} className="border-b border-[#2d3148]/50 hover:bg-[#1e2236]/50">
                        <td className="py-2.5 px-4 text-[#8890a4] whitespace-nowrap">{log.timestamp?.split('INFO')[0]?.trim().slice(0, 19)}</td>
                        <td className="py-2.5 px-4">
                          <span className={`text-xs px-2 py-0.5 rounded-full ${log.mode === 'QUERY' ? 'bg-blue-500/10 text-blue-400' : 'bg-green-500/10 text-green-400'}`}>
                            {log.mode || '—'}
                          </span>
                        </td>
                        <td className="py-2.5 px-4 text-[#8890a4] font-mono text-xs">{log.book || '—'}</td>
                        <td className="py-2.5 px-4 text-white">{log.tokens || '—'}</td>
                        <td className="py-2.5 px-4 text-green-400">{log.cost || '—'}</td>
                        <td className="py-2.5 px-4 text-white max-w-xs truncate" title={log.q}>{log.q || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
        )}

        {/* ── TAB: CONFIG ── */}
        {tab === 'config' && (
          configLoading ? <div className="flex justify-center py-20"><Loader2 className="w-6 h-6 animate-spin text-[#6c63ff]" /></div>
            : config && (
              <div className="max-w-2xl space-y-4">
                <div className="card">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="font-semibold text-white">Cấu hình AI hiện tại</h3>
                    <button onClick={() => setEditConfig(e => !e)} className="btn-ghost px-3 py-2 text-sm">
                      <Edit2 className="w-4 h-4" /> {editConfig ? 'Hủy' : 'Chỉnh sửa'}
                    </button>
                  </div>
                  {!editConfig ? (
                    <div className="space-y-3">
                      <p className="text-xs text-[#6c63ff] font-semibold uppercase tracking-wider">🤖 Chat / RAG</p>
                      <div className="flex items-center justify-between py-2 border-b border-[#2d3148]/50">
                        <span className="text-[#8890a4] text-sm">Provider</span>
                        <span className="text-white font-medium text-sm">{config.providers[config.current.provider]?.name || config.current.provider}</span>
                      </div>
                      <div className="flex items-center justify-between py-2 border-b border-[#2d3148]/50">
                        <span className="text-[#8890a4] text-sm">Model</span>
                        <span className="text-white font-medium text-sm font-mono">{config.current.chat_model}</span>
                      </div>
                      {config.providers[config.current.provider]?.base_url && (
                        <div className="flex items-center justify-between py-2 border-b border-[#2d3148]/50">
                          <span className="text-[#8890a4] text-sm">Base URL</span>
                          <code className="text-[#6c63ff] text-xs">{config.providers[config.current.provider].base_url}</code>
                        </div>
                      )}
                      <p className="text-xs text-[#34d399] font-semibold uppercase tracking-wider pt-3">📐 Embedding</p>
                      <div className="flex items-center justify-between py-2 border-b border-[#2d3148]/50">
                        <span className="text-[#8890a4] text-sm">Provider</span>
                        <span className="text-white font-medium text-sm">{config.embedding_providers?.[config.current.embedding_provider]?.name || config.current.embedding_provider || 'OpenAI'}</span>
                      </div>
                      <div className="flex items-center justify-between py-2 border-b border-[#2d3148]/50">
                        <span className="text-[#8890a4] text-sm">Model</span>
                        <span className="text-white font-medium text-sm font-mono">{config.current.embedding_model}</span>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {/* ── Chat / RAG ── */}
                      <p className="text-xs text-[#6c63ff] font-semibold uppercase tracking-wider">🤖 Chat / RAG</p>
                      <div>
                        <label className="text-xs text-[#8890a4] mb-1 block">Chat Provider</label>
                        <select className="input" value={newProvider} onChange={e => {
                          setNewProvider(e.target.value);
                          const chatMs = config.providers[e.target.value]?.chat_models || [];
                          if (chatMs.length) setNewChatModel(chatMs[0].id);
                        }}>
                          {Object.entries(config.providers).map(([k, v]: any) => (
                            <option key={k} value={k} disabled={!config.available?.[k]}>
                              {v.name} {config.available?.[k] ? '✅' : '⚠️ Chưa có API Key'}
                            </option>
                          ))}
                        </select>
                        {config.providers[newProvider]?.base_url && (
                          <p className="text-xs text-[#8890a4] mt-1">
                            🔗 <code className="text-[#6c63ff]">{config.providers[newProvider].base_url}</code>
                          </p>
                        )}
                      </div>
                      <div>
                        <label className="text-xs text-[#8890a4] mb-1 block">Chat Model</label>
                        <select className="input" value={newChatModel} onChange={e => setNewChatModel(e.target.value)}>
                          {(config.providers[newProvider]?.chat_models || []).map((m: any) => (
                            <option key={m.id} value={m.id}>
                              {m.name} {m.input_price === 0 && m.output_price === 0 ? '— Miễn phí' : `— $${m.input_price}/$${m.output_price} / 1M tokens`}
                            </option>
                          ))}
                        </select>
                      </div>

                      {/* ── Embedding ── */}
                      <div className="border-t border-[#2d3148] pt-4">
                        <p className="text-xs text-[#34d399] font-semibold uppercase tracking-wider mb-3">📐 Embedding</p>
                      </div>
                      <div>
                        <label className="text-xs text-[#8890a4] mb-1 block">Embedding Provider</label>
                        <select className="input" value={newEmbedProvider} onChange={e => {
                          setNewEmbedProvider(e.target.value);
                          const embedMs = config.embedding_providers?.[e.target.value]?.embedding_models || [];
                          if (embedMs.length) setNewEmbedModel(embedMs[0].id);
                        }}>
                          {Object.entries(config.embedding_providers || {}).map(([k, v]: any) => (
                            <option key={k} value={k} disabled={!config.available?.[k]}>
                              {v.name} {config.available?.[k] ? '✅' : '⚠️ Chưa có API Key'}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="text-xs text-[#8890a4] mb-1 block">Embedding Model</label>
                        <select className="input" value={newEmbedModel} onChange={e => setNewEmbedModel(e.target.value)}>
                          {(config.embedding_providers?.[newEmbedProvider]?.embedding_models || []).map((m: any) => (
                            <option key={m.id} value={m.id}>
                              {m.name} {m.price === 0 ? '— Miễn phí' : `— $${m.price} / 1M tokens`}
                            </option>
                          ))}
                        </select>
                      </div>

                      {configMsg && <p className="text-sm">{configMsg}</p>}
                      <button onClick={saveConfig} disabled={configSaving} className="btn-primary">
                        {configSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Check className="w-4 h-4" /> Lưu cấu hình</>}
                      </button>
                    </div>
                  )}
                </div>

                {/* Đổi mật khẩu */}
                <ChangePasswordCard />
              </div>
            )
        )}
      </div>
    </div>
  );
}

function ChangePasswordCard() {
  const [cur, setCur] = useState(''); const [nw, setNw] = useState(''); const [loading, setLoading] = useState(false); const [msg, setMsg] = useState('');
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setMsg(''); setLoading(true);
    try { await authAPI.changePassword(cur, nw); setMsg('✅ Đổi mật khẩu thành công'); setCur(''); setNw(''); }
    catch (e: any) { setMsg('❌ ' + e.message); }
    finally { setLoading(false); }
  };
  return (
    <div className="card">
      <h3 className="font-semibold text-white mb-4">Đổi mật khẩu</h3>
      <form onSubmit={submit} className="space-y-3">
        <input className="input" type="password" placeholder="Mật khẩu hiện tại" value={cur} onChange={e => setCur(e.target.value)} required />
        <input className="input" type="password" placeholder="Mật khẩu mới (ít nhất 8 ký tự)" value={nw} onChange={e => setNw(e.target.value)} required minLength={8} />
        {msg && <p className="text-sm">{msg}</p>}
        <button type="submit" disabled={loading} className="btn-primary w-full justify-center">
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Đổi mật khẩu'}
        </button>
      </form>
    </div>
  );
}
