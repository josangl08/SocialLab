-- Migración 002: Asegurar que la tabla 'posts' tenga las columnas necesarias
-- para la integración con Instagram

-- Agregar columna instagram_post_id si no existe
-- Esta columna almacena el ID único de la publicación en Instagram
ALTER TABLE posts
ADD COLUMN IF NOT EXISTS instagram_post_id TEXT UNIQUE;

-- Agregar columna publication_date si no existe
-- Esta columna almacena la fecha real de publicación en Instagram
ALTER TABLE posts
ADD COLUMN IF NOT EXISTS publication_date TIMESTAMPTZ;

-- Crear índice para mejorar búsquedas por instagram_post_id
CREATE INDEX IF NOT EXISTS idx_posts_instagram_post_id
ON posts(instagram_post_id)
WHERE instagram_post_id IS NOT NULL;

-- Comentarios descriptivos
COMMENT ON COLUMN posts.instagram_post_id IS 'ID único de la publicación en Instagram Graph API';
COMMENT ON COLUMN posts.publication_date IS 'Fecha y hora real de publicación en Instagram';
