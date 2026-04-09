/**
 * Shared configuration — single source of truth cho API URL
 */
const rawUrl = (process.env.NEXT_PUBLIC_API_URL || 'https://ebook-api-7v44.onrender.com/api/v1').replace(/\/$/, '');
export const API_BASE = rawUrl.endsWith('/api/v1') ? rawUrl : `${rawUrl}/api/v1`;
