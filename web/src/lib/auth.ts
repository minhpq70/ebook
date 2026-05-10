/**
 * Auth utilities — httpOnly cookie auth + API fetch
 *
 * Token JWT được lưu trong httpOnly cookie bởi server.
 * JavaScript KHÔNG truy cập được token → an toàn trước XSS.
 * Browser tự gửi cookie kèm mỗi request nhờ credentials: 'include'.
 *
 * localStorage chỉ lưu thông tin user (role, username) để hiển thị UI.
 */
import { API_BASE } from './config';

const USER_KEY = 'ebook_user';

export interface AuthUser {
  username: string;
  role: 'admin' | 'user';
}

// ── User Info (UI only — KHÔNG chứa token) ───────────────────────────────────

export function setUser(user: AuthUser) {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function getUser(): AuthUser | null {
  if (typeof window === 'undefined') return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

export function clearAuth() {
  localStorage.removeItem(USER_KEY);
}

export function isLoggedIn(): boolean {
  return !!getUser();
}

export function isAdmin(): boolean {
  return getUser()?.role === 'admin';
}

// ── Fetch với httpOnly cookie ────────────────────────────────────────────────

async function authFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    credentials: 'include',  // ← browser tự gửi httpOnly cookie
  });

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
      credentials: 'include',  // ← nhận httpOnly cookie từ server
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Sai tên đăng nhập hoặc mật khẩu' }));
      throw new Error(err.detail);
    }
    const data = await res.json() as { role: string; username: string; message: string };
    // Lưu user info cho UI (token đã nằm trong cookie, JS không lấy được)
    setUser({ username: data.username, role: data.role as 'admin' | 'user' });
    return data;
  },

  register: async (username: string, password: string, email?: string) => {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password, email }),
      credentials: 'include',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Đăng ký thất bại' }));
      throw new Error(err.detail);
    }
    const data = await res.json() as { role: string; username: string; message: string };
    setUser({ username: data.username, role: data.role as 'admin' | 'user' });
    return data;
  },

  logout: async () => {
    await fetch(`${API_BASE}/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    });
    clearAuth();
  },

  changePassword: (currentPassword: string, newPassword: string) =>
    authFetch<{ message: string }>('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    }),
};

// ── Admin API Types ──────────────────────────────────────────────────────────

interface AIModelInfo {
  id: string;
  name: string;
  input_price: number;
  output_price: number;
}

interface EmbeddingModelInfo {
  id: string;
  name: string;
  price: number;
}

interface AIProvider {
  name: string;
  chat_models: AIModelInfo[];
  embedding_models: EmbeddingModelInfo[];
}

interface AIConfig {
  provider: string;
  chat_model: string;
  embedding_provider: string;
  embedding_model: string;
  updated_at?: string;
}

interface AIConfigResponse {
  current: AIConfig;
  providers: Record<string, AIProvider>;
  embedding_providers: Record<string, any>;
  available: Record<string, boolean>;
}

interface LogEntry {
  timestamp: string;
  [key: string]: string;
}

interface LogsResponse {
  logs: LogEntry[];
  total: number;
  note?: string;
}

interface UpdateBookResponse {
  message: string;
  book: Record<string, unknown>;
}

// ── Admin API ─────────────────────────────────────────────────────────────────

export const adminAPI = {
  getConfig: () => authFetch<AIConfigResponse>('/admin/config'),
  updateConfig: (data: { provider: string; chat_model: string; embedding_provider: string; embedding_model: string }) =>
    authFetch<{ message: string; config: AIConfig }>('/admin/config', { method: 'PUT', body: JSON.stringify(data) }),
  getLogs: (lines = 100) => authFetch<LogsResponse>(`/admin/logs?lines=${lines}`),
  updateBook: (id: string, data: Record<string, string>) =>
    authFetch<UpdateBookResponse>(`/admin/books/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),

  // Metrics & Monitoring
  getRuntime: () => authFetch<Record<string, unknown>>('/metrics/runtime'),
  getSummary: () => authFetch<Record<string, unknown>>('/metrics/summary'),
  getAnalytics: () => authFetch<Record<string, unknown>>('/metrics/analytics'),
  getErrors: (limit = 50) => authFetch<{ errors: Record<string, unknown>[]; summary: Record<string, unknown> }>(`/metrics/errors?limit=${limit}`),
  clearErrors: () => authFetch<{ message: string }>('/metrics/errors/clear', { method: 'POST' }),
};

export { authFetch };

