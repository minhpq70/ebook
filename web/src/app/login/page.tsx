'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { BookOpen, LogIn, Eye, EyeOff, AlertCircle } from 'lucide-react';
import { authAPI, setAuth } from '@/lib/auth';

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await authAPI.login(username, password);
      setAuth(res.access_token, { username: res.username, role: res.role as 'admin' | 'user' });
      router.replace(res.role === 'admin' ? '/admin' : '/');
    } catch (err: any) {
      setError(err.message || 'Đăng nhập thất bại');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4" style={{ background: 'radial-gradient(ellipse at top, #1a1f35 0%, #0f1117 60%)' }}>
      <div style={{ width: '100%', maxWidth: 400 }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div style={{ width: 56, height: 56, borderRadius: '1rem', background: '#6c63ff', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', marginBottom: '1rem' }}>
            <BookOpen style={{ width: 28, height: 28, color: 'white' }} />
          </div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'white', margin: 0 }}>EbookAI</h1>
          <p style={{ color: '#8890a4', marginTop: '0.25rem', fontSize: '0.875rem' }}>Đăng nhập để tiếp tục</p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="card" style={{ padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div>
            <label style={{ fontSize: '0.875rem', color: '#8890a4', display: 'block', marginBottom: '0.375rem' }}>Tên đăng nhập</label>
            <input
              className="input"
              placeholder="Nhập username..."
              value={username}
              onChange={e => setUsername(e.target.value)}
              required
              autoFocus
            />
          </div>

          <div>
            <label style={{ fontSize: '0.875rem', color: '#8890a4', display: 'block', marginBottom: '0.375rem' }}>Mật khẩu</label>
            <div style={{ position: 'relative' }}>
              <input
                className="input"
                type={showPass ? 'text' : 'password'}
                placeholder="Nhập mật khẩu..."
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                style={{ paddingRight: '2.75rem' }}
              />
              <button
                type="button"
                onClick={() => setShowPass(p => !p)}
                style={{ position: 'absolute', right: '0.75rem', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: '#8890a4' }}
              >
                {showPass ? <EyeOff style={{ width: 16, height: 16 }} /> : <Eye style={{ width: 16, height: 16 }} />}
              </button>
            </div>
          </div>

          {error && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: '0.75rem', padding: '0.75rem' }}>
              <AlertCircle style={{ width: 16, height: 16, color: '#ef4444', flexShrink: 0 }} />
              <p style={{ fontSize: '0.875rem', color: '#ef4444' }}>{error}</p>
            </div>
          )}

          <button type="submit" disabled={loading} className="btn-primary" style={{ justifyContent: 'center', padding: '0.75rem', marginTop: '0.25rem' }}>
            {loading ? 'Đang đăng nhập...' : <><LogIn style={{ width: 16, height: 16 }} /> Đăng nhập</>}
          </button>

          <p style={{ textAlign: 'center', color: '#8890a4', fontSize: '0.875rem' }}>
            Chưa có tài khoản?{' '}
            <Link href="/register" style={{ color: '#6c63ff', textDecoration: 'none' }}>Đăng ký</Link>
          </p>
        </form>

        <p style={{ textAlign: 'center', marginTop: '1.5rem' }}>
          <Link href="/" style={{ color: '#8890a4', fontSize: '0.875rem', textDecoration: 'none' }}>← Về trang chủ</Link>
        </p>
      </div>
    </div>
  );
}
