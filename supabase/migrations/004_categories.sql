-- ============================================================
-- Migration 004: Categories table
-- Chạy trên Supabase SQL Editor
-- ============================================================

CREATE TABLE IF NOT EXISTS categories (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name         text UNIQUE NOT NULL,
  sort_order   int NOT NULL DEFAULT 0,
  created_at   timestamptz NOT NULL DEFAULT now()
);

-- Thêm một danh mục mặc định để có sẵn dữ liệu nếu cần
INSERT INTO categories (name, sort_order) VALUES
  ('Giáo trình', 1),
  ('Lịch sử', 2),
  ('Chính trị', 3)
ON CONFLICT (name) DO NOTHING;
