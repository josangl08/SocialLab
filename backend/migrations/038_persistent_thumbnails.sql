-- 038: miniaturas persistentes de los posts (persistent-thumbnails, AD-1, AD-2). Idempotente.

-- Bucket público: la ruta lleva un uuid aleatorio por versión de imagen. Solo escribe el
-- service role (sin políticas de INSERT para usuarios).
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES ('thumbnails', 'thumbnails', true, 524288, ARRAY['image/webp'])
ON CONFLICT (id) DO NOTHING;

-- URL pública sin sufijo; el cliente añade `_{size}.webp`
ALTER TABLE posts ADD COLUMN IF NOT EXISTS thumbnail_url_base text;

-- Cambiar la imagen del post, por cualquier vía, invalida la miniatura guardada
CREATE OR REPLACE FUNCTION posts_invalidate_thumbnail()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.media_url IS DISTINCT FROM OLD.media_url
       OR NEW.drive_file_id IS DISTINCT FROM OLD.drive_file_id THEN
        NEW.thumbnail_url_base := NULL;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS posts_invalidate_thumbnail ON posts;
CREATE TRIGGER posts_invalidate_thumbnail
    BEFORE UPDATE OF media_url, drive_file_id ON posts
    FOR EACH ROW
    EXECUTE FUNCTION posts_invalidate_thumbnail();
