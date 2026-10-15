-- 041: publicaciones en colaboración de otros autores (persistent-thumbnails, AD-10). Idempotente.

-- Media de `/{ig_user_id}/collaborative_media`: se muestran en el calendario, sin métricas propias
ALTER TABLE posts ADD COLUMN IF NOT EXISTS is_collaboration boolean NOT NULL DEFAULT false;
