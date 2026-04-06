-- ============================================================
-- Ebook Platform — Supabase Schema (POC)
-- Enable pgvector extension
-- ============================================================

create extension if not exists vector;

-- ============================================================
-- BOOKS TABLE: metadata cho sách
-- ============================================================
create table if not exists books (
  id          uuid primary key default gen_random_uuid(),
  title       text not null,
  author      text,
  description text,
  language    text default 'vi',
  cover_url   text,
  file_path   text not null,       -- Supabase Storage path
  file_size   bigint,
  total_pages integer,
  status      text default 'processing' check (status in ('processing', 'ready', 'error')),
  created_at  timestamptz default now(),
  updated_at  timestamptz default now()
);

-- ============================================================
-- BOOK_CHUNKS TABLE: các đoạn văn đã được embed
-- ============================================================
create table if not exists book_chunks (
  id          uuid primary key default gen_random_uuid(),
  book_id     uuid not null references books(id) on delete cascade,
  chunk_index integer not null,
  page_number integer,
  content     text not null,                    -- nội dung đoạn văn gốc
  embedding   vector(1536),                     -- OpenAI text-embedding-3-small = 1536 dims
  token_count integer,
  created_at  timestamptz default now()
);

-- Index HNSW cho vector similarity search (nhanh nhất cho Supabase)
create index if not exists book_chunks_embedding_idx
  on book_chunks using hnsw (embedding vector_cosine_ops)
  with (m = 16, ef_construction = 64);

-- Index cho filter theo book_id
create index if not exists book_chunks_book_id_idx on book_chunks(book_id);

-- ============================================================
-- READING_SESSIONS TABLE: theo dõi tiến độ đọc (tùy chọn cho POC)
-- ============================================================
create table if not exists reading_sessions (
  id            uuid primary key default gen_random_uuid(),
  book_id       uuid not null references books(id) on delete cascade,
  session_key   text not null,     -- anonymous session cho POC (không cần auth)
  current_page  integer default 1,
  last_read_at  timestamptz default now()
);

-- ============================================================
-- QUERY_LOGS TABLE: log các câu hỏi và trả lời (debug/analytics)
-- ============================================================
create table if not exists query_logs (
  id            uuid primary key default gen_random_uuid(),
  book_id       uuid references books(id),
  query         text not null,
  task_type     text,              -- qa, explain, summarize_chapter, summarize_book, suggest
  retrieved_chunks integer,
  response      text,
  model         text,
  tokens_used   integer,
  latency_ms    integer,
  created_at    timestamptz default now()
);

-- ============================================================
-- FUNCTION: hybrid_search — kết hợp vector + full-text search
-- ============================================================
create or replace function hybrid_search(
  p_book_id     uuid,
  p_query_emb   vector(1536),
  p_query_text  text,
  p_top_k       int default 5,
  p_vector_w    float default 0.7,  -- weight cho vector search
  p_fts_w       float default 0.3   -- weight cho full-text search
)
returns table (
  id          uuid,
  book_id     uuid,
  chunk_index int,
  page_number int,
  content     text,
  score       float
)
language sql
as $$
  with vector_results as (
    select
      id, book_id, chunk_index, page_number, content,
      1 - (embedding <=> p_query_emb) as similarity
    from book_chunks
    where book_chunks.book_id = p_book_id
    order by embedding <=> p_query_emb
    limit p_top_k * 2
  ),
  fts_results as (
    select
      id, book_id, chunk_index, page_number, content,
      ts_rank(
        to_tsvector('simple', content),
        websearch_to_tsquery('simple', p_query_text)
      ) as fts_score
    from book_chunks
    where book_chunks.book_id = p_book_id
      and to_tsvector('simple', content) @@ websearch_to_tsquery('simple', p_query_text)
    limit p_top_k * 2
  ),
  combined as (
    select
      coalesce(v.id, f.id) as id,
      coalesce(v.book_id, f.book_id) as book_id,
      coalesce(v.chunk_index, f.chunk_index) as chunk_index,
      coalesce(v.page_number, f.page_number) as page_number,
      coalesce(v.content, f.content) as content,
      coalesce(v.similarity, 0) * p_vector_w + coalesce(f.fts_score, 0) * p_fts_w as score
    from vector_results v
    full outer join fts_results f on v.id = f.id
  )
  select * from combined
  order by score desc
  limit p_top_k;
$$;
