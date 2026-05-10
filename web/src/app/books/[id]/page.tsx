'use client';
import { useEffect, useState, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, BookOpen, Send, Loader2, User, Bot, ChevronDown, ChevronUp } from 'lucide-react';
import { booksAPI, Book } from '@/lib/api';
import { API_BASE } from '@/lib/config';
import ReactMarkdown from 'react-markdown';

interface Message { role: 'user' | 'assistant'; content: string; }

export default function BookDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [book, setBook] = useState<Book | null>(null);
  const [loading, setLoading] = useState(true);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [summaryOpen, setSummaryOpen] = useState(true);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    booksAPI.get(id)
      .then(setBook)
      .catch(() => router.replace('/'))
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const sendMessage = async () => {
    const q = input.trim();
    if (!q || chatLoading) return;
    setInput('');
    setMessages(m => [...m, { role: 'user', content: q }]);
    setChatLoading(true);

    try {
      const res = await fetch(`${API_BASE}/rag/query/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ book_id: id, query: q, task_type: 'auto' }),
        credentials: 'include',
      });
      if (!res.ok) throw new Error('Lỗi AI');

      let answer = '';
      setMessages(m => [...m, { role: 'assistant', content: '' }]);
      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let streamDone = false;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // giữ lại dòng chưa hoàn chỉnh
        for (const line of lines) {
          if (!line.startsWith('data:')) continue;
          const data = line.slice(5).trim();
          if (data === '[DONE]') { streamDone = true; break; }
          try {
            const json = JSON.parse(data);
            if (json.type === 'token') {
              answer += json.data;
              setMessages(m => { const copy = [...m]; copy[copy.length - 1] = { role: 'assistant', content: answer }; return copy; });
            }
          } catch { }
        }
        if (streamDone) break;
      }
    } catch {
      setMessages(m => [...m, { role: 'assistant', content: 'Có lỗi xảy ra, vui lòng thử lại.' }]);
    } finally {
      setChatLoading(false);
    }
  };

  if (loading) return (
    <div style={{ minHeight: '100vh', background: '#f5f6fa', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <Loader2 style={{ width: 32, height: 32, color: '#1a237e', animation: 'spin 1s linear infinite' }} />
    </div>
  );
  if (!book) return null;

  const coverBg = `hsl(${Math.abs(book.id.charCodeAt(0) * 37) % 360}, 55%, 32%)`;

  return (
    <div style={{ minHeight: '100vh', background: '#f5f6fa', color: '#1a1a2e' }}>
      {/* Header */}
      <header style={{ background: '#1a237e', color: 'white', padding: '0.875rem 1.5rem', display: 'flex', alignItems: 'center', gap: '1rem', position: 'sticky', top: 0, zIndex: 50, boxShadow: '0 2px 8px rgba(0,0,0,0.2)' }}>
        <button onClick={() => router.back()} style={{ background: 'rgba(255,255,255,0.15)', border: 'none', borderRadius: '0.5rem', width: 36, height: 36, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: 'white' }}>
          <ArrowLeft style={{ width: 18, height: 18 }} />
        </button>
        <BookOpen style={{ width: 20, height: 20 }} />
        <span style={{ fontWeight: 600, fontSize: '1rem' }}>Chi tiết sách</span>
        <Link href="/" style={{ marginLeft: 'auto', color: 'rgba(255,255,255,0.7)', fontSize: '0.8rem', textDecoration: 'none' }}>← Trang chủ</Link>
      </header>

      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '2rem 1.5rem', display: 'grid', gridTemplateColumns: '280px 1fr', gap: '2rem', alignItems: 'start' }}>
        {/* Left: Book info */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', position: 'sticky', top: '5rem' }}>
          {/* Cover */}
          <div style={{ borderRadius: '0.75rem', overflow: 'hidden', boxShadow: '0 8px 24px rgba(0,0,0,0.15)', aspectRatio: '3/4', background: coverBg, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            {book.cover_url
              ? <img src={book.cover_url} alt={book.title} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
              : <BookOpen style={{ width: 72, height: 72, color: 'rgba(255,255,255,0.4)' }} />
            }
          </div>

          {/* Metadata card */}
          <div style={{ background: 'white', borderRadius: '0.75rem', padding: '1.25rem', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
            <h1 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#1a1a2e', margin: '0 0 0.5rem', lineHeight: 1.4 }}>{book.title}</h1>
            {book.author && <p style={{ fontSize: '0.875rem', color: '#555', margin: '0 0 0.75rem' }}>{book.author}</p>}
            {book.category && (
              <span style={{ display: 'inline-block', background: '#e8eaf6', color: '#1a237e', fontSize: '0.75rem', padding: '0.2rem 0.625rem', borderRadius: '2rem', fontWeight: 500, marginBottom: '0.875rem' }}>
                {book.category}
              </span>
            )}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem', fontSize: '0.8rem' }}>
              {book.publisher && <div style={{ display: 'flex', gap: '0.375rem' }}><span style={{ color: '#999', minWidth: 80 }}>NXB:</span><span style={{ color: '#1a1a2e', fontWeight: 500 }}>{book.publisher}</span></div>}
              {book.published_year && <div style={{ display: 'flex', gap: '0.375rem' }}><span style={{ color: '#999', minWidth: 80 }}>Năm XB:</span><span style={{ color: '#1a1a2e' }}>{book.published_year}</span></div>}
              {book.page_size && <div style={{ display: 'flex', gap: '0.375rem' }}><span style={{ color: '#999', minWidth: 80 }}>Khổ cỡ:</span><span style={{ color: '#1a1a2e' }}>{book.page_size}</span></div>}
              {book.total_pages && <div style={{ display: 'flex', gap: '0.375rem' }}><span style={{ color: '#999', minWidth: 80 }}>Số trang:</span><span style={{ color: '#1a1a2e' }}>{book.total_pages} trang</span></div>}
              {book.language && <div style={{ display: 'flex', gap: '0.375rem' }}><span style={{ color: '#999', minWidth: 80 }}>Ngôn ngữ:</span><span style={{ color: '#1a1a2e' }}>{book.language === 'vi' ? 'Tiếng Việt' : book.language}</span></div>}
            </div>
          </div>
        </div>

        {/* Right: Summary + Chat */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* AI Summary */}
          {book.ai_summary && (
            <div style={{ background: 'white', borderRadius: '0.75rem', boxShadow: '0 2px 8px rgba(0,0,0,0.06)', overflow: 'hidden' }}>
              <button onClick={() => setSummaryOpen(o => !o)}
                style={{ width: '100%', padding: '1rem 1.25rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'none', border: 'none', cursor: 'pointer', borderBottom: summaryOpen ? '1px solid #f0f0f0' : 'none' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Bot style={{ width: 18, height: 18, color: '#1a237e' }} />
                  <span style={{ fontWeight: 600, color: '#1a1a2e' }}>Tóm tắt nội dung sách</span>
                  <span style={{ fontSize: '0.7rem', background: '#e8eaf6', color: '#1a237e', padding: '0.1rem 0.4rem', borderRadius: '2rem' }}>AI</span>
                </div>
                {summaryOpen ? <ChevronUp style={{ width: 16, height: 16, color: '#999' }} /> : <ChevronDown style={{ width: 16, height: 16, color: '#999' }} />}
              </button>
              {summaryOpen && <div style={{ padding: '1.25rem', fontSize: '0.9rem', lineHeight: 1.7, color: '#444' }}>{book.ai_summary}</div>}
            </div>
          )}

          {/* Chat */}
          <div style={{ background: 'white', borderRadius: '0.75rem', boxShadow: '0 2px 8px rgba(0,0,0,0.06)', display: 'flex', flexDirection: 'column', minHeight: 480 }}>
            <div style={{ padding: '1rem 1.25rem', borderBottom: '1px solid #f0f0f0', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Bot style={{ width: 18, height: 18, color: '#1a237e' }} />
              <span style={{ fontWeight: 600, color: '#1a1a2e' }}>Hỏi AI về cuốn sách này</span>
            </div>
            {/* Messages */}
            <div style={{ flex: 1, padding: '1rem 1.25rem', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.875rem', maxHeight: 380 }}>
              {messages.length === 0 && (
                <div style={{ textAlign: 'center', color: '#bbb', padding: '2rem', fontSize: '0.875rem' }}>
                  Bắt đầu đặt câu hỏi về nội dung cuốn sách...
                </div>
              )}
              {messages.map((msg, i) => (
                <div key={i} style={{ display: 'flex', gap: '0.625rem', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
                  {msg.role === 'assistant' && (
                    <div style={{ width: 28, height: 28, borderRadius: '50%', background: '#e8eaf6', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                      <Bot style={{ width: 14, height: 14, color: '#1a237e' }} />
                    </div>
                  )}
                  <div style={{ maxWidth: '75%', padding: '0.625rem 0.875rem', borderRadius: msg.role === 'user' ? '1rem 1rem 0.25rem 1rem' : '1rem 1rem 1rem 0.25rem', background: msg.role === 'user' ? '#1a237e' : '#f5f6fa', color: msg.role === 'user' ? 'white' : '#1a1a2e', fontSize: '0.875rem', lineHeight: 1.6 }}>
                    {msg.role === 'assistant' ? (
                      <ReactMarkdown
                        components={{
                          h1: ({ children }) => <h3 style={{ fontSize: '1rem', fontWeight: 600, margin: '0.5rem 0 0.25rem' }}>{children}</h3>,
                          h2: ({ children }) => <h3 style={{ fontSize: '1rem', fontWeight: 600, margin: '0.5rem 0 0.25rem' }}>{children}</h3>,
                          h3: ({ children }) => <h4 style={{ fontSize: '0.9rem', fontWeight: 600, margin: '0.5rem 0 0.25rem' }}>{children}</h4>,
                          p: ({ children }) => <p style={{ margin: '0.25rem 0' }}>{children}</p>,
                          ul: ({ children }) => <ul style={{ paddingLeft: '1.25rem', margin: '0.25rem 0' }}>{children}</ul>,
                          ol: ({ children }) => <ol style={{ paddingLeft: '1.25rem', margin: '0.25rem 0' }}>{children}</ol>,
                          li: ({ children }) => <li style={{ margin: '0.125rem 0' }}>{children}</li>,
                          strong: ({ children }) => <strong style={{ fontWeight: 600 }}>{children}</strong>,
                        }}
                      >{msg.content || (chatLoading && i === messages.length - 1 ? '...' : '')}</ReactMarkdown>
                    ) : (
                      <span style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</span>
                    )}
                  </div>
                  {msg.role === 'user' && (
                    <div style={{ width: 28, height: 28, borderRadius: '50%', background: '#1a237e', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                      <User style={{ width: 14, height: 14, color: 'white' }} />
                    </div>
                  )}
                </div>
              ))}
              <div ref={bottomRef} />
            </div>
            {/* Input */}
            <div style={{ padding: '0.875rem 1.25rem', borderTop: '1px solid #f0f0f0', display: 'flex', gap: '0.625rem' }}>
              <input
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } }}
                placeholder="Nhập câu hỏi... (Enter để gửi)"
                disabled={chatLoading}
                style={{ flex: 1, padding: '0.625rem 1rem', borderRadius: '2rem', border: '1.5px solid #e0e0e0', outline: 'none', fontSize: '0.875rem', background: '#fafafa', color: '#1a1a2e' }}
              />
              <button onClick={sendMessage} disabled={chatLoading || !input.trim()}
                style={{ width: 40, height: 40, borderRadius: '50%', background: '#1a237e', border: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', flexShrink: 0, opacity: chatLoading || !input.trim() ? 0.5 : 1 }}>
                {chatLoading ? <Loader2 style={{ width: 16, height: 16, color: 'white', animation: 'spin 1s linear infinite' }} /> : <Send style={{ width: 16, height: 16, color: 'white' }} />}
              </button>
            </div>
          </div>
        </div>
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
