/**
 * Shared configuration — single source of truth cho API URL
 */
const rawUrl = (process.env.NEXT_PUBLIC_API_URL || 'https://ebook-api-7v44.onrender.com/api/v1').replace(/\/$/, '');
// API_BASE đảm bảo luôn kết thúc bằng /api/v1 để đồng bộ với backend routers
export const API_BASE = rawUrl.endsWith('/api/v1') ? rawUrl : `${rawUrl}/api/v1`;

if (typeof window !== 'undefined' && process.env.NODE_ENV === 'development') {
    console.log('Using API Base:', API_BASE);
}
