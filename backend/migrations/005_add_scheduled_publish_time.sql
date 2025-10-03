-- Migración 005: Agregar columna scheduled_publish_time para programar publicaciones

-- Agregar columna scheduled_publish_time si no existe
ALTER TABLE posts
ADD COLUMN IF NOT EXISTS scheduled_publish_time TIMESTAMPTZ;

-- Crear índice para búsquedas de posts programados
CREATE INDEX IF NOT EXISTS idx_posts_scheduled_publish_time
ON posts(scheduled_publish_time)
WHERE scheduled_publish_time IS NOT NULL AND status = 'scheduled';

-- Comentario descriptivo
COMMENT ON COLUMN posts.scheduled_publish_time IS 'Fecha y hora programada para publicar en Instagram';
