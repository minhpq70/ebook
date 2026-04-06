-- Thêm cột Nhà xuất bản và Năm xuất bản vào bảng books
ALTER TABLE books
ADD COLUMN IF NOT EXISTS publisher text,
ADD COLUMN IF NOT EXISTS published_year text;

-- (Tuỳ chọn) Đánh index để hỗ trợ tìm kiếm theo nhà xuất bản nhanh hơn về sau
CREATE INDEX IF NOT EXISTS books_publisher_idx ON books(publisher);
