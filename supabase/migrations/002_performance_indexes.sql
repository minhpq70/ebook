-- ============================================================
-- Performance Optimization Migration
-- Optimized indexes for production workload
-- ============================================================

-- Drop existing HNSW index
DROP INDEX IF EXISTS book_chunks_embedding_idx;

-- Create optimized HNSW index for production
-- m=32 (vs 16): better recall, ef_construction=128 (vs 64): better quality
CREATE INDEX CONCURRENTLY IF NOT EXISTS book_chunks_embedding_idx_optimized
ON book_chunks USING hnsw (embedding vector_cosine_ops)
WITH (m = 32, ef_construction = 128, ef_search = 64);

-- Compound index for hybrid search filtering
-- Covers book_id + chunk_index for efficient filtering
CREATE INDEX CONCURRENTLY IF NOT EXISTS book_chunks_hybrid_search_idx
ON book_chunks (book_id, chunk_index)
WHERE book_id IS NOT NULL;

-- Partial index for active books only
-- Reduces index size and improves performance for ready books
CREATE INDEX CONCURRENTLY IF NOT EXISTS book_chunks_active_books_idx
ON book_chunks USING hnsw (embedding vector_cosine_ops)
WHERE EXISTS (
    SELECT 1 FROM books b
    WHERE b.id = book_chunks.book_id
    AND b.status = 'ready'
);

-- Covering index for common queries
-- Includes page_number, token_count, created_at for query optimization
CREATE INDEX CONCURRENTLY IF NOT EXISTS book_chunks_covering_idx
ON book_chunks (book_id, page_number, token_count, created_at);

-- Index for book status queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS books_status_idx
ON books (status, created_at DESC);

-- Index for book search by title/author
CREATE INDEX CONCURRENTLY IF NOT EXISTS books_search_idx
ON books USING gin (to_tsvector('english', title || ' ' || coalesce(author, '') || ' ' || coalesce(description, '')));

-- Index for recent books
CREATE INDEX CONCURRENTLY IF NOT EXISTS books_recent_idx
ON books (created_at DESC)
WHERE status = 'ready';

-- Analyze tables for query optimization
ANALYZE book_chunks;
ANALYZE books;