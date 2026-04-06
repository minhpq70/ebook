/**
 * Auth utilities — token management + API fetch với Auth header
 */

const TOKEN_KEY = 'ebook_token';
const USER_KEY  = 'ebook_user';

export interface AuthUser {
  username: string;
  role: 'admin' | 'user';
}

// ── Token ─────────────────────────────────────────────────────────────────────

export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setAuth(token: string, user: AuthUser) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function getUser(): AuthUser | null {
  if (typeof window === 'undefined') return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

export function isLoggedIn(): boolean {
  return !!getToken();
}

export function isAdmin(): boolean {
  return getUser()?.role === 'admin';
}

// ── Fetch với Bearer token ────────────────────────────────────────────────────

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://ebook-api-7v44.onrender.com/api/v1';

async function authFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (res.status === 401) {
    clearAuth();
    if (typeof window !== 'undefined') window.location.href = '/login';
    throw new Error('Phiên đăng nhập hết hạn');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Lỗi API');
  }
  return res.json();
}

// ── Auth API ──────────────────────────────────────────────────────────────────

export const authAPI = {
  login: async (username: string, password: string) => {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Sai tên đăng nhập hoặc mật khẩu' }));
      throw new Error(err.detail);
    }
    return res.json() as Promise<{ access_token: string; role: string; username: string }>;
  },

  register: async (username: string, password: string, email?: string) => {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password, email }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Đăng ký thất bại' }));
      throw new Error(err.detail);
    }
    return res.json() as Promise<{ access_token: string; role: string; username: string }>;
  },

  changePassword: (currentPassword: string, newPassword: string) =>
    authFetch<{ message: string }>('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    }),
};

// ── Admin API ─────────────────────────────────────────────────────────────────

export const adminAPI = {
  getConfig:   () => authFetch<any>('/admin/config'),
  updateConfig: (data: { provider: string; chat_model: string; embedding_model: string }) =>
    authFetch<any>('/admin/config', { method: 'PUT', body: JSON.stringify(data) }),
  getLogs:     (lines = 100) => authFetch<any>(`/admin/logs?lines=${lines}`),
  updateBook:  (id: string, data: Record<string, string>) =>
    authFetch<any>(`/admin/books/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
};

export { authFetch };
