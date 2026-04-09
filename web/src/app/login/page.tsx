'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { BookOpen, LogIn, Eye, EyeOff, AlertCircle } from 'lucide-react';
import { authAPI } from '@/lib/auth';

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
      router.replace(res.role === 'admin' ? '/admin' : '/');
    } catch (err: any) {
      setError(err.message || 'Đăng nhập thất bại');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4" style={{ background: 'radial-gradient(ellipse at top, #1a1f35 0%, #0f1117 60%)' }}>
      <div className="w-full max-w-[400px]">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-[#6c63ff] inline-flex items-center justify-center mb-4">
            <BookOpen className="w-7 h-7 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white m-0">EbookAI</h1>
          <p className="text-[#8890a4] mt-1 text-sm">Đăng nhập để tiếp tục</p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="card p-8 flex flex-col gap-5">
          <div>
            <label className="text-sm text-[#8890a4] block mb-1.5">Tên đăng nhập</label>
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
            <label className="text-sm text-[#8890a4] block mb-1.5">Mật khẩu</label>
            <div className="relative">
              <input
                className="input pr-11"
                type={showPass ? 'text' : 'password'}
                placeholder="Nhập mật khẩu..."
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
              />
              <button
                type="button"
                onClick={() => setShowPass(p => !p)}
                className="absolute right-3 top-1/2 -translate-y-1/2 bg-none border-none cursor-pointer text-[#8890a4]"
              >
                {showPass ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {error && (
            <div className="flex items-center gap-2 bg-red-500/10 border border-red-500/20 rounded-xl p-3">
              <AlertCircle className="w-4 h-4 text-red-500 shrink-0" />
              <p className="text-sm text-red-500">{error}</p>
            </div>
          )}

          <button type="submit" disabled={loading} className="btn-primary justify-center p-3 mt-1">
            {loading ? 'Đang đăng nhập...' : <><LogIn className="w-4 h-4" /> Đăng nhập</>}
          </button>

          <p className="text-center text-[#8890a4] text-sm">
            Chưa có tài khoản?{' '}
            <Link href="/register" className="text-[#6c63ff] no-underline">Đăng ký</Link>
          </p>
        </form>

        <p className="text-center mt-6">
          <Link href="/" className="text-[#8890a4] text-sm no-underline">← Về trang chủ</Link>
        </p>
      </div>
    </div>
  );
}
