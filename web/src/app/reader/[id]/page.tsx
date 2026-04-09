'use client';
import { useEffect, useState, useRef } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft, BookOpen, Loader2, Sparkles, Send, X,
  ChevronUp, ChevronDown, ExternalLink, MessageSquare, Menu
} from 'lucide-react';
import { booksAPI, Book, ChunkInfo, TaskType } from '@/lib/api';
import { API_BASE } from '@/lib/config';
import PDFViewer from '@/components/PDFViewer';

type Message = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: ChunkInfo[];
  loading?: boolean;
  streaming?: boolean;
};

const TASK_OPTIONS: { value: TaskType; label: string; emoji: string }[] = [
  { value: 'qa',                 label: 'Hỏi đáp',        emoji: '💬' },
  { value: 'explain',           label: 'Giải thích',      emoji: '🔍' },
  { value: 'summarize_chapter', label: 'Tóm tắt chương',  emoji: '📝' },
  { value: 'summarize_book',    label: 'Tóm tắt sách',    emoji: '📚' },
  { value: 'suggest',           label: 'Gợi ý',           emoji: '✨' },
];

export default function ReaderPage() {
  const { id } = useParams<{ id: string }>();
  const [book, setBook] = useState<Book | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [chatOpen, setChatOpen] = useState(true);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [taskType, setTaskType] = useState<TaskType>('qa');
  const [sending, setSending] = useState(false);
  const [sourcesOpen, setSourcesOpen] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    Promise.all([
      booksAPI.get(id),
      booksAPI.getPdfUrl(id),
    ])
    .then(([bookInfo, urlInfo]) => {
      setBook(bookInfo);
      setPdfUrl(urlInfo.url);
    })
    .catch(e => setError(e.message))
    .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || sending) return;
    const query = input.trim();
    setInput('');
    setSending(true);

    const userMsgId = Date.now().toString();
    const asstMsgId = (Date.now() + 1).toString();

    setMessages(prev => [
      ...prev,
      { id: userMsgId, role: 'user', content: query },
      { id: asstMsgId, role: 'assistant', content: '', loading: true, streaming: false },
    ]);

    try {
      const res = await fetch(`${API_BASE}/rag/query/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ book_id: id, query, task_type: taskType }),
        credentials: 'include',
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || 'Lỗi server');
      }

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let sources: ChunkInfo[] = [];

      // Chuyển sang streaming mode
      setMessages(prev => prev.map(m =>
        m.id === asstMsgId ? { ...m, loading: false, streaming: true } : m
      ));

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const data = line.slice(6).trim();
          if (data === '[DONE]') break;

          try {
            const event = JSON.parse(data);

            if (event.type === 'sources') {
              sources = event.data;
              setMessages(prev => prev.map(m =>
                m.id === asstMsgId ? { ...m, sources } : m
              ));
            } else if (event.type === 'token') {
              setMessages(prev => prev.map(m =>
                m.id === asstMsgId ? { ...m, content: m.content + event.data } : m
              ));
            } else if (event.type === 'done') {
              setMessages(prev => prev.map(m =>
                m.id === asstMsgId ? { ...m, streaming: false } : m
              ));
            } else if (event.type === 'error') {
              throw new Error(event.data);
            }
          } catch { /* JSON parse errors từ non-JSON lines */ }
        }
      }
    } catch (err: any) {
      setMessages(prev => prev.map(m =>
        m.id === asstMsgId
          ? { ...m, content: `❌ ${err.message}`, loading: false, streaming: false }
          : m
      ));
    } finally {
      setSending(false);
    }
  };

  if (loading) return <FullPageLoader />;
  if (error || !book) return <ErrorScreen error={error} />;

  return (
    <div className="min-h-screen flex flex-col">
      {/* Navbar */}
      <nav style={{ borderBottom: '1px solid #2d3148', background: 'rgba(15,17,23,0.9)', backdropFilter: 'blur(8px)', position: 'sticky', top: 0, zIndex: 50 }}>
        <div style={{ maxWidth: 1152, margin: '0 auto', padding: '0.75rem 1.5rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', minWidth: 0 }}>
            <Link href="/" className="btn-ghost" style={{ padding: '0.5rem 0.75rem', flexShrink: 0 }}>
              <ArrowLeft style={{ width: 16, height: 16 }} />
            </Link>
            <div style={{ minWidth: 0 }}>
              <p style={{ fontWeight: 600, color: 'white', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{book.title}</p>
              {book.author && <p style={{ fontSize: '0.75rem', color: '#8890a4' }}>{book.author}</p>}
            </div>
          </div>
          <button onClick={() => setChatOpen(o => !o)} className="btn-primary" style={{ flexShrink: 0, padding: '0.5rem 0.75rem', gap: '0.375rem' }}>
            <Sparkles style={{ width: 16, height: 16 }} />
            <span className="hidden sm:inline">Hỏi AI</span>
          </button>
        </div>
      </nav>

      <div style={{ display: 'flex', flex: 1, maxWidth: '100%', padding: '1rem', gap: '1rem', overflow: 'hidden' }}>
        {/* Main PDF Area */}
        <div style={{ flex: chatOpen ? '0 0 60%' : 1, transition: 'all 0.3s ease', minWidth: 0, display: 'flex', flexDirection: 'column' }}>
          {pdfUrl ? (
            <PDFViewer 
              url={pdfUrl} 
              onTextSelect={(text) => {
                setTaskType('explain');
                setInput(`Hãy giải thích đoạn văn bản sau: "${text}"`);
                setChatOpen(true);
              }}
            />
          ) : (
            <div className="card" style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center' }}>
              <BookOpen style={{ width: 64, height: 64, color: '#2d3148', marginBottom: '1rem' }} />
              <p style={{ fontSize: '1.25rem', fontWeight: 600, color: 'white', marginBottom: '0.5rem' }}>{book.title}</p>
              {book.author && <p style={{ color: '#8890a4', marginBottom: '0.5rem' }}>by {book.author}</p>}
            </div>
          )}
        </div>

        {/* Chat panel */}
        {chatOpen && (
          <div style={{ flex: '0 0 40%', display: 'flex', flexDirection: 'column', transition: 'all 0.3s ease', minWidth: 320 }}>
            <div className="card" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
              {/* Header */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingBottom: '1rem', marginBottom: '1rem', borderBottom: '1px solid #2d3148' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Sparkles style={{ width: 16, height: 16, color: '#6c63ff' }} />
                  <span style={{ fontWeight: 500, color: 'white' }}>AI Assistant</span>
                  <span style={{ fontSize: '0.625rem', color: '#8890a4', fontFamily: 'monospace' }}>Private RAG</span>
                </div>
                <button onClick={() => setChatOpen(false)} style={{ color: '#8890a4', background: 'none', border: 'none', cursor: 'pointer' }}>
                  <X style={{ width: 16, height: 16 }} />
                </button>
              </div>

              {/* Task selector */}
              <div style={{ display: 'flex', gap: '0.375rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
                {TASK_OPTIONS.map(t => (
                  <button key={t.value} onClick={() => setTaskType(t.value)}
                    style={{
                      fontSize: '0.75rem', padding: '0.25rem 0.625rem', borderRadius: 9999, cursor: 'pointer',
                      border: `1px solid ${taskType === t.value ? '#6c63ff' : '#2d3148'}`,
                      background: taskType === t.value ? 'rgba(108,99,255,0.2)' : 'transparent',
                      color: taskType === t.value ? '#8b85ff' : '#8890a4',
                    }}>
                    {t.emoji} {t.label}
                  </button>
                ))}
              </div>

              {/* Messages */}
              <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '1rem', paddingRight: '0.25rem' }}>
                {messages.length === 0 && (
                  <div style={{ textAlign: 'center', padding: '2rem 0', color: '#8890a4' }}>
                    <MessageSquare style={{ width: 32, height: 32, margin: '0 auto 0.75rem', color: '#2d3148' }} />
                    <p style={{ fontSize: '0.875rem' }}>Đặt câu hỏi về nội dung sách</p>
                  </div>
                )}

                {messages.map(msg => (
                  <div key={msg.id} style={{ display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
                    <div style={{
                      maxWidth: '85%', borderRadius: '1rem', padding: '0.75rem 1rem', fontSize: '0.875rem', lineHeight: 1.6,
                      background: msg.role === 'user' ? '#6c63ff' : '#1a1d27',
                      border: msg.role === 'assistant' ? '1px solid #2d3148' : 'none',
                      color: '#e8eaf0',
                    }}>
                      {msg.loading ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <Loader2 style={{ width: 14, height: 14, color: '#6c63ff', animation: 'spin 1s linear infinite' }} />
                          <span style={{ color: '#8890a4', fontSize: '0.75rem' }}>Đang tìm và phân tích...</span>
                        </div>
                      ) : (
                        <>
                          <div style={{ whiteSpace: 'pre-wrap' }}>
                            {msg.content}
                            {msg.streaming && (
                              <span style={{ display: 'inline-block', width: 2, height: '1em', background: '#6c63ff', marginLeft: 2, animation: 'blink 1s step-end infinite', verticalAlign: 'text-bottom' }} />
                            )}
                          </div>

                          {/* Sources */}
                          {msg.sources && msg.sources.length > 0 && (
                            <div style={{ marginTop: '0.75rem', paddingTop: '0.75rem', borderTop: '1px solid #2d3148' }}>
                              <button onClick={() => setSourcesOpen(sourcesOpen === msg.id ? null : msg.id)}
                                style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', fontSize: '0.75rem', color: '#8890a4', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}>
                                <ExternalLink style={{ width: 12, height: 12 }} />
                                {msg.sources.length} nguồn trích dẫn
                                {sourcesOpen === msg.id ? <ChevronUp style={{ width: 12, height: 12 }} /> : <ChevronDown style={{ width: 12, height: 12 }} />}
                              </button>
                              {sourcesOpen === msg.id && (
                                <div style={{ marginTop: '0.5rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                                  {msg.sources.map((src, i) => (
                                    <div key={src.id} style={{ borderRadius: '0.5rem', background: '#0f1117', padding: '0.625rem', fontSize: '0.75rem', color: '#8890a4' }}>
                                      <div style={{ color: '#6c63ff', fontWeight: 500, marginBottom: '0.25rem' }}>
                                        Đoạn {i + 1}{src.page_number ? ` · Trang ${src.page_number}` : ''}
                                      </div>
                                      <p style={{ overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical' }}>{src.content}</p>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>

              {/* Input */}
              <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid #2d3148', display: 'flex', gap: '0.5rem' }}>
                <input className="input" style={{ flex: 1, padding: '0.625rem 1rem' }}
                  placeholder={`${TASK_OPTIONS.find(t => t.value === taskType)?.emoji} Nhập câu hỏi...`}
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMessage()}
                  disabled={sending}
                />
                <button onClick={sendMessage} disabled={!input.trim() || sending} className="btn-primary" style={{ padding: '0.625rem 0.75rem' }}>
                  {sending ? <Loader2 style={{ width: 16, height: 16, animation: 'spin 1s linear infinite' }} /> : <Send style={{ width: 16, height: 16 }} />}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes blink { 50% { opacity: 0; } }
      `}</style>
    </div>
  );
}

function FullPageLoader() {
  return <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
    <Loader2 style={{ width: 32, height: 32, color: '#6c63ff', animation: 'spin 1s linear infinite' }} />
    <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
  </div>;
}

function ErrorScreen({ error }: { error: string }) {
  return <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '1rem' }}>
    <p style={{ color: '#ef4444' }}>{error || 'Không tìm thấy sách'}</p>
    <Link href="/" className="btn-ghost">← Về trang chủ</Link>
  </div>;
}
