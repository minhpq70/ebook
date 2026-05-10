-- Migration: Add external_id and source_system to books
-- This supports integration with external library systems (System A)

ALTER TABLE books
ADD COLUMN external_id VARCHAR(255),
ADD COLUMN source_system VARCHAR(100);

-- Index for fast lookup by external_id
CREATE INDEX idx_books_external_id ON books(external_id);
