'use client';
import { useState, useCallback, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Upload, BookOpen, ArrowLeft, FileText, CheckCircle, XCircle, Loader2, Clock } from 'lucide-react';
import { booksAPI } from '@/lib/api';

type UploadPhase = 'idle' | 'uploading' | 'processing' | 'success' | 'error';

const PHASE_LABELS: Record<UploadPhase, string> = {
  idle: '',
  uploading: '📤 Đang upload file...',
  processing: '⚙️ Đang xử lý: trích xuất → chunk → embedding...',
  success: '',
  error: '',
};

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [form, setForm] = useState({ title: '', author: '', description: '' });
  const [phase, setPhase] = useState<UploadPhase>('idle');
  const [message, setMessage] = useState('');
  const [bookId, setBookId] = useState('');
  const [elapsedSec, setElapsedSec] = useState(0);
  const pollRef = useRef<NodeJS.Timeout | null>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  // Tính giờ chạy khi đang processing
  useEffect(() => {
    if (phase === 'processing') {
      timerRef.current = setInterval(() => setElapsedSec(s => s + 1), 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
      setElapsedSec(0);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [phase]);

  // Poll status khi processing
  useEffect(() => {
    if (phase === 'processing' && bookId) {
      pollRef.current = setInterval(async () => {
        try {
          const book = await booksAPI.get(bookId);
          if (book.status === 'ready') {
            clearInterval(pollRef.current!);
            setPhase('success');
            setMessage(`✅ Sách "${book.title}" đã sẵn sàng! (${book.total_pages || '?'} trang)`);
          } else if (book.status === 'error') {
            clearInterval(pollRef.current!);
            setPhase('error');
            setMessage('Có lỗi xảy ra trong quá trình xử lý sách');
          }
        } catch { /* polling failures are silent */ }
      }, 2000); // poll mỗi 2s
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [phase, bookId]);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped?.type === 'application/pdf') {
      setFile(dropped);
      if (!form.title) setForm(f => ({ ...f, title: dropped.name.replace('.pdf', '') }));
    }
  }, [form.title]);

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) {
      setFile(f);
      if (!form.title) setForm(prev => ({ ...prev, title: f.name.replace('.pdf', '') }));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !form.title) return;

    setPhase('uploading');

    try {
      const result = await booksAPI.upload(file, {
        title: form.title,
        author: form.author || undefined,
        description: form.description || undefined,
        language: 'vi',
      });

      setBookId(result.book_id);
      setPhase('processing'); // API trả về ngay, bắt đầu poll
    } catch (err: any) {
      setPhase('error');
      setMessage(err.message || 'Có lỗi xảy ra khi upload');
    }
  };

  const reset = () => {
    setPhase('idle');
    setFile(null);
    setForm({ title: '', author: '', description: '' });
    setBookId('');
    setMessage('');
  };

  const formatSize = (bytes: number) =>
    bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(0)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;

  return (
    <div className="min-h-screen">
      <nav style={{ borderBottom: '1px solid #2d3148', background: 'rgba(15,17,23,0.8)', backdropFilter: 'blur(8px)', position: 'sticky', top: 0, zIndex: 50 }}>
        <div style={{ maxWidth: 672, margin: '0 auto', padding: '1rem 1.5rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <Link href="/admin" className="btn-ghost" style={{ padding: '0.5rem 0.75rem' }}>
            <ArrowLeft style={{ width: 16, height: 16 }} />
          </Link>
          <BookOpen style={{ width: 16, height: 16, color: '#6c63ff' }} />
          <span style={{ fontWeight: 500 }}>Upload sách PDF</span>
        </div>
      </nav>

      <div style={{ maxWidth: 672, margin: '0 auto', padding: '3rem 1.5rem' }}>
        {/* Success */}
        {phase === 'success' && (
          <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
            <CheckCircle style={{ width: 56, height: 56, color: '#34d399', margin: '0 auto 1rem' }} />
            <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'white', marginBottom: '0.5rem' }}>Upload thành công!</h2>
            <p style={{ color: '#8890a4', marginBottom: '2rem' }}>{message}</p>
            <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center' }}>
              <Link href={`/reader/${bookId}`} className="btn-primary">
                <BookOpen style={{ width: 16, height: 16 }} /> Đọc ngay
              </Link>
              <button onClick={reset} className="btn-ghost">Upload sách khác</button>
            </div>
          </div>
        )}

        {/* Processing overlay */}
        {phase === 'processing' && (
          <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
            <div style={{ position: 'relative', width: 64, height: 64, margin: '0 auto 1.5rem' }}>
              <Loader2 style={{ width: 64, height: 64, color: '#6c63ff', animation: 'spin 1s linear infinite' }} />
            </div>
            <h2 style={{ fontSize: '1.125rem', fontWeight: 600, color: 'white', marginBottom: '0.5rem' }}>Đang xử lý sách...</h2>
            <p style={{ color: '#8890a4', fontSize: '0.875rem', marginBottom: '1.5rem' }}>
              Trích xuất text → Chunk → Embedding → Lưu vector DB
            </p>
            {/* Progress steps */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxWidth: 280, margin: '0 auto 1.5rem', textAlign: 'left' }}>
              {[
                { label: 'Upload lên Storage', done: true },
                { label: 'Trích xuất nội dung PDF', done: elapsedSec > 2 },
                { label: 'Phân đoạn văn bản (chunking)', done: elapsedSec > 5 },
                { label: 'Tạo vector embeddings (OpenAI)', done: elapsedSec > 10 },
                { label: 'Lưu vào pgvector', done: elapsedSec > 12 },
              ].map((step, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8rem' }}>
                  <div style={{
                    width: 18, height: 18, borderRadius: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                    background: step.done ? 'rgba(52,211,153,0.15)' : 'rgba(108,99,255,0.1)',
                    border: `1px solid ${step.done ? '#34d399' : '#2d3148'}`,
                  }}>
                    {step.done
                      ? <span style={{ color: '#34d399', fontSize: 10 }}>✓</span>
                      : i === [true, elapsedSec > 2, elapsedSec > 5, elapsedSec > 10, elapsedSec > 12].lastIndexOf(false) && i === [true, elapsedSec > 2, elapsedSec > 5, elapsedSec > 10, elapsedSec > 12].indexOf(false)
                        ? <Loader2 style={{ width: 10, height: 10, color: '#6c63ff', animation: 'spin 1s linear infinite' }} />
                        : <span style={{ fontSize: 10, color: '#8890a4' }}>·</span>}
                  </div>
                  <span style={{ color: step.done ? '#e8eaf0' : '#8890a4' }}>{step.label}</span>
                </div>
              ))}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.375rem', color: '#8890a4', fontSize: '0.75rem' }}>
              <Clock style={{ width: 12, height: 12 }} />
              {elapsedSec}s đã trôi qua...
            </div>
          </div>
        )}

        {/* Upload form */}
        {(phase === 'idle' || phase === 'uploading' || phase === 'error') && (
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'white' }}>Upload sách PDF</h1>

            {/* Drop zone */}
            <div
              onDrop={onDrop}
              onDragOver={e => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              style={{
                position: 'relative', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                borderRadius: '1rem', border: `2px dashed ${dragging ? '#6c63ff' : '#2d3148'}`,
                background: dragging ? 'rgba(108,99,255,0.1)' : '#1e2130',
                padding: '2.5rem', cursor: 'pointer', transition: 'all 0.2s',
              }}
            >
              <input type="file" accept=".pdf" style={{ position: 'absolute', inset: 0, opacity: 0, cursor: 'pointer' }} onChange={onFileChange} />
              {file ? (
                <div style={{ textAlign: 'center' }}>
                  <FileText style={{ width: 40, height: 40, color: '#6c63ff', margin: '0 auto 0.75rem' }} />
                  <p style={{ fontWeight: 500, color: 'white' }}>{file.name}</p>
                  <p style={{ fontSize: '0.875rem', color: '#8890a4', marginTop: '0.25rem' }}>{formatSize(file.size)}</p>
                </div>
              ) : (
                <div style={{ textAlign: 'center' }}>
                  <Upload style={{ width: 40, height: 40, color: '#8890a4', margin: '0 auto 0.75rem' }} />
                  <p style={{ color: 'white', fontWeight: 500 }}>Kéo thả file PDF vào đây</p>
                  <p style={{ fontSize: '0.875rem', color: '#8890a4', marginTop: '0.25rem' }}>hoặc click để chọn (tối đa 50MB)</p>
                </div>
              )}
            </div>

            {/* Metadata */}
            <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <h3 style={{ fontWeight: 500, color: 'white' }}>Thông tin sách</h3>
              {[
                { key: 'title', label: 'Tiêu đề *', placeholder: 'Tên sách...', required: true },
                { key: 'author', label: 'Tác giả', placeholder: 'Tên tác giả...' },
              ].map(({ key, label, placeholder, required }) => (
                <div key={key}>
                  <label style={{ fontSize: '0.875rem', color: '#8890a4', display: 'block', marginBottom: '0.375rem' }}>{label}</label>
                  <input className="input" placeholder={placeholder} required={required}
                    value={form[key as keyof typeof form]}
                    onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))} />
                </div>
              ))}
              <div>
                <label style={{ fontSize: '0.875rem', color: '#8890a4', display: 'block', marginBottom: '0.375rem' }}>Mô tả</label>
                <textarea className="input" rows={3} style={{ resize: 'none' }} placeholder="Mô tả ngắn..."
                  value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
              </div>
            </div>

            {phase === 'error' && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', borderRadius: '0.75rem', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', padding: '0.75rem 1rem' }}>
                <XCircle style={{ width: 16, height: 16, color: '#ef4444', flexShrink: 0 }} />
                <p style={{ fontSize: '0.875rem', color: '#ef4444' }}>{message}</p>
              </div>
            )}

            <button type="submit" disabled={!file || !form.title || phase === 'uploading'} className="btn-primary" style={{ justifyContent: 'center', padding: '0.75rem' }}>
              {phase === 'uploading'
                ? <><Loader2 style={{ width: 16, height: 16, animation: 'spin 1s linear infinite' }} /> Đang upload...</>
                : <><Upload style={{ width: 16, height: 16 }} /> Upload & Xử lý sách</>}
            </button>
          </form>
        )}
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
