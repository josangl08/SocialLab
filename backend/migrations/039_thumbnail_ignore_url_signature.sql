-- 039: el trigger de miniaturas ignora la query de media_url (persistent-thumbnails, AD-8). Idempotente.

-- Las URLs de Instagram llevan una firma (?oh=…&oe=…) que cambia en cada sync aunque la imagen
-- sea la misma: solo un cambio de la ruta cuenta como imagen nueva
CREATE OR REPLACE FUNCTION posts_invalidate_thumbnail()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF split_part(NEW.media_url, '?', 1) IS DISTINCT FROM split_part(OLD.media_url, '?', 1)
       OR NEW.drive_file_id IS DISTINCT FROM OLD.drive_file_id THEN
        NEW.thumbnail_url_base := NULL;
    END IF;
    RETURN NEW;
END;
$$;
