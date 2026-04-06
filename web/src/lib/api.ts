const rawUrl = (process.env.NEXT_PUBLIC_API_URL || 'https://ebook-api-7v44.onrender.com/api/v1').replace(/\/$/, '');
const API_BASE = rawUrl.endsWith('/api/v1') ? rawUrl : `${rawUrl}/api/v1`;

export interface Book {
  id: string;
  title: string;
  author?: string;
  publisher?: string;
  published_year?: string;
  category?: string;
  page_size?: string;
  ai_summary?: string;
  description?: string;
  language: string;
  cover_url?: string;
  file_path: string;
  file_size?: number;
  total_pages?: number;
  status: string;
  created_at: string;
}

export interface ChunkInfo {
  id: string;
  chunk_index: number;
  page_number?: number;
  content: string;
  score?: number;
}

export interface RAGQueryResponse {
  query: string;
  task_type: string;
  answer: string;
  sources: ChunkInfo[];
  model: string;
  tokens_used?: number;
}

export type TaskType = 'qa' | 'explain' | 'summarize_chapter' | 'summarize_book' | 'suggest';

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  // Tự động đính kèm Bearer token nếu đã đăng nhập
  let token: string | null = null;
  if (typeof window !== 'undefined') {
    token = localStorage.getItem('ebook_token');
  }
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Lỗi API');
  }
  return res.json();
}

// Books API
export const booksAPI = {
  list: () => fetchAPI<{ books: Book[]; total: number }>('/books'),

  get: (id: string) => fetchAPI<Book>(`/books/${id}`),

  upload: async (
    file: File,
    metadata: { title: string; author?: string; publisher?: string; published_year?: string; category?: string; page_size?: string; description?: string; language?: string }
  ) => {
    const { getToken } = await import('@/lib/auth');
    const form = new FormData();
    form.append('file', file);
    form.append('title', metadata.title);
    if (metadata.author) form.append('author', metadata.author);
    if (metadata.publisher) form.append('publisher', metadata.publisher);
    if (metadata.published_year) form.append('published_year', metadata.published_year);
    if (metadata.category) form.append('category', metadata.category);
    if (metadata.page_size) form.append('page_size', metadata.page_size);
    if (metadata.description) form.append('description', metadata.description);
    form.append('language', metadata.language || 'vi');

    const token = getToken();
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const res = await fetch(`${API_BASE}/books/upload`, { method: 'POST', headers, body: form });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Lỗi upload');
    }
    return res.json();
  },

  delete: (id: string) =>
    fetchAPI<{ message: string }>(`/books/${id}`, { method: 'DELETE' }),

  getPdfUrl: (id: string) => 
    fetchAPI<{ url: string; expires_in: number }>(`/books/${id}/pdf-url`),
};


// RAG API
export const ragAPI = {
  query: (req: {
    book_id: string;
    query: string;
    task_type: TaskType;
    top_k?: number;
  }) =>
    fetchAPI<RAGQueryResponse>('/rag/query', {
      method: 'POST',
      body: JSON.stringify(req),
    }),
};
