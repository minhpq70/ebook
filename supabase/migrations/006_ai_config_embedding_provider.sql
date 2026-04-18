-- Add embedding_provider column to ai_config table
-- Cho phép tách riêng Chat provider và Embedding provider
ALTER TABLE ai_config
  ADD COLUMN IF NOT EXISTS embedding_provider TEXT DEFAULT 'openai';
