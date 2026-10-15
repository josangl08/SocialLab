-- 040: portada de los vídeos de Instagram (persistent-thumbnails, AD-9). Idempotente.

-- `thumbnail_url` de la Graph API: los vídeos no tienen otra imagen y a los que llevan audio
-- con copyright Instagram no les da `media_url`. Va firmada como `media_url`, así que no entra en
-- el trigger de invalidación: la miniatura guardada se genera una vez y sobrevive a que caduque
ALTER TABLE posts ADD COLUMN IF NOT EXISTS media_thumbnail_url text;
