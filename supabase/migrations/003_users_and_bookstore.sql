-- ============================================================
-- Migration 003: Users, Chat History, AI Config, Book Extras
-- Chạy trên Supabase SQL Editor
-- ============================================================

-- 1. Bảng người dùng (admin + user thường)
CREATE TABLE IF NOT EXISTS app_users (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  username     text UNIQUE NOT NULL,
  email        text UNIQUE,
  password_hash text NOT NULL,
  role         text NOT NULL DEFAULT 'user',   -- 'admin' | 'user'
  is_active    bool NOT NULL DEFAULT true,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS app_users_role_idx ON app_users(role);

-- 2. Lịch sử chat của người dùng
CREATE TABLE IF NOT EXISTS chat_history (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    uuid REFERENCES app_users(id) ON DELETE CASCADE,
  book_id    uuid REFERENCES books(id) ON DELETE CASCADE,
  role       text NOT NULL,          -- 'user' | 'assistant'
  content    text NOT NULL,
  task_type  text,
  tokens_used int,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS chat_history_user_book ON chat_history(user_id, book_id);
CREATE INDEX IF NOT EXISTS chat_history_book_idx  ON chat_history(book_id);

-- 3. Cấu hình AI (1 row duy nhất, id=1)
CREATE TABLE IF NOT EXISTS ai_config (
  id              int PRIMARY KEY DEFAULT 1,
  provider        text NOT NULL DEFAULT 'openai',
  chat_model      text NOT NULL DEFAULT 'gpt-4o-mini',
  embedding_model text NOT NULL DEFAULT 'text-embedding-3-small',
  updated_at      timestamptz NOT NULL DEFAULT now()
);
INSERT INTO ai_config (id) VALUES (1) ON CONFLICT DO NOTHING;

-- 4. Thêm cột mới vào bảng books
ALTER TABLE books
  ADD COLUMN IF NOT EXISTS category     text,
  ADD COLUMN IF NOT EXISTS page_size    text,        -- khổ cỡ ví dụ "14x20cm"
  ADD COLUMN IF NOT EXISTS ai_summary   text,        -- tóm tắt do AI sinh
  ADD COLUMN IF NOT EXISTS cover_url    text;        -- URL ảnh bìa trên Storage

CREATE INDEX IF NOT EXISTS books_category_idx ON books(category);
