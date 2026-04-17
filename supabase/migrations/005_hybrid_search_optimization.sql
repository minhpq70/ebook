-- ============================================================
-- Hybrid Search Optimization
-- - Add GIN index for full-text search on book_chunks.content
-- - Replace hybrid_search RPC with a more efficient rank-fusion strategy
-- ============================================================

-- Full-text index for chunk content
CREATE INDEX IF NOT EXISTS book_chunks_content_fts_idx
ON book_chunks
USING gin (to_tsvector('simple', content));


-- Improved hybrid_search function
-- Strategy:
-- 1. Vector search retrieves a bounded candidate set via HNSW
-- 2. FTS retrieves a bounded lexical candidate set via GIN
-- 3. Reciprocal rank fusion (RRF) combines both rankings robustly
-- 4. A small raw-score contribution keeps ties more meaningful
CREATE OR REPLACE FUNCTION hybrid_search(
  p_book_id     uuid,
  p_query_emb   vector(1536),
  p_query_text  text,
  p_top_k       int default 5,
  p_vector_w    float default 0.7,
  p_fts_w       float default 0.3
)
RETURNS TABLE (
  id          uuid,
  book_id     uuid,
  chunk_index int,
  page_number int,
  content     text,
  score       float
)
LANGUAGE sql
AS $$
  WITH params AS (
    SELECT
      GREATEST(p_top_k, 1) AS top_k,
      GREATEST(p_top_k * 6, 24) AS candidate_limit,
      NULLIF(TRIM(p_query_text), '') AS cleaned_query,
      60.0::float AS rrf_k
  ),
  query_input AS (
    SELECT
      top_k,
      candidate_limit,
      cleaned_query,
      CASE
        WHEN cleaned_query IS NOT NULL THEN websearch_to_tsquery('simple', cleaned_query)
        ELSE NULL
      END AS ts_query,
      rrf_k
    FROM params
  ),
  vector_results AS (
    SELECT
      bc.id,
      bc.book_id,
      bc.chunk_index,
      bc.page_number,
      bc.content,
      1 - (bc.embedding <=> p_query_emb) AS similarity,
      ROW_NUMBER() OVER (ORDER BY bc.embedding <=> p_query_emb, bc.chunk_index) AS vec_rank
    FROM book_chunks bc
    CROSS JOIN query_input qi
    WHERE bc.book_id = p_book_id
      AND bc.embedding IS NOT NULL
    ORDER BY bc.embedding <=> p_query_emb, bc.chunk_index
    LIMIT (SELECT candidate_limit FROM query_input)
  ),
  fts_results AS (
    SELECT
      bc.id,
      bc.book_id,
      bc.chunk_index,
      bc.page_number,
      bc.content,
      ts_rank_cd(
        to_tsvector('simple', bc.content),
        qi.ts_query
      ) AS fts_score,
      ROW_NUMBER() OVER (
        ORDER BY ts_rank_cd(to_tsvector('simple', bc.content), qi.ts_query) DESC, bc.chunk_index
      ) AS fts_rank
    FROM book_chunks bc
    CROSS JOIN query_input qi
    WHERE bc.book_id = p_book_id
      AND qi.ts_query IS NOT NULL
      AND to_tsvector('simple', bc.content) @@ qi.ts_query
    ORDER BY ts_rank_cd(to_tsvector('simple', bc.content), qi.ts_query) DESC, bc.chunk_index
    LIMIT (SELECT candidate_limit FROM query_input)
  ),
  combined AS (
    SELECT
      COALESCE(v.id, f.id) AS id,
      COALESCE(v.book_id, f.book_id) AS book_id,
      COALESCE(v.chunk_index, f.chunk_index) AS chunk_index,
      COALESCE(v.page_number, f.page_number) AS page_number,
      COALESCE(v.content, f.content) AS content,
      COALESCE(v.similarity, 0.0) AS similarity,
      COALESCE(f.fts_score, 0.0) AS fts_score,
      COALESCE(v.vec_rank, 1000000) AS vec_rank,
      COALESCE(f.fts_rank, 1000000) AS fts_rank
    FROM vector_results v
    FULL OUTER JOIN fts_results f ON v.id = f.id
  )
  SELECT
    c.id,
    c.book_id,
    c.chunk_index,
    c.page_number,
    c.content,
    (
      (p_vector_w / (qi.rrf_k + c.vec_rank)) +
      (p_fts_w / (qi.rrf_k + c.fts_rank)) +
      (c.similarity * 0.05) +
      (c.fts_score * 0.02)
    )::float AS score
  FROM combined c
  CROSS JOIN query_input qi
  ORDER BY score DESC, c.chunk_index
  LIMIT (SELECT top_k FROM query_input);
$$;


ANALYZE book_chunks;
