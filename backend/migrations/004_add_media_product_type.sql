-- Migración 004: Agregar columna media_product_type para identificar tipo de contenido
-- Esta columna permite diferenciar entre FEED posts, REELS, STORIES, etc.

-- Agregar columna media_product_type si no existe
ALTER TABLE posts
ADD COLUMN IF NOT EXISTS media_product_type TEXT DEFAULT 'FEED';

-- Crear índice para búsquedas por tipo de producto
CREATE INDEX IF NOT EXISTS idx_posts_media_product_type
ON posts(media_product_type);

-- Comentario descriptivo
COMMENT ON COLUMN posts.media_product_type IS 'Tipo de producto de Instagram: FEED, REELS, STORY, AD, IGTV';

-- Actualizar posts existentes que son de tipo 'reel' para que tengan REELS como media_product_type
UPDATE posts
SET media_product_type = 'REELS'
WHERE post_type = 'reel' AND media_product_type = 'FEED';

-- Actualizar posts existentes que son de tipo 'story' para que tengan STORY como media_product_type
UPDATE posts
SET media_product_type = 'STORY'
WHERE post_type = 'story' AND media_product_type = 'FEED';
