-- Thêm cột metadata mở rộng vào bảng books
ALTER TABLE books
ADD COLUMN IF NOT EXISTS publisher text,
ADD COLUMN IF NOT EXISTS published_year text,
ADD COLUMN IF NOT EXISTS category text,
ADD COLUMN IF NOT EXISTS page_size text;

-- (Tuỳ chọn) Index hỗ trợ tìm kiếm
CREATE INDEX IF NOT EXISTS books_publisher_idx ON books(publisher);
CREATE INDEX IF NOT EXISTS books_category_idx ON books(category);
