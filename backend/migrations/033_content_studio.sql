-- Migración 033: Content Studio
-- Soporte para formatos estructurados (Reel, Carrusel, Story), reportes de calidad,
-- rol en la matriz de contenido, y configuración del humanizador por cuenta.

ALTER TABLE posts
  ADD COLUMN IF NOT EXISTS content_format TEXT
    CHECK (content_format IN ('post','reel','carousel','story')),
  ADD COLUMN IF NOT EXISTS content_structure JSONB,   -- slides | beats | frames
  ADD COLUMN IF NOT EXISTS quality_report JSONB,
  ADD COLUMN IF NOT EXISTS matrix_role TEXT;          -- proof|teach|opinion|offer|story|learning|reflection

ALTER TABLE instagram_accounts
  ADD COLUMN IF NOT EXISTS humanizer_enabled BOOLEAN NOT NULL DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS banned_phrases TEXT[] NOT NULL DEFAULT '{}';
